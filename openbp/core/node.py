"""
Pure Python implementation of B&P tree nodes.

This is a fallback when the C++ module is not available.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Any
import math


class NodeStatus(Enum):
    """Status of a B&P tree node."""
    PENDING = auto()
    PROCESSING = auto()
    BRANCHED = auto()
    PRUNED_BOUND = auto()
    PRUNED_INFEASIBLE = auto()
    INTEGER = auto()
    FATHOMED = auto()


class BranchType(Enum):
    """Type of branching decision."""
    VARIABLE = auto()
    RYAN_FOSTER = auto()
    ARC = auto()
    RESOURCE = auto()
    CUSTOM = auto()


@dataclass
class BranchingDecision:
    """A single branching decision."""
    type: BranchType = BranchType.VARIABLE

    # Variable branching
    variable_index: int = -1
    bound_value: float = 0.0
    is_upper_bound: bool = False

    # Ryan-Foster
    item_i: int = -1
    item_j: int = -1
    same_column: bool = False

    # Arc branching
    arc_index: int = -1
    source_node: int = -1
    arc_required: bool = False

    # Resource branching
    resource_index: int = -1
    lower_bound: float = 0.0
    upper_bound: float = float("inf")

    # Custom
    custom_int_data: List[int] = field(default_factory=list)
    custom_float_data: List[float] = field(default_factory=list)

    @staticmethod
    def variable_branch(var_idx: int, value: float, upper: bool) -> "BranchingDecision":
        """Create a variable branching decision."""
        return BranchingDecision(
            type=BranchType.VARIABLE,
            variable_index=var_idx,
            bound_value=value,
            is_upper_bound=upper,
        )

    @staticmethod
    def ryan_foster(item_i: int, item_j: int, same: bool) -> "BranchingDecision":
        """Create a Ryan-Foster branching decision."""
        return BranchingDecision(
            type=BranchType.RYAN_FOSTER,
            item_i=item_i,
            item_j=item_j,
            same_column=same,
        )

    @staticmethod
    def arc_branch(arc: int, source: int, required: bool) -> "BranchingDecision":
        """Create an arc branching decision."""
        return BranchingDecision(
            type=BranchType.ARC,
            arc_index=arc,
            source_node=source,
            arc_required=required,
        )

    @staticmethod
    def resource_branch(res_idx: int, lb: float, ub: float) -> "BranchingDecision":
        """Create a resource branching decision."""
        return BranchingDecision(
            type=BranchType.RESOURCE,
            resource_index=res_idx,
            lower_bound=lb,
            upper_bound=ub,
        )


@dataclass
class BPNode:
    """A node in the branch-and-price tree."""
    id: int = 0
    parent_id: int = -1
    depth: int = 0

    lower_bound: float = float("-inf")
    upper_bound: float = float("inf")
    lp_value: float = float("inf")

    status: NodeStatus = NodeStatus.PENDING
    is_integer: bool = False

    inherited_decisions: List[BranchingDecision] = field(default_factory=list)
    local_decisions: List[BranchingDecision] = field(default_factory=list)
    children: List[int] = field(default_factory=list)

    solution: List[float] = field(default_factory=list)
    solution_columns: List[int] = field(default_factory=list)

    @property
    def gap(self) -> float:
        """Compute optimality gap."""
        if self.upper_bound == float("inf") or self.lower_bound == float("-inf"):
            return float("inf")
        if self.upper_bound == 0.0:
            return 0.0 if self.lower_bound == 0.0 else float("inf")
        return (self.upper_bound - self.lower_bound) / abs(self.upper_bound)

    @property
    def is_processed(self) -> bool:
        """Whether node has been processed."""
        return self.status not in (NodeStatus.PENDING, NodeStatus.PROCESSING)

    @property
    def is_pruned(self) -> bool:
        """Whether node has been pruned."""
        return self.status in (
            NodeStatus.PRUNED_BOUND,
            NodeStatus.PRUNED_INFEASIBLE,
            NodeStatus.FATHOMED,
        )

    @property
    def can_be_explored(self) -> bool:
        """Whether node can still be explored."""
        return self.status == NodeStatus.PENDING

    @property
    def has_children(self) -> bool:
        """Whether node has children."""
        return len(self.children) > 0

    @property
    def has_solution(self) -> bool:
        """Whether node has a solution stored."""
        return len(self.solution) > 0

    @property
    def num_decisions(self) -> int:
        """Total number of branching decisions."""
        return len(self.inherited_decisions) + len(self.local_decisions)

    def all_decisions(self) -> List[BranchingDecision]:
        """Get all branching decisions."""
        return self.inherited_decisions + self.local_decisions

    def add_local_decision(self, decision: BranchingDecision) -> None:
        """Add a local branching decision."""
        self.local_decisions.append(decision)

    def add_child(self, child_id: int) -> None:
        """Add a child node ID."""
        self.children.append(child_id)

    def try_prune_by_bound(self, global_upper: float) -> bool:
        """Try to prune by bound."""
        if self.lower_bound >= global_upper - 1e-6:
            self.status = NodeStatus.PRUNED_BOUND
            return True
        return False

    def set_solution(self, sol: List[float]) -> None:
        """Set the solution vector."""
        self.solution = sol

    def set_solution_columns(self, cols: List[int]) -> None:
        """Set the solution columns."""
        self.solution_columns = cols

    def set_inherited_decisions(self, decisions: List[BranchingDecision]) -> None:
        """Set inherited decisions."""
        self.inherited_decisions = decisions
