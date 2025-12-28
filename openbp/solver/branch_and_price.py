"""
Branch-and-Price solver implementation.

This module provides the main BranchAndPrice solver that orchestrates
tree management, node selection, branching, and column generation.
"""

import math
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional

# Try to import from C++ core, fall back to Python
try:
    from openbp._core import (
        BestFirstSelector,
        BPNode,
        BPTree,
        BranchingDecision,
        NodeStatus,
        create_selector,
    )
    HAS_CPP_BACKEND = True
except ImportError:
    from openbp.core.node import BPNode, BranchingDecision, NodeStatus
    from openbp.core.selection import create_selector
    from openbp.core.tree import BPTree
    HAS_CPP_BACKEND = False

from openbp.branching.base import BranchingStrategy
from openbp.branching.variable import VariableBranching


class BPStatus(Enum):
    """Status of the branch-and-price solution."""
    OPTIMAL = auto()
    FEASIBLE = auto()  # Time limit with incumbent
    INFEASIBLE = auto()
    UNBOUNDED = auto()
    TIME_LIMIT = auto()
    NODE_LIMIT = auto()
    ERROR = auto()
    NOT_SOLVED = auto()


@dataclass
class BPConfig:
    """Configuration for branch-and-price solver."""
    # Termination criteria
    max_time: float = 3600.0  # seconds
    max_nodes: int = 0  # 0 = unlimited
    gap_tolerance: float = 1e-6

    # Node selection
    node_selection: str = "best_first"  # best_first, depth_first, hybrid, best_estimate

    # Column generation at each node
    cg_max_iterations: int = 1000
    cg_max_time: float = 0.0  # 0 = no limit
    cg_tolerance: float = 1e-6

    # Branching
    branching_strategy: Optional[BranchingStrategy] = None

    # Warm starting
    warm_start: bool = True
    column_pool_global: bool = True  # Share columns across nodes

    # Logging
    verbose: bool = True
    log_frequency: int = 10  # Log every N nodes

    # Callbacks
    node_callback: Optional[Callable[["BPNode", "BranchAndPrice"], None]] = None


@dataclass
class BPSolution:
    """Solution from branch-and-price."""
    status: BPStatus
    objective: float = float("inf")
    gap: float = float("inf")
    columns: list[Any] = field(default_factory=list)  # List[Column]
    column_values: list[float] = field(default_factory=list)

    # Statistics
    nodes_explored: int = 0
    nodes_pruned: int = 0
    total_time: float = 0.0
    time_in_cg: float = 0.0
    time_in_branching: float = 0.0

    # Best bounds
    lower_bound: float = float("-inf")
    upper_bound: float = float("inf")

    # Tree info
    max_depth: int = 0

    def is_optimal(self) -> bool:
        """Check if solution is proven optimal."""
        return self.status == BPStatus.OPTIMAL

    def is_feasible(self) -> bool:
        """Check if a feasible solution was found."""
        return self.status in (BPStatus.OPTIMAL, BPStatus.FEASIBLE)


class BranchAndPrice:
    """
    Branch-and-Price solver.

    Solves set partitioning/covering problems using column generation
    at each node of a branch-and-bound tree.

    Example:
        from openbp import BranchAndPrice, BestFirstSelection
        from openbp.branching import RyanFosterBranching
        from opencg import Problem

        problem = Problem.from_file("instance.txt")

        solver = BranchAndPrice(
            problem,
            branching_strategy=RyanFosterBranching(),
            node_selection=BestFirstSelection(),
        )

        solution = solver.solve(time_limit=3600)
        print(f"Optimal: {solution.objective}, Nodes: {solution.nodes_explored}")
    """

    def __init__(
        self,
        problem: Any,  # opencg.Problem
        branching_strategy: Optional[BranchingStrategy] = None,
        node_selection: Optional[Any] = None,  # NodeSelector
        pricing_class: Optional[type] = None,  # PricingProblem subclass
        master_class: Optional[type] = None,  # MasterProblem subclass
        config: Optional[BPConfig] = None,
    ):
        """
        Initialize the branch-and-price solver.

        Args:
            problem: The OpenCG problem to solve
            branching_strategy: Strategy for selecting branching decisions
            node_selection: Node selection policy (default: best-first)
            pricing_class: Class for pricing subproblem (default: from OpenCG)
            master_class: Class for master problem (default: from OpenCG)
            config: Solver configuration
        """
        self.problem = problem
        self.config = config or BPConfig()

        # Branching strategy
        self.branching_strategy = branching_strategy or VariableBranching()

        # Node selection
        if node_selection is not None:
            self.node_selector = node_selection
        else:
            self.node_selector = create_selector(self.config.node_selection)

        # Problem solving components (from OpenCG)
        self.pricing_class = pricing_class
        self.master_class = master_class

        # State
        self._tree: Optional[BPTree] = None
        self._column_pool: list[Any] = []  # Global column pool
        self._solution: Optional[BPSolution] = None
        self._start_time: float = 0.0
        self._cg_time: float = 0.0
        self._branch_time: float = 0.0

        # Import OpenCG components
        self._import_opencg()

    def _import_opencg(self) -> None:
        """Import OpenCG components."""
        try:
            from opencg import CGConfig, ColumnGeneration
            from opencg.master import HiGHSMasterProblem
            from opencg.pricing import PricingConfig, create_labeling_algorithm

            self._ColumnGeneration = ColumnGeneration
            self._CGConfig = CGConfig
            self._PricingConfig = PricingConfig

            if self.master_class is None:
                self.master_class = HiGHSMasterProblem

            if self.pricing_class is None:
                self._create_pricing = create_labeling_algorithm
            else:
                self._create_pricing = lambda p, c: self.pricing_class(p, c)

        except ImportError as e:
            raise ImportError(
                "OpenCG is required for BranchAndPrice. "
                "Install with: pip install -e ../opencg"
            ) from e

    def solve(
        self,
        time_limit: Optional[float] = None,
        node_limit: Optional[int] = None,
    ) -> BPSolution:
        """
        Solve the problem using branch-and-price.

        Args:
            time_limit: Maximum solving time (seconds)
            node_limit: Maximum number of nodes to explore

        Returns:
            BPSolution with status, objective, and statistics
        """
        # Apply limits
        if time_limit is not None:
            self.config.max_time = time_limit
        if node_limit is not None:
            self.config.max_nodes = node_limit

        self._start_time = time.time()
        self._cg_time = 0.0
        self._branch_time = 0.0

        # Initialize tree
        self._tree = BPTree(minimize=True)
        self._column_pool = list(self.problem.initial_columns) if hasattr(self.problem, 'initial_columns') else []

        # Add root to selector
        root = self._tree.root()
        self.node_selector.add_node(root)

        # Main B&P loop
        nodes_explored = 0

        while not self.node_selector.empty():
            # Check termination
            if self._check_termination(nodes_explored):
                break

            # Select next node
            node = self.node_selector.select_next()
            if node is None:
                break

            nodes_explored += 1
            node.status = NodeStatus.PROCESSING

            # Log progress
            if self.config.verbose and nodes_explored % self.config.log_frequency == 0:
                self._log_progress(nodes_explored, node)

            # Process node
            self._process_node(node)

            # Callback
            if self.config.node_callback:
                self.config.node_callback(node, self)

        # Build solution
        self._solution = self._build_solution(nodes_explored)
        return self._solution

    def _check_termination(self, nodes_explored: int) -> bool:
        """Check if we should terminate."""
        # Time limit
        elapsed = time.time() - self._start_time
        if elapsed >= self.config.max_time:
            return True

        # Node limit
        if self.config.max_nodes > 0 and nodes_explored >= self.config.max_nodes:
            return True

        # Gap closed
        if self._tree.gap() <= self.config.gap_tolerance:
            return True

        return False

    def _process_node(self, node: BPNode) -> None:
        """Process a single B&P node."""
        # Get branching decisions for this node
        decisions = node.all_decisions()

        # Solve column generation at this node
        cg_start = time.time()
        cg_result = self._solve_cg_at_node(node, decisions)
        self._cg_time += time.time() - cg_start

        if cg_result is None:
            # Infeasible
            self._tree.mark_processed(node, NodeStatus.PRUNED_INFEASIBLE)
            return

        lp_value, columns, column_values, duals = cg_result
        node.lp_value = lp_value
        node.lower_bound = lp_value

        # Check if pruned by bound
        if node.try_prune_by_bound(self._tree.global_upper_bound):
            return

        # Check if integer
        if self._is_integer_solution(column_values):
            node.is_integer = True
            node.set_solution(column_values)
            self._tree.mark_processed(node, NodeStatus.INTEGER)

            # Update incumbent
            if lp_value < self._tree.global_upper_bound:
                self._tree.set_incumbent(node)
                self._column_pool.extend(columns)  # Add to pool
                self.node_selector.on_bound_update(lp_value)

                # Prune nodes by bound
                self._tree.prune_by_bound()
                self.node_selector.prune()

            return

        # Branch
        branch_start = time.time()
        candidate = self.branching_strategy.select_best_candidate(
            node, columns, column_values, duals
        )
        self._branch_time += time.time() - branch_start

        if candidate is None:
            # No valid branching - treat as integer (shouldn't happen)
            node.is_integer = True
            self._tree.mark_processed(node, NodeStatus.INTEGER)
            return

        # Create children
        children = self._tree.create_children(node, candidate.decisions)

        # Add children to selector
        self.node_selector.add_nodes(children)

    def _solve_cg_at_node(
        self,
        node: BPNode,
        decisions: list[BranchingDecision],
    ) -> Optional[tuple]:
        """
        Solve column generation at a node.

        Returns:
            Tuple of (lp_value, columns, column_values, duals) or None if infeasible
        """
        # Create CG config
        cg_config = self._CGConfig(
            max_iterations=self.config.cg_max_iterations,
            max_time=self.config.cg_max_time if self.config.cg_max_time > 0 else float("inf"),
            optimality_tolerance=self.config.cg_tolerance,
        )

        # Create master and pricing
        master = self.master_class(self.problem)
        pricing_config = self._PricingConfig(max_columns=200)
        pricing = self._create_pricing(self.problem, pricing_config)

        # Apply branching decisions to master/pricing
        self._apply_decisions(master, pricing, decisions)

        # Warm start from column pool
        if self.config.warm_start and self._column_pool:
            valid_columns = self.branching_strategy.filter_columns(
                self._column_pool, decisions
            )
            for col in valid_columns:
                master.add_column(col)

        # Create and run CG
        cg = self._ColumnGeneration(self.problem, cg_config)
        cg.set_master(master)
        cg.set_pricing(pricing)

        try:
            result = cg.solve()
        except Exception as e:
            if self.config.verbose:
                print(f"  CG error at node {node.id}: {e}")
            return None

        if result.status.name == "INFEASIBLE":
            return None

        # Extract results
        lp_value = result.lp_objective
        columns = result.columns
        column_values = [getattr(c, 'value', 0.0) or 0.0 for c in columns]

        # Get duals
        duals = {}
        if hasattr(master, "get_duals"):
            try:
                dual_values = master.get_duals()
                for i, d in enumerate(dual_values):
                    duals[i] = d
            except Exception:
                pass

        # Add new columns to global pool
        if self.config.column_pool_global:
            for col in columns:
                if col not in self._column_pool:
                    self._column_pool.append(col)

        return (lp_value, columns, column_values, duals)

    def _apply_decisions(
        self,
        master: Any,
        pricing: Any,
        decisions: list[BranchingDecision],
    ) -> None:
        """
        Apply branching decisions to master and pricing.

        This modifies the master problem and pricing to enforce
        the branching constraints.
        """
        for decision in decisions:
            # Apply to master (add constraints)
            if hasattr(master, "add_branching_constraint"):
                master.add_branching_constraint(decision)

            # Apply to pricing (modify network/resources)
            if hasattr(pricing, "apply_branching_decision"):
                pricing.apply_branching_decision(decision)

    def _is_integer_solution(
        self,
        column_values: list[float],
        tolerance: float = 1e-6,
    ) -> bool:
        """Check if solution values are integral."""
        for val in column_values:
            frac = val - math.floor(val)
            if frac > tolerance and frac < 1 - tolerance:
                return False
        return True

    def _log_progress(self, nodes: int, node: BPNode) -> None:
        """Log solving progress."""
        elapsed = time.time() - self._start_time
        gap = self._tree.gap() * 100
        lb = self._tree.global_lower_bound
        ub = self._tree.global_upper_bound
        open_nodes = self.node_selector.size()

        print(
            f"Node {nodes:6d} | "
            f"Depth {node.depth:4d} | "
            f"LB {lb:12.4f} | "
            f"UB {ub:12.4f} | "
            f"Gap {gap:6.2f}% | "
            f"Open {open_nodes:5d} | "
            f"Time {elapsed:8.1f}s"
        )

    def _build_solution(self, nodes_explored: int) -> BPSolution:
        """Build the final solution."""
        elapsed = time.time() - self._start_time

        # Determine status
        if self._tree.gap() <= self.config.gap_tolerance:
            status = BPStatus.OPTIMAL
        elif self._tree.incumbent() is not None:
            if elapsed >= self.config.max_time:
                status = BPStatus.TIME_LIMIT
            elif self.config.max_nodes > 0 and nodes_explored >= self.config.max_nodes:
                status = BPStatus.NODE_LIMIT
            else:
                status = BPStatus.FEASIBLE
        elif elapsed >= self.config.max_time:
            status = BPStatus.TIME_LIMIT
        elif self.config.max_nodes > 0 and nodes_explored >= self.config.max_nodes:
            status = BPStatus.NODE_LIMIT
        else:
            status = BPStatus.INFEASIBLE

        # Get incumbent solution
        incumbent = self._tree.incumbent()
        if incumbent:
            objective = incumbent.lp_value
            # Get columns from incumbent
            # (This would need proper tracking in the solver)
            columns = []
            column_values = list(incumbent.solution) if incumbent.has_solution else []
        else:
            objective = float("inf")
            columns = []
            column_values = []

        return BPSolution(
            status=status,
            objective=objective,
            gap=self._tree.gap(),
            columns=columns,
            column_values=column_values,
            nodes_explored=nodes_explored,
            nodes_pruned=self._tree.stats.nodes_pruned_bound + self._tree.stats.nodes_pruned_infeasible,
            total_time=elapsed,
            time_in_cg=self._cg_time,
            time_in_branching=self._branch_time,
            lower_bound=self._tree.global_lower_bound,
            upper_bound=self._tree.global_upper_bound,
            max_depth=self._tree.stats.max_depth,
        )

    @property
    def tree(self) -> Optional[BPTree]:
        """Get the search tree."""
        return self._tree

    @property
    def column_pool(self) -> list[Any]:
        """Get the global column pool."""
        return self._column_pool

    @property
    def solution(self) -> Optional[BPSolution]:
        """Get the current solution."""
        return self._solution
