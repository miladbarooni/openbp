"""
Pure Python implementation of B&P tree.

This is a fallback when the C++ module is not available.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from openbp.core.node import BPNode, BranchingDecision, NodeStatus


@dataclass
class TreeStats:
    """Statistics about the B&P tree."""
    nodes_created: int = 0
    nodes_processed: int = 0
    nodes_pruned_bound: int = 0
    nodes_pruned_infeasible: int = 0
    nodes_integer: int = 0
    nodes_branched: int = 0
    nodes_open: int = 0
    max_depth: int = 0
    best_lower_bound: float = float("-inf")
    best_upper_bound: float = float("inf")

    def gap(self) -> float:
        """Current optimality gap."""
        if self.best_upper_bound == float("inf") or self.best_lower_bound == float("-inf"):
            return float("inf")
        if abs(self.best_upper_bound) < 1e-10:
            return 0.0 if abs(self.best_lower_bound) < 1e-10 else float("inf")
        return (self.best_upper_bound - self.best_lower_bound) / abs(self.best_upper_bound)


class BPTree:
    """The branch-and-price search tree."""

    def __init__(self, minimize: bool = True):
        """
        Create a new B&P tree.

        Args:
            minimize: True for minimization, False for maximization
        """
        self._minimize = minimize
        self._nodes: dict[int, BPNode] = {}
        self._next_id = 0
        self._global_lower_bound = float("-inf")
        self._global_upper_bound = float("inf")
        self._incumbent: Optional[BPNode] = None
        self._stats = TreeStats()

        # Create root node
        self._root = BPNode(id=self._next_id)
        self._next_id += 1
        self._nodes[self._root.id] = self._root
        self._stats.nodes_created = 1
        self._stats.nodes_open = 1

    def root(self) -> BPNode:
        """Get the root node."""
        return self._root

    @property
    def root_id(self) -> int:
        """Root node ID."""
        return self._root.id if self._root else -1

    def node(self, node_id: int) -> Optional[BPNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def has_node(self, node_id: int) -> bool:
        """Check if a node exists."""
        return node_id in self._nodes

    @property
    def num_nodes(self) -> int:
        """Total number of nodes."""
        return len(self._nodes)

    def create_child(
        self,
        parent: BPNode,
        decision: BranchingDecision,
    ) -> BPNode:
        """Create a child node."""
        child = BPNode(
            id=self._next_id,
            parent_id=parent.id,
            depth=parent.depth + 1,
            lower_bound=parent.lower_bound,
            upper_bound=parent.upper_bound,
        )
        child.local_decisions = [decision]
        child.inherited_decisions = parent.all_decisions()

        self._next_id += 1
        parent.add_child(child.id)
        self._nodes[child.id] = child

        self._stats.nodes_created += 1
        self._stats.nodes_open += 1
        if child.depth > self._stats.max_depth:
            self._stats.max_depth = child.depth

        return child

    def create_children(
        self,
        parent: BPNode,
        decisions: list[BranchingDecision],
    ) -> list[BPNode]:
        """Create multiple children."""
        children = [self.create_child(parent, d) for d in decisions]

        parent.status = NodeStatus.BRANCHED
        self._stats.nodes_branched += 1
        self._stats.nodes_open -= 1

        return children

    def mark_processed(self, node: BPNode, new_status: NodeStatus) -> None:
        """Mark a node as processed."""
        old_status = node.status
        node.status = new_status

        if old_status in (NodeStatus.PENDING, NodeStatus.PROCESSING):
            self._stats.nodes_processed += 1
            if new_status != NodeStatus.BRANCHED:
                self._stats.nodes_open -= 1

        if new_status == NodeStatus.PRUNED_BOUND:
            self._stats.nodes_pruned_bound += 1
        elif new_status == NodeStatus.PRUNED_INFEASIBLE:
            self._stats.nodes_pruned_infeasible += 1
        elif new_status == NodeStatus.INTEGER:
            self._stats.nodes_integer += 1

    @property
    def global_lower_bound(self) -> float:
        """Global lower bound."""
        return self._global_lower_bound

    @global_lower_bound.setter
    def global_lower_bound(self, value: float) -> None:
        self._global_lower_bound = value

    @property
    def global_upper_bound(self) -> float:
        """Global upper bound."""
        return self._global_upper_bound

    @global_upper_bound.setter
    def global_upper_bound(self, value: float) -> None:
        self._global_upper_bound = value

    @property
    def is_minimizing(self) -> bool:
        """Whether minimizing."""
        return self._minimize

    def update_bounds(self, node: BPNode) -> bool:
        """Update bounds after processing a node."""
        improved = False

        if node.is_integer and node.lp_value < self._global_upper_bound:
            self._global_upper_bound = node.lp_value
            self._stats.best_upper_bound = self._global_upper_bound
            improved = True

        return improved

    def compute_lower_bound(self, open_node_ids: list[int]) -> float:
        """Compute lower bound from open nodes."""
        lb = self._global_upper_bound
        for node_id in open_node_ids:
            node = self._nodes.get(node_id)
            if node and node.can_be_explored:
                lb = min(lb, node.lower_bound)
        return lb

    def prune_by_bound(self) -> int:
        """Prune all nodes by bound."""
        pruned = 0
        for node in self._nodes.values():
            if node.can_be_explored and node.try_prune_by_bound(self._global_upper_bound):
                self._stats.nodes_pruned_bound += 1
                self._stats.nodes_open -= 1
                pruned += 1
        return pruned

    def get_open_nodes(self) -> list[int]:
        """Get IDs of all open nodes."""
        return [n.id for n in self._nodes.values() if n.can_be_explored]

    @property
    def is_complete(self) -> bool:
        """Whether tree exploration is complete."""
        return self._stats.nodes_open == 0

    def gap(self) -> float:
        """Current optimality gap."""
        if self._global_upper_bound == float("inf") or self._global_lower_bound == float("-inf"):
            return float("inf")
        if abs(self._global_upper_bound) < 1e-10:
            return 0.0 if abs(self._global_lower_bound) < 1e-10 else float("inf")
        return (self._global_upper_bound - self._global_lower_bound) / abs(self._global_upper_bound)

    @property
    def stats(self) -> TreeStats:
        """Tree statistics."""
        return self._stats

    def incumbent(self) -> Optional[BPNode]:
        """Get the incumbent node."""
        return self._incumbent

    def set_incumbent(self, node: BPNode) -> None:
        """Set the incumbent node."""
        self._incumbent = node
        if node:
            self._global_upper_bound = node.lp_value
            self._stats.best_upper_bound = self._global_upper_bound

    def get_path_to_root(self, target_id: int) -> list[int]:
        """Get node IDs from root to target."""
        path = []
        current = target_id

        while current != -1:
            path.append(current)
            node = self._nodes.get(current)
            if node is None:
                break
            current = node.parent_id

        path.reverse()
        return path

    def for_each_node(self, callback: Callable[[BPNode], None]) -> None:
        """Iterate over all nodes."""
        for node in self._nodes.values():
            callback(node)
