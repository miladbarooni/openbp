"""
OpenBP: Open-Source Branch-and-Price Framework

A research-grade, extensible framework for solving optimization problems
using Branch-and-Price, built on top of OpenCG for column generation.
"""

__version__ = "0.1.0"

# Core classes from C++ backend
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
    # Backend info
    HAS_CPP_BACKEND,
)

# Python branching strategies
from openbp.branching import (
    BranchingStrategy,
    BranchingCandidate,
    VariableBranching,
    RyanFosterBranching,
    ArcBranching,
    StrongBranching,
)

# Solver
from openbp.solver import (
    BranchAndPrice,
    BPConfig,
    BPSolution,
    BPStatus,
)

# Selection (Python wrappers for convenience)
from openbp.selection import (
    BestFirstSelection,
    DepthFirstSelection,
    BestEstimateSelection,
    HybridSelection,
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
