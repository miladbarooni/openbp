"""
Branch-and-Price solver orchestrator.

This module provides the main BranchAndPrice solver that coordinates:
- Tree management (C++ BPTree)
- Node selection (C++ selectors)
- Branching strategies (Python extensible)
- Column generation integration (OpenCG)
"""

from openbp.solver.branch_and_price import (
    BranchAndPrice,
    BPConfig,
    BPSolution,
    BPStatus,
)

__all__ = [
    "BranchAndPrice",
    "BPConfig",
    "BPSolution",
    "BPStatus",
]
