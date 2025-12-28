"""
Branch-and-Price solver for the Cutting Stock Problem.

The cutting stock problem: Given a roll width W and items with sizes
and demands, find the minimum number of rolls needed to cut all items.

This is a classic application of branch-and-price where column generation
generates cutting patterns and branching ensures integrality.

For cutting stock, we use:
- Master Problem: Set covering LP
- Pricing Problem: Bounded knapsack (NOT labeling algorithm)
- Branching: Variable branching on pattern usage

Note on branching implementation:
We track bounds on specific patterns (identified by their dict representation)
rather than column indices, since column indices change at each node.
"""

import math
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from openbp.solver import BPSolution, BPStatus


def _pattern_key(pattern: dict[int, int]) -> tuple[tuple[int, int], ...]:
    """Convert a pattern dict to a hashable tuple for tracking."""
    return tuple(sorted(pattern.items()))


@dataclass
class CuttingStockBPConfig:
    """Configuration for cutting stock branch-and-price."""
    # Termination
    max_time: float = 3600.0
    max_nodes: int = 0
    gap_tolerance: float = 1e-6

    # Column generation
    cg_max_iterations: int = 100

    # Node selection
    node_selection: str = "best_first"

    # Logging
    verbose: bool = True


@dataclass
class _NodeData:
    """Data associated with each B&P node for cutting stock."""
    # Pattern bounds: pattern_key -> (lower_bound, upper_bound)
    # These are accumulated from the path to root
    pattern_bounds: dict[tuple[tuple[int, int], ...], tuple[int, int]] = field(default_factory=dict)


def solve_cutting_stock_bp(
    instance: Any,  # opencg.applications.CuttingStockInstance
    config: Optional[CuttingStockBPConfig] = None,
) -> BPSolution:
    """
    Solve a cutting stock problem using branch-and-price.

    This extends OpenCG's column generation with a branch-and-bound
    tree to find and prove optimal integer solutions.

    Args:
        instance: A CuttingStockInstance from OpenCG
        config: Solver configuration

    Returns:
        BPSolution with optimal integer solution

    Example:
        from opencg.applications import CuttingStockInstance
        from openbp.applications import solve_cutting_stock_bp

        instance = CuttingStockInstance(
            roll_width=100,
            item_sizes=[45, 36, 31, 14],
            item_demands=[97, 610, 395, 211],
        )

        solution = solve_cutting_stock_bp(instance)
        print(f"Optimal rolls: {solution.objective}")
    """
    config = config or CuttingStockBPConfig()

    # Import OpenCG components
    try:
        from opencg.applications.cutting_stock import (
            CuttingStockMaster,
            CuttingStockPricing,
            _generate_ffd_patterns,
            create_cutting_stock_problem,
        )
        from opencg.core.column import Column
        from opencg.pricing import PricingConfig
    except ImportError as e:
        raise ImportError(
            "OpenCG is required. Install with: pip install -e ../opencg"
        ) from e

    start_time = time.time()

    # Build the problem
    problem = create_cutting_stock_problem(instance)

    # Statistics
    nodes_explored = 0
    nodes_pruned = 0
    max_depth = 0

    # L2 lower bound
    l2_bound = math.ceil(
        sum(s * d for s, d in zip(instance.item_sizes, instance.item_demands))
        / instance.roll_width
    )

    # Track best solution
    best_objective = float('inf')
    best_columns: list[Any] = []
    best_values: list[float] = []
    global_lower_bound = float(l2_bound)

    # Node queue: list of (lower_bound, node_id, depth, pattern_bounds)
    # Using a simple list with best-first selection
    node_queue: list[tuple[float, int, int, dict]] = []
    next_node_id = 0

    # Add root node
    node_queue.append((global_lower_bound, next_node_id, 0, {}))
    next_node_id += 1

    if config.verbose:
        print("Cutting Stock B&P Solver")
        print(f"  Items: {instance.num_items}")
        print(f"  Roll width: {instance.roll_width}")
        print(f"  L2 bound: {l2_bound}")
        print()

    # Main B&P loop
    while node_queue:
        # Check limits
        elapsed = time.time() - start_time
        if elapsed >= config.max_time:
            if config.verbose:
                print(f"Time limit reached ({elapsed:.1f}s)")
            break

        if config.max_nodes > 0 and nodes_explored >= config.max_nodes:
            if config.verbose:
                print(f"Node limit reached ({nodes_explored})")
            break

        # Select best node (lowest lower bound)
        node_queue.sort(key=lambda x: x[0])
        lb, node_id, depth, pattern_bounds = node_queue.pop(0)

        nodes_explored += 1
        max_depth = max(max_depth, depth)

        # Prune by bound
        if lb >= best_objective - config.gap_tolerance:
            nodes_pruned += 1
            continue

        if config.verbose and nodes_explored % 10 == 1:
            gap = (best_objective - global_lower_bound) / best_objective * 100 if best_objective < float('inf') else 100
            print(f"  Node {nodes_explored}: depth={depth}, LB={global_lower_bound:.2f}, "
                  f"UB={best_objective:.0f}, gap={gap:.2f}%")

        # Solve CG at this node with pattern bounds
        result = _solve_cg_with_bounds(
            instance, problem, pattern_bounds,
            config.cg_max_iterations, config.verbose
        )

        if result is None:
            # Infeasible
            nodes_pruned += 1
            continue

        lp_value, columns, column_values, patterns = result

        # Update global lower bound
        if node_queue:
            global_lower_bound = min(lp_value, min(n[0] for n in node_queue))
        else:
            global_lower_bound = lp_value

        # Check if integer
        is_integer = all(
            abs(v - round(v)) < 1e-6
            for v in column_values
        )

        if is_integer:
            # Found integer solution
            ip_value = int(round(sum(round(v) for v in column_values)))
            if ip_value < best_objective:
                best_objective = ip_value
                best_columns = columns
                best_values = column_values

                if config.verbose:
                    print(f"    New incumbent: {ip_value}")

            # Prune nodes with worse bound
            node_queue = [(b, i, d, p) for b, i, d, p in node_queue
                         if b < best_objective - config.gap_tolerance]

        else:
            # Need to branch - find most fractional variable
            best_frac = 0.0
            best_idx = -1
            for i, v in enumerate(column_values):
                frac = abs(v - round(v))
                if frac > best_frac:
                    best_frac = frac
                    best_idx = i

            if best_idx >= 0 and best_frac > 1e-6:
                frac_pattern = patterns[best_idx]
                frac_value = column_values[best_idx]
                pattern_key = _pattern_key(frac_pattern)

                floor_val = int(math.floor(frac_value))
                ceil_val = int(math.ceil(frac_value))

                # Left child: pattern <= floor
                left_bounds = dict(pattern_bounds)
                if pattern_key in left_bounds:
                    old_lb, old_ub = left_bounds[pattern_key]
                    left_bounds[pattern_key] = (old_lb, min(old_ub, floor_val))
                else:
                    left_bounds[pattern_key] = (0, floor_val)

                # Right child: pattern >= ceil
                right_bounds = dict(pattern_bounds)
                if pattern_key in right_bounds:
                    old_lb, old_ub = right_bounds[pattern_key]
                    right_bounds[pattern_key] = (max(old_lb, ceil_val), old_ub)
                else:
                    right_bounds[pattern_key] = (ceil_val, 10000)  # Large upper bound

                # Add children to queue
                node_queue.append((lp_value, next_node_id, depth + 1, left_bounds))
                next_node_id += 1
                node_queue.append((lp_value, next_node_id, depth + 1, right_bounds))
                next_node_id += 1

    # Build solution
    total_time = time.time() - start_time

    if best_objective < float('inf'):
        status = BPStatus.OPTIMAL if len(node_queue) == 0 else BPStatus.FEASIBLE
    else:
        status = BPStatus.INFEASIBLE

    # Calculate final gap
    if node_queue:
        final_lb = min(global_lower_bound, min(n[0] for n in node_queue))
    else:
        final_lb = global_lower_bound
    gap = (best_objective - final_lb) / best_objective if best_objective < float('inf') and best_objective > 0 else 0.0

    solution = BPSolution(
        status=status,
        objective=best_objective,
        lower_bound=final_lb,
        upper_bound=best_objective,
        gap=gap,
        nodes_explored=nodes_explored,
        nodes_pruned=nodes_pruned,
        max_depth=max_depth,
        total_time=total_time,
        time_in_cg=total_time * 0.9,  # Approximate
        time_in_branching=total_time * 0.1,
        columns=best_columns,
        column_values=best_values,
    )

    if config.verbose:
        print()
        print("B&P Complete:")
        print(f"  Status: {status.name}")
        print(f"  Objective: {best_objective}")
        print(f"  Nodes: {nodes_explored}")
        print(f"  Time: {total_time:.2f}s")

    return solution


def _solve_cg_with_bounds(
    instance,
    problem,
    pattern_bounds: dict[tuple[tuple[int, int], ...], tuple[int, int]],
    max_iterations: int,
    verbose: bool,
) -> Optional[tuple[float, list[Any], list[float], list[dict[int, int]]]]:
    """
    Solve column generation at a B&P node with pattern bounds.

    Args:
        instance: CuttingStockInstance
        problem: Problem from create_cutting_stock_problem
        pattern_bounds: Dict mapping pattern_key -> (lower_bound, upper_bound)
        max_iterations: Max CG iterations
        verbose: Print progress

    Returns:
        (lp_value, columns, column_values, patterns) or None if infeasible
        patterns[i] corresponds to column_values[i]
    """
    try:
        import highspy
    except ImportError:
        raise ImportError("HiGHS is required. Install with: pip install highspy")

    from opencg.applications.cutting_stock import (
        CuttingStockPricing,
        _generate_ffd_patterns,
    )
    from opencg.core.column import Column
    from opencg.pricing import PricingConfig

    # Create HiGHS model directly so we can control bounds
    highs = highspy.Highs()
    highs.setOptionValue('output_flag', False)
    highs.setOptionValue('log_to_console', False)
    highs.changeObjectiveSense(highspy.ObjSense.kMinimize)

    # Add demand constraints: sum_p a_ip * x_p >= d_i
    for i in range(instance.num_items):
        highs.addRow(
            float(instance.item_demands[i]),  # lower bound
            highspy.kHighsInf,                # upper bound
            0, [], []
        )

    # Track columns: list of (pattern, solver_idx)
    columns_info: list[tuple[dict[int, int], int]] = []
    next_col_id = 0

    def add_pattern_to_model(pattern: dict[int, int]) -> int:
        """Add a pattern to the HiGHS model with appropriate bounds."""
        nonlocal next_col_id

        pattern_key = _pattern_key(pattern)

        # Get bounds for this pattern
        lb, ub = pattern_bounds.get(pattern_key, (0, highspy.kHighsInf))

        # Build constraint coefficients
        indices = []
        values = []
        for item_id, count in pattern.items():
            if count > 0:
                indices.append(item_id)
                values.append(float(count))

        # Add column
        highs.addCol(
            1.0,             # cost
            float(lb),       # lower bound
            float(ub) if ub < 10000 else highspy.kHighsInf,  # upper bound
            len(indices),
            indices,
            values
        )

        solver_idx = highs.getNumCol() - 1
        columns_info.append((pattern.copy(), solver_idx))
        next_col_id += 1
        return solver_idx

    # Generate initial columns using FFD heuristic
    ffd_patterns = _generate_ffd_patterns(instance)
    for pattern in ffd_patterns:
        add_pattern_to_model(pattern)

    # Add trivial patterns for feasibility
    for i in range(instance.num_items):
        max_in_roll = instance.max_copies(i)
        if max_in_roll > 0:
            pattern = {i: max_in_roll}
            add_pattern_to_model(pattern)

    # Create pricing
    pricing_config = PricingConfig(reduced_cost_threshold=-1e-6)
    pricing = CuttingStockPricing(instance, problem, pricing_config)

    # Column generation loop
    for iteration in range(max_iterations):
        # Solve LP
        highs.run()
        status = highs.getModelStatus()

        if status != highspy.HighsModelStatus.kOptimal:
            return None

        # Get duals
        sol = highs.getSolution()
        duals = {i: sol.row_dual[i] for i in range(instance.num_items)}

        # Run pricing
        pricing.set_dual_values(duals)
        pricing_result = pricing.solve()

        # Check convergence
        if not pricing_result.columns:
            break

        # Add new columns
        for col in pricing_result.columns:
            pattern = col.attributes.get('pattern', {})
            add_pattern_to_model(pattern)

    # Get final solution
    highs.run()
    status = highs.getModelStatus()

    if status != highspy.HighsModelStatus.kOptimal:
        return None

    info = highs.getInfo()
    lp_value = info.objective_function_value

    sol = highs.getSolution()

    # Extract non-zero columns
    columns = []
    column_values = []
    patterns = []

    for pattern, solver_idx in columns_info:
        val = sol.col_value[solver_idx]
        if abs(val) > 1e-9:
            # Create a Column object for consistency
            col = Column(
                arc_indices=(),
                cost=1.0,
                covered_items=frozenset(pattern.keys()),
                column_id=solver_idx,
                attributes={'pattern': pattern},
            )
            columns.append(col)
            column_values.append(val)
            patterns.append(pattern)

    return (lp_value, columns, column_values, patterns)
