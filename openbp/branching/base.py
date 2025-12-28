"""
Abstract base classes for branching strategies.

This module defines the interface that all branching strategies must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from openbp._core import BPNode, BranchingDecision
    from opencg import Column


@dataclass
class BranchingCandidate:
    """
    A candidate for branching.

    Represents a potential branching choice with associated score
    and the decisions that would result from branching.

    Attributes:
        score: Priority score (higher = more likely to be selected)
        decisions: List of branching decisions (one per child)
        description: Human-readable description of the branching
        metadata: Additional strategy-specific information
    """
    score: float
    decisions: List["BranchingDecision"]
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: "BranchingCandidate") -> bool:
        """Higher score = higher priority."""
        return self.score < other.score


class BranchingStrategy(ABC):
    """
    Abstract base class for branching strategies.

    A branching strategy determines how to split a B&P node into
    children. It analyzes the LP solution and selects branching
    decisions that:
    1. Exclude the current fractional solution
    2. Partition the solution space
    3. Ideally improve bounds quickly

    Subclasses must implement:
    - select_branching_candidates(): Find branching opportunities

    Subclasses may override:
    - filter_columns(): Remove columns violating branching decisions
    - is_applicable(): Check if strategy can be applied
    - configure(): Set strategy-specific parameters
    """

    def __init__(self, name: str = ""):
        """
        Initialize the branching strategy.

        Args:
            name: Human-readable name for logging
        """
        self.name = name or self.__class__.__name__

    @abstractmethod
    def select_branching_candidates(
        self,
        node: "BPNode",
        columns: List["Column"],
        column_values: List[float],
        duals: Dict[int, float],
    ) -> List[BranchingCandidate]:
        """
        Find branching candidates for a node.

        This is the main extension point for custom branching strategies.
        Analyze the LP solution and return a list of possible branching
        choices, ordered by priority (highest score first).

        Args:
            node: The B&P node to branch on
            columns: List of columns in the current LP solution
            column_values: LP solution values for each column
            duals: Dual values indexed by constraint index

        Returns:
            List of branching candidates, sorted by score (descending)
        """
        pass

    def select_best_candidate(
        self,
        node: "BPNode",
        columns: List["Column"],
        column_values: List[float],
        duals: Dict[int, float],
    ) -> Optional[BranchingCandidate]:
        """
        Select the best branching candidate.

        Convenience method that returns the highest-scored candidate.

        Args:
            node: The B&P node to branch on
            columns: List of columns in the current LP solution
            column_values: LP solution values for each column
            duals: Dual values indexed by constraint index

        Returns:
            The best candidate, or None if no valid candidates exist
        """
        candidates = self.select_branching_candidates(
            node, columns, column_values, duals
        )
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.score)

    def filter_columns(
        self,
        columns: List["Column"],
        decisions: List["BranchingDecision"],
    ) -> List["Column"]:
        """
        Filter columns that violate branching decisions.

        Called when creating child nodes to determine which columns
        from the parent's pool are still valid.

        Default implementation returns all columns (no filtering).
        Subclasses should override for their specific decision types.

        Args:
            columns: Columns to filter
            decisions: Active branching decisions

        Returns:
            Columns that satisfy all decisions
        """
        return columns

    def is_applicable(
        self,
        node: "BPNode",
        columns: List["Column"],
        column_values: List[float],
    ) -> bool:
        """
        Check if this strategy can be applied to a node.

        Override to add preconditions for the strategy.

        Args:
            node: The node to check
            columns: Current columns
            column_values: Current LP solution

        Returns:
            True if strategy can be applied
        """
        return True

    def configure(self, **kwargs: Any) -> None:
        """
        Configure strategy-specific parameters.

        Override to accept custom configuration options.

        Args:
            **kwargs: Strategy-specific parameters
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"


class CompositeBranchingStrategy(BranchingStrategy):
    """
    Combine multiple branching strategies with fallback.

    Tries each strategy in order until one returns valid candidates.
    Useful for combining specialized strategies (e.g., Ryan-Foster)
    with generic fallbacks (e.g., variable branching).
    """

    def __init__(self, strategies: List[BranchingStrategy]):
        """
        Initialize with a list of strategies.

        Args:
            strategies: Strategies to try, in priority order
        """
        super().__init__("Composite")
        self.strategies = strategies

    def select_branching_candidates(
        self,
        node: "BPNode",
        columns: List["Column"],
        column_values: List[float],
        duals: Dict[int, float],
    ) -> List[BranchingCandidate]:
        """Try each strategy until one succeeds."""
        for strategy in self.strategies:
            if not strategy.is_applicable(node, columns, column_values):
                continue

            candidates = strategy.select_branching_candidates(
                node, columns, column_values, duals
            )
            if candidates:
                return candidates

        return []

    def filter_columns(
        self,
        columns: List["Column"],
        decisions: List["BranchingDecision"],
    ) -> List["Column"]:
        """Apply all strategies' filters."""
        result = columns
        for strategy in self.strategies:
            result = strategy.filter_columns(result, decisions)
        return result

    def __repr__(self) -> str:
        strategy_names = ", ".join(s.name for s in self.strategies)
        return f"<CompositeBranchingStrategy [{strategy_names}]>"
