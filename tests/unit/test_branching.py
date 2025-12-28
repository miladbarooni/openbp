"""Tests for branching strategies."""

import pytest
from dataclasses import dataclass
from typing import FrozenSet, Tuple

from openbp.branching.base import BranchingStrategy, BranchingCandidate
from openbp.branching.variable import VariableBranching
from openbp.branching.ryan_foster import RyanFosterBranching
from openbp.branching.arc import ArcBranching
from openbp.core.node import BPNode

# Import BranchType and BranchingDecision from the same source as branching strategies
# This ensures enum values match
try:
    from openbp._core import BranchType, BranchingDecision
except ImportError:
    from openbp.core.node import BranchType, BranchingDecision


# Mock Column class for testing
@dataclass(frozen=True)
class MockColumn:
    """Mock column for testing branching strategies."""
    arc_indices: Tuple[int, ...]
    cost: float
    covered_items: FrozenSet[int]
    value: float = 0.0
    source_node: int = 0


class TestVariableBranching:
    """Tests for VariableBranching."""

    def test_find_fractional_variables(self):
        """Test finding fractional variables."""
        strategy = VariableBranching()
        node = BPNode()

        columns = [
            MockColumn(arc_indices=(1,), cost=10.0, covered_items=frozenset({1})),
            MockColumn(arc_indices=(2,), cost=20.0, covered_items=frozenset({2})),
            MockColumn(arc_indices=(3,), cost=30.0, covered_items=frozenset({3})),
        ]
        column_values = [0.5, 1.0, 0.3]  # First and third are fractional

        candidates = strategy.select_branching_candidates(
            node, columns, column_values, {}
        )

        assert len(candidates) == 2

        # Check that candidates have correct structure
        for c in candidates:
            assert len(c.decisions) == 2
            assert c.decisions[0].type == BranchType.VARIABLE
            assert c.decisions[1].type == BranchType.VARIABLE

    def test_prefer_balanced_fractionality(self):
        """Test that balanced fractionality is preferred."""
        strategy = VariableBranching(prefer_balanced=True)
        node = BPNode()

        columns = [
            MockColumn(arc_indices=(1,), cost=10.0, covered_items=frozenset({1})),
            MockColumn(arc_indices=(2,), cost=20.0, covered_items=frozenset({2})),
        ]
        column_values = [0.5, 0.1]  # 0.5 should score higher

        candidates = strategy.select_branching_candidates(
            node, columns, column_values, {}
        )

        # First candidate should have higher score (0.5 fractionality)
        assert candidates[0].metadata["value"] == 0.5

    def test_skip_integer_values(self):
        """Test that integer values are skipped."""
        strategy = VariableBranching()
        node = BPNode()

        columns = [
            MockColumn(arc_indices=(1,), cost=10.0, covered_items=frozenset({1})),
            MockColumn(arc_indices=(2,), cost=20.0, covered_items=frozenset({2})),
        ]
        column_values = [1.0, 2.0]  # Both integer

        candidates = strategy.select_branching_candidates(
            node, columns, column_values, {}
        )

        assert len(candidates) == 0

    def test_branching_decisions(self):
        """Test that branching decisions are correct."""
        strategy = VariableBranching()
        node = BPNode()

        columns = [
            MockColumn(arc_indices=(1,), cost=10.0, covered_items=frozenset({1})),
        ]
        column_values = [2.7]  # floor=2, ceil=3

        candidates = strategy.select_branching_candidates(
            node, columns, column_values, {}
        )

        assert len(candidates) == 1
        c = candidates[0]

        # Left: x[0] <= 2
        assert c.decisions[0].is_upper_bound is True
        assert c.decisions[0].bound_value == 2

        # Right: x[0] >= 3
        assert c.decisions[1].is_upper_bound is False
        assert c.decisions[1].bound_value == 3


class TestRyanFosterBranching:
    """Tests for RyanFosterBranching."""

    def test_find_fractional_pairs(self):
        """Test finding pairs with fractional overlap."""
        strategy = RyanFosterBranching()
        node = BPNode()

        # Items 1,2 together in col1, items 1,3 together in col2
        columns = [
            MockColumn(arc_indices=(1,), cost=10.0, covered_items=frozenset({1, 2})),
            MockColumn(arc_indices=(2,), cost=20.0, covered_items=frozenset({1, 3})),
        ]
        column_values = [0.5, 0.5]

        candidates = strategy.select_branching_candidates(
            node, columns, column_values, {}
        )

        # Should find pairs with fractional overlap
        assert len(candidates) > 0

        # Each candidate should have same/different decisions
        for c in candidates:
            assert len(c.decisions) == 2
            assert c.decisions[0].type == BranchType.RYAN_FOSTER
            assert c.decisions[0].same_column is True  # Same branch
            assert c.decisions[1].same_column is False  # Different branch

    def test_filter_columns_same(self):
        """Test filtering columns for same-column decision."""
        strategy = RyanFosterBranching()

        columns = [
            MockColumn(arc_indices=(1,), cost=10.0, covered_items=frozenset({1, 2})),
            MockColumn(arc_indices=(2,), cost=20.0, covered_items=frozenset({1})),
            MockColumn(arc_indices=(3,), cost=30.0, covered_items=frozenset({2})),
            MockColumn(arc_indices=(4,), cost=40.0, covered_items=frozenset({3})),
        ]

        # Items 1,2 must be together
        decision = BranchingDecision.ryan_foster(1, 2, True)

        filtered = strategy.filter_columns(columns, [decision])

        # Should keep: col1 (both), col4 (neither)
        # Should remove: col2 (only 1), col3 (only 2)
        assert len(filtered) == 2

    def test_filter_columns_different(self):
        """Test filtering columns for different-column decision."""
        strategy = RyanFosterBranching()

        columns = [
            MockColumn(arc_indices=(1,), cost=10.0, covered_items=frozenset({1, 2})),
            MockColumn(arc_indices=(2,), cost=20.0, covered_items=frozenset({1})),
            MockColumn(arc_indices=(3,), cost=30.0, covered_items=frozenset({2})),
            MockColumn(arc_indices=(4,), cost=40.0, covered_items=frozenset({3})),
        ]

        # Items 1,2 must be different
        decision = BranchingDecision.ryan_foster(1, 2, False)

        filtered = strategy.filter_columns(columns, [decision])

        # Should keep: col2 (only 1), col3 (only 2), col4 (neither)
        # Should remove: col1 (both)
        assert len(filtered) == 3

    def test_is_applicable(self):
        """Test applicability check."""
        strategy = RyanFosterBranching()
        node = BPNode()

        # With covered items
        columns = [
            MockColumn(arc_indices=(1,), cost=10.0, covered_items=frozenset({1, 2})),
        ]
        assert strategy.is_applicable(node, columns, [1.0]) is True

        # Empty columns
        assert strategy.is_applicable(node, [], []) is False


class TestArcBranching:
    """Tests for ArcBranching."""

    def test_find_fractional_arcs(self):
        """Test finding arcs with fractional usage."""
        strategy = ArcBranching()
        node = BPNode()

        columns = [
            MockColumn(arc_indices=(1, 2, 3), cost=10.0, covered_items=frozenset({1})),
            MockColumn(arc_indices=(1, 4, 5), cost=20.0, covered_items=frozenset({2})),
        ]
        column_values = [0.5, 0.5]  # Arc 1 has usage 1.0, arcs 2-5 have usage 0.5

        candidates = strategy.select_branching_candidates(
            node, columns, column_values, {}
        )

        # Should find arcs with fractional usage
        assert len(candidates) > 0

        # Each candidate should have required/forbidden decisions
        for c in candidates:
            assert len(c.decisions) == 2
            assert c.decisions[0].type == BranchType.ARC
            assert c.decisions[0].arc_required is False  # Forbidden first
            assert c.decisions[1].arc_required is True  # Required second

    def test_filter_columns_required(self):
        """Test filtering columns for required arc."""
        strategy = ArcBranching()

        columns = [
            MockColumn(arc_indices=(1, 2, 3), cost=10.0, covered_items=frozenset({1})),
            MockColumn(arc_indices=(4, 5, 6), cost=20.0, covered_items=frozenset({2})),
        ]

        # Arc 2 must be used
        decision = BranchingDecision.arc_branch(2, 0, True)

        filtered = strategy.filter_columns(columns, [decision])

        # Should keep only col1 (has arc 2)
        assert len(filtered) == 1
        assert 2 in filtered[0].arc_indices

    def test_filter_columns_forbidden(self):
        """Test filtering columns for forbidden arc."""
        strategy = ArcBranching()

        columns = [
            MockColumn(arc_indices=(1, 2, 3), cost=10.0, covered_items=frozenset({1})),
            MockColumn(arc_indices=(4, 5, 6), cost=20.0, covered_items=frozenset({2})),
        ]

        # Arc 2 is forbidden
        decision = BranchingDecision.arc_branch(2, 0, False)

        filtered = strategy.filter_columns(columns, [decision])

        # Should keep only col2 (doesn't have arc 2)
        assert len(filtered) == 1
        assert 2 not in filtered[0].arc_indices


class TestBranchingCandidate:
    """Tests for BranchingCandidate."""

    def test_candidate_comparison(self):
        """Test candidate comparison by score."""
        c1 = BranchingCandidate(score=0.5, decisions=[], description="c1")
        c2 = BranchingCandidate(score=0.8, decisions=[], description="c2")

        # Higher score should be "greater"
        assert c1 < c2
        assert not c2 < c1

        # Max should return higher score
        assert max([c1, c2]).description == "c2"

    def test_candidate_metadata(self):
        """Test candidate metadata."""
        c = BranchingCandidate(
            score=0.5,
            decisions=[],
            description="test",
            metadata={"key": "value", "count": 42},
        )

        assert c.metadata["key"] == "value"
        assert c.metadata["count"] == 42
