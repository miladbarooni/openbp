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

from openbp.branching.base import (
    BranchingStrategy,
    BranchingCandidate,
)
from openbp.branching.variable import VariableBranching
from openbp.branching.ryan_foster import RyanFosterBranching
from openbp.branching.arc import ArcBranching
from openbp.branching.strong import StrongBranching

__all__ = [
    "BranchingStrategy",
    "BranchingCandidate",
    "VariableBranching",
    "RyanFosterBranching",
    "ArcBranching",
    "StrongBranching",
]
