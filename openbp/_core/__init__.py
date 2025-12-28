"""
OpenBP C++ Core Module

This module provides high-performance C++ implementations of tree
structures and node selection policies.

If the C++ module is not available (build failed), we fall back to
pure Python implementations.
"""

try:
    from openbp._core import (
        HAS_CPP_BACKEND,
        BestEstimateSelector,
        BestFirstSelector,
        # Node and tree
        BPNode,
        BPTree,
        BranchingDecision,
        BranchType,
        DepthFirstSelector,
        HybridSelector,
        # Selection policies
        NodeSelector,
        NodeStatus,
        TreeStats,
        # Version info
        __version__,
        create_selector,
    )
except ImportError:
    # C++ module not available - use pure Python fallback
    HAS_CPP_BACKEND = False
    from openbp.core.node import (
        BPNode,
        BranchingDecision,
        BranchType,
        NodeStatus,
    )
    from openbp.core.selection import (
        BestEstimateSelector,
        BestFirstSelector,
        DepthFirstSelector,
        HybridSelector,
        NodeSelector,
        create_selector,
    )
    from openbp.core.tree import BPTree, TreeStats
    __version__ = "0.1.0"

__all__ = [
    "BPNode",
    "BPTree",
    "TreeStats",
    "NodeStatus",
    "BranchType",
    "BranchingDecision",
    "NodeSelector",
    "BestFirstSelector",
    "DepthFirstSelector",
    "BestEstimateSelector",
    "HybridSelector",
    "create_selector",
    "__version__",
    "HAS_CPP_BACKEND",
]
