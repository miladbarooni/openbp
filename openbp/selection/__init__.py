"""
Node selection policies for branch-and-price.

This module provides Python wrappers around the C++ node selection
implementations for convenience and type hints.

Available Policies:
-----------------
- BestFirstSelection: Explore nodes with lowest bound first
- DepthFirstSelection: Dive deep before backtracking
- BestEstimateSelection: Balance bound and depth
- HybridSelection: Alternate between strategies
"""

from typing import Optional

try:
    from openbp._core import (
        BestEstimateSelector,
        BestFirstSelector,
        DepthFirstSelector,
        HybridSelector,
        NodeSelector,
        create_selector,
    )
    HAS_CPP_BACKEND = True
except ImportError:
    from openbp.core.selection import (
        BestEstimateSelector,
        BestFirstSelector,
        DepthFirstSelector,
        HybridSelector,
        NodeSelector,
        create_selector,
    )
    HAS_CPP_BACKEND = False


class BestFirstSelection:
    """
    Best-first (best-bound) node selection.

    Always explores the node with the lowest lower bound.
    This minimizes the number of nodes explored but may delay
    finding good integer solutions.

    Best for: Proving optimality on easy instances.
    """

    def __new__(cls) -> NodeSelector:
        return BestFirstSelector()


class DepthFirstSelection:
    """
    Depth-first node selection (diving).

    Explores deepest nodes first, finding integer solutions quickly.
    Uses best-bound as tiebreaker at same depth.

    Best for: Finding good solutions on hard instances.
    """

    def __new__(cls) -> NodeSelector:
        return DepthFirstSelector()


class BestEstimateSelection:
    """
    Best-estimate node selection.

    Uses a combination of lower bound and depth-based estimate
    to prioritize nodes likely to lead to good solutions.

    Args:
        estimate_weight: Weight for depth-based estimate (default 0.5)
                        Higher values favor deeper nodes.
    """

    def __new__(cls, estimate_weight: float = 0.5) -> NodeSelector:
        return BestEstimateSelector(estimate_weight)


class HybridSelection:
    """
    Hybrid node selection with periodic diving.

    Alternates between best-first and depth-first selection
    to balance bound improvement and solution finding.

    Args:
        dive_frequency: How often to start diving (every N nodes)
        dive_depth: How deep to dive before switching back
    """

    def __new__(
        cls,
        dive_frequency: int = 5,
        dive_depth: int = 10,
    ) -> NodeSelector:
        return HybridSelector(dive_frequency, dive_depth)


__all__ = [
    "NodeSelector",
    "BestFirstSelector",
    "DepthFirstSelector",
    "BestEstimateSelector",
    "HybridSelector",
    "BestFirstSelection",
    "DepthFirstSelection",
    "BestEstimateSelection",
    "HybridSelection",
    "create_selector",
    "HAS_CPP_BACKEND",
]
