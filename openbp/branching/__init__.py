"""
Branching strategies for branch-and-price.

This module provides abstract base classes and concrete implementations
of branching strategies used in the B&P algorithm.

Available Strategies:
--------------------
- VariableBranching: Standard variable branching on fractional LP values
- RyanFosterBranching: Ryan-Foster branching for set partitioning
- ArcBranching: Arc-based branching for VRP/crew scheduling
- StrongBranching: Variable selection via LP evaluations

Extension Points:
----------------
Users can implement custom branching by subclassing BranchingStrategy
and implementing the select_branching_candidates() method.
"""

from openbp.branching.arc import ArcBranching
from openbp.branching.base import (
    BranchingCandidate,
    BranchingStrategy,
)
from openbp.branching.ryan_foster import RyanFosterBranching
from openbp.branching.strong import StrongBranching
from openbp.branching.variable import VariableBranching

__all__ = [
    "BranchingStrategy",
    "BranchingCandidate",
    "VariableBranching",
    "RyanFosterBranching",
    "ArcBranching",
    "StrongBranching",
]
