"""
OpenBP C++ Core Module

This module provides high-performance C++ implementations of tree
structures and node selection policies.

If the C++ module is not available (build failed), we fall back to
pure Python implementations.
"""

try:
    from openbp._core import (
        # Node and tree
        BPNode,
        BPTree,
        TreeStats,
        NodeStatus,
        BranchType,
        BranchingDecision,
        # Selection policies
        NodeSelector,
        BestFirstSelector,
        DepthFirstSelector,
        BestEstimateSelector,
        HybridSelector,
        create_selector,
        # Version info
        __version__,
        HAS_CPP_BACKEND,
    )
except ImportError:
    # C++ module not available - use pure Python fallback
    HAS_CPP_BACKEND = False
    from openbp.core.node import (
        BPNode,
        NodeStatus,
        BranchType,
        BranchingDecision,
    )
    from openbp.core.tree import BPTree, TreeStats
    from openbp.core.selection import (
        NodeSelector,
        BestFirstSelector,
        DepthFirstSelector,
        BestEstimateSelector,
        HybridSelector,
        create_selector,
    )
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
