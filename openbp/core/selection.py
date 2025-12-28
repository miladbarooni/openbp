"""
Pure Python implementation of node selection policies.

This is a fallback when the C++ module is not available.
"""

import heapq
from abc import ABC, abstractmethod
from typing import Optional

from openbp.core.node import BPNode


class NodeSelector(ABC):
    """Abstract base class for node selection policies."""

    @abstractmethod
    def add_node(self, node: BPNode) -> None:
        """Add a node to the open queue."""
        pass

    def add_nodes(self, nodes: list[BPNode]) -> None:
        """Add multiple nodes to the open queue."""
        for node in nodes:
            self.add_node(node)

    @abstractmethod
    def select_next(self) -> Optional[BPNode]:
        """Select and remove the next node to explore."""
        pass

    @abstractmethod
    def peek_next(self) -> Optional[BPNode]:
        """Peek at the next node without removing it."""
        pass

    @abstractmethod
    def empty(self) -> bool:
        """Check if there are any open nodes."""
        pass

    @abstractmethod
    def size(self) -> int:
        """Get the number of open nodes."""
        pass

    @abstractmethod
    def prune(self) -> int:
        """Remove pruned nodes from the queue."""
        pass

    def on_bound_update(self, new_bound: float) -> None:
        """Called when global upper bound is updated."""
        pass

    @abstractmethod
    def best_bound(self) -> float:
        """Get the best (lowest) bound among open nodes."""
        pass

    @abstractmethod
    def get_open_node_ids(self) -> list[int]:
        """Get all open node IDs."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all nodes from the selector."""
        pass


class BestFirstSelector(NodeSelector):
    """Best-first (best-bound) node selection."""

    def __init__(self):
        self._heap: list[tuple] = []  # (bound, id, node)
        self._counter = 0

    def add_node(self, node: BPNode) -> None:
        if node and node.can_be_explored:
            heapq.heappush(self._heap, (node.lower_bound, self._counter, node))
            self._counter += 1

    def select_next(self) -> Optional[BPNode]:
        self.prune()
        while self._heap:
            _, _, node = heapq.heappop(self._heap)
            if node.can_be_explored:
                return node
        return None

    def peek_next(self) -> Optional[BPNode]:
        while self._heap:
            if self._heap[0][2].can_be_explored:
                return self._heap[0][2]
            heapq.heappop(self._heap)
        return None

    def empty(self) -> bool:
        return len(self._heap) == 0

    def size(self) -> int:
        return len(self._heap)

    def prune(self) -> int:
        valid = [(b, c, n) for b, c, n in self._heap if n.can_be_explored]
        removed = len(self._heap) - len(valid)
        self._heap = valid
        heapq.heapify(self._heap)
        return removed

    def best_bound(self) -> float:
        if not self._heap:
            return float("inf")
        return self._heap[0][0]

    def get_open_node_ids(self) -> list[int]:
        return [n.id for _, _, n in self._heap]

    def clear(self) -> None:
        self._heap = []


class DepthFirstSelector(NodeSelector):
    """Depth-first node selection."""

    def __init__(self):
        self._heap: list[tuple] = []  # (-depth, bound, id, node)
        self._counter = 0

    def add_node(self, node: BPNode) -> None:
        if node and node.can_be_explored:
            heapq.heappush(self._heap, (-node.depth, node.lower_bound, self._counter, node))
            self._counter += 1

    def select_next(self) -> Optional[BPNode]:
        self.prune()
        while self._heap:
            _, _, _, node = heapq.heappop(self._heap)
            if node.can_be_explored:
                return node
        return None

    def peek_next(self) -> Optional[BPNode]:
        while self._heap:
            if self._heap[0][3].can_be_explored:
                return self._heap[0][3]
            heapq.heappop(self._heap)
        return None

    def empty(self) -> bool:
        return len(self._heap) == 0

    def size(self) -> int:
        return len(self._heap)

    def prune(self) -> int:
        valid = [(d, b, c, n) for d, b, c, n in self._heap if n.can_be_explored]
        removed = len(self._heap) - len(valid)
        self._heap = valid
        heapq.heapify(self._heap)
        return removed

    def best_bound(self) -> float:
        if not self._heap:
            return float("inf")
        return min(b for _, b, _, _ in self._heap)

    def get_open_node_ids(self) -> list[int]:
        return [n.id for _, _, _, n in self._heap]

    def clear(self) -> None:
        self._heap = []


class BestEstimateSelector(NodeSelector):
    """Best-estimate node selection."""

    def __init__(self, estimate_weight: float = 0.5):
        self._nodes: list[BPNode] = []
        self._estimate_weight = estimate_weight
        self._global_upper = float("inf")
        self._max_depth = 1

    def add_node(self, node: BPNode) -> None:
        if node and node.can_be_explored:
            self._nodes.append(node)
            self._max_depth = max(self._max_depth, node.depth)

    def select_next(self) -> Optional[BPNode]:
        self.prune()
        if not self._nodes:
            return None

        best_idx = min(range(len(self._nodes)), key=lambda i: self._estimate(self._nodes[i]))
        node = self._nodes.pop(best_idx)
        return node

    def peek_next(self) -> Optional[BPNode]:
        if not self._nodes:
            return None
        return min(self._nodes, key=self._estimate)

    def _estimate(self, node: BPNode) -> float:
        lb = node.lower_bound
        if self._global_upper == float("inf"):
            return lb - self._estimate_weight * node.depth
        depth_ratio = node.depth / max(1, self._max_depth)
        gap = self._global_upper - lb
        return lb + self._estimate_weight * (1.0 - depth_ratio) * gap

    def empty(self) -> bool:
        return len(self._nodes) == 0

    def size(self) -> int:
        return len(self._nodes)

    def prune(self) -> int:
        old_size = len(self._nodes)
        self._nodes = [n for n in self._nodes if n.can_be_explored]
        return old_size - len(self._nodes)

    def on_bound_update(self, new_bound: float) -> None:
        self._global_upper = new_bound

    def best_bound(self) -> float:
        if not self._nodes:
            return float("inf")
        return min(n.lower_bound for n in self._nodes)

    def get_open_node_ids(self) -> list[int]:
        return [n.id for n in self._nodes]

    def clear(self) -> None:
        self._nodes = []


class HybridSelector(NodeSelector):
    """Hybrid node selection with periodic diving."""

    def __init__(self, dive_frequency: int = 5, dive_depth: int = 10):
        self._best_first = BestFirstSelector()
        self._depth_first = DepthFirstSelector()
        self._dive_frequency = dive_frequency
        self._dive_depth = dive_depth
        self._nodes_since_dive = 0
        self._current_dive_depth = 0
        self._diving = False

    def add_node(self, node: BPNode) -> None:
        if node and node.can_be_explored:
            self._best_first.add_node(node)
            self._depth_first.add_node(node)

    def select_next(self) -> Optional[BPNode]:
        if not self._diving and self._nodes_since_dive >= self._dive_frequency:
            self._diving = True
            self._current_dive_depth = 0

        if self._diving:
            node = self._depth_first.select_next()
            if node:
                self._current_dive_depth += 1
                if self._current_dive_depth >= self._dive_depth:
                    self._diving = False
                    self._nodes_since_dive = 0
                self._best_first.prune()
                return node
            self._diving = False

        self._nodes_since_dive += 1
        self._depth_first.prune()
        return self._best_first.select_next()

    def peek_next(self) -> Optional[BPNode]:
        if self._diving:
            return self._depth_first.peek_next()
        return self._best_first.peek_next()

    def empty(self) -> bool:
        return self._best_first.empty()

    def size(self) -> int:
        return self._best_first.size()

    def prune(self) -> int:
        r1 = self._best_first.prune()
        r2 = self._depth_first.prune()
        return max(r1, r2)

    def best_bound(self) -> float:
        return self._best_first.best_bound()

    def get_open_node_ids(self) -> list[int]:
        return self._best_first.get_open_node_ids()

    def clear(self) -> None:
        self._best_first.clear()
        self._depth_first.clear()
        self._nodes_since_dive = 0
        self._current_dive_depth = 0
        self._diving = False


def create_selector(name: str) -> NodeSelector:
    """Create a node selector by name."""
    name_lower = name.lower()
    if name_lower in ("best_first", "bestfirst"):
        return BestFirstSelector()
    elif name_lower in ("depth_first", "depthfirst"):
        return DepthFirstSelector()
    elif name_lower in ("best_estimate", "bestestimate"):
        return BestEstimateSelector()
    elif name_lower == "hybrid":
        return HybridSelector()
    return BestFirstSelector()
