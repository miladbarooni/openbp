"""
OpenBP: Open-Source Branch-and-Price Framework

A research-grade, extensible framework for solving optimization problems
using Branch-and-Price, built on top of OpenCG for column generation.
"""

__version__ = "0.1.0"

# Core classes from C++ backend
from openbp._core import (
    # Backend info
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
    create_selector,
)

# Python branching strategies
from openbp.branching import (
    ArcBranching,
    BranchingCandidate,
    BranchingStrategy,
    RyanFosterBranching,
    StrongBranching,
    VariableBranching,
)

# Selection (Python wrappers for convenience)
from openbp.selection import (
    BestEstimateSelection,
    BestFirstSelection,
    DepthFirstSelection,
    HybridSelection,
)

# Solver
from openbp.solver import (
    BPConfig,
    BPSolution,
    BPStatus,
    BranchAndPrice,
)

__all__ = [
    # Version
    "__version__",
    # C++ core
    "BPNode",
    "BPTree",
    "TreeStats",
    "NodeStatus",
    "BranchType",
    "BranchingDecision",
    # Selection (C++)
    "NodeSelector",
    "BestFirstSelector",
    "DepthFirstSelector",
    "BestEstimateSelector",
    "HybridSelector",
    "create_selector",
    # Selection (Python wrappers)
    "BestFirstSelection",
    "DepthFirstSelection",
    "BestEstimateSelection",
    "HybridSelection",
    # Branching
    "BranchingStrategy",
    "BranchingCandidate",
    "VariableBranching",
    "RyanFosterBranching",
    "ArcBranching",
    "StrongBranching",
    # Solver
    "BranchAndPrice",
    "BPConfig",
    "BPSolution",
    "BPStatus",
    # Backend
    "HAS_CPP_BACKEND",
]
