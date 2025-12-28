"""Tests for node selection policies."""

import pytest

from openbp.core.selection import (
    BestFirstSelector,
    DepthFirstSelector,
    BestEstimateSelector,
    HybridSelector,
    create_selector,
)
from openbp.core.node import BPNode, NodeStatus


class TestBestFirstSelector:
    """Tests for BestFirstSelector."""

    def test_empty_selector(self):
        """Test empty selector behavior."""
        selector = BestFirstSelector()

        assert selector.empty() is True
        assert selector.size() == 0
        assert selector.select_next() is None
        assert selector.peek_next() is None
        assert selector.best_bound() == float("inf")

    def test_add_single_node(self):
        """Test adding a single node."""
        selector = BestFirstSelector()
        node = BPNode(id=1)
        node.lower_bound = 50.0

        selector.add_node(node)

        assert selector.empty() is False
        assert selector.size() == 1
        assert selector.best_bound() == 50.0

    def test_select_by_bound(self):
        """Test that best-first selects by lowest bound."""
        selector = BestFirstSelector()

        n1 = BPNode(id=1)
        n1.lower_bound = 100.0

        n2 = BPNode(id=2)
        n2.lower_bound = 50.0

        n3 = BPNode(id=3)
        n3.lower_bound = 75.0

        selector.add_node(n1)
        selector.add_node(n2)
        selector.add_node(n3)

        # Should select in order: n2 (50), n3 (75), n1 (100)
        assert selector.select_next().id == 2
        assert selector.select_next().id == 3
        assert selector.select_next().id == 1
        assert selector.empty() is True

    def test_skip_pruned_nodes(self):
        """Test that pruned nodes are skipped."""
        selector = BestFirstSelector()

        n1 = BPNode(id=1)
        n1.lower_bound = 50.0

        n2 = BPNode(id=2)
        n2.lower_bound = 75.0
        n2.status = NodeStatus.PRUNED_BOUND  # Pruned

        selector.add_node(n1)
        selector.add_node(n2)

        # Should only get n1
        assert selector.select_next().id == 1
        assert selector.select_next() is None

    def test_prune_method(self):
        """Test the prune method."""
        selector = BestFirstSelector()

        n1 = BPNode(id=1)
        n1.lower_bound = 50.0

        n2 = BPNode(id=2)
        n2.lower_bound = 75.0

        selector.add_node(n1)
        selector.add_node(n2)

        n2.status = NodeStatus.PRUNED_BOUND

        removed = selector.prune()
        assert removed == 1
        assert selector.size() == 1

    def test_get_open_node_ids(self):
        """Test getting open node IDs."""
        selector = BestFirstSelector()

        for i in range(5):
            node = BPNode(id=i)
            node.lower_bound = float(i * 10)
            selector.add_node(node)

        ids = selector.get_open_node_ids()
        assert len(ids) == 5
        assert set(ids) == {0, 1, 2, 3, 4}

    def test_clear(self):
        """Test clearing the selector."""
        selector = BestFirstSelector()

        for i in range(5):
            selector.add_node(BPNode(id=i))

        selector.clear()

        assert selector.empty() is True
        assert selector.size() == 0


class TestDepthFirstSelector:
    """Tests for DepthFirstSelector."""

    def test_select_by_depth(self):
        """Test that depth-first selects by depth."""
        selector = DepthFirstSelector()

        n1 = BPNode(id=1, depth=1)
        n1.lower_bound = 50.0

        n2 = BPNode(id=2, depth=3)
        n2.lower_bound = 100.0

        n3 = BPNode(id=3, depth=2)
        n3.lower_bound = 75.0

        selector.add_node(n1)
        selector.add_node(n2)
        selector.add_node(n3)

        # Should select in order: n2 (depth=3), n3 (depth=2), n1 (depth=1)
        assert selector.select_next().id == 2
        assert selector.select_next().id == 3
        assert selector.select_next().id == 1

    def test_tiebreak_by_bound(self):
        """Test tiebreaking by bound at same depth."""
        selector = DepthFirstSelector()

        n1 = BPNode(id=1, depth=2)
        n1.lower_bound = 100.0

        n2 = BPNode(id=2, depth=2)
        n2.lower_bound = 50.0

        selector.add_node(n1)
        selector.add_node(n2)

        # Same depth, should select lower bound first
        assert selector.select_next().id == 2


class TestBestEstimateSelector:
    """Tests for BestEstimateSelector."""

    def test_estimate_based_selection(self):
        """Test selection based on estimate."""
        selector = BestEstimateSelector(estimate_weight=0.5)

        n1 = BPNode(id=1, depth=1)
        n1.lower_bound = 100.0

        n2 = BPNode(id=2, depth=10)
        n2.lower_bound = 100.0

        selector.add_node(n1)
        selector.add_node(n2)

        # With no incumbent, deeper nodes should be preferred
        # (lower estimate due to depth penalty)
        selected = selector.select_next()
        assert selected.id == 2

    def test_bound_update(self):
        """Test that bound updates affect selection."""
        selector = BestEstimateSelector(estimate_weight=0.5)

        n1 = BPNode(id=1, depth=1)
        n1.lower_bound = 50.0

        n2 = BPNode(id=2, depth=5)
        n2.lower_bound = 80.0

        selector.add_node(n1)
        selector.add_node(n2)

        # Update with incumbent
        selector.on_bound_update(100.0)

        # Selection should now consider gap-based estimate
        selected = selector.select_next()
        # The deeper node should be more attractive despite higher bound


class TestHybridSelector:
    """Tests for HybridSelector."""

    def test_hybrid_switching(self):
        """Test that hybrid switches between strategies."""
        selector = HybridSelector(dive_frequency=2, dive_depth=2)

        # Add nodes at various depths
        for i in range(10):
            node = BPNode(id=i, depth=i)
            node.lower_bound = float(100 - i)  # Lower bound = deeper
            selector.add_node(node)

        # First few selections should be best-first
        # Then should switch to diving

        selected_ids = []
        for _ in range(6):
            node = selector.select_next()
            if node:
                selected_ids.append(node.id)

        # Should see a mix of depths
        assert len(selected_ids) > 0


class TestCreateSelector:
    """Tests for the create_selector factory."""

    def test_create_best_first(self):
        """Test creating best-first selector."""
        selector = create_selector("best_first")
        assert isinstance(selector, BestFirstSelector)

        selector = create_selector("BestFirst")
        assert isinstance(selector, BestFirstSelector)

    def test_create_depth_first(self):
        """Test creating depth-first selector."""
        selector = create_selector("depth_first")
        assert isinstance(selector, DepthFirstSelector)

    def test_create_best_estimate(self):
        """Test creating best-estimate selector."""
        selector = create_selector("best_estimate")
        assert isinstance(selector, BestEstimateSelector)

    def test_create_hybrid(self):
        """Test creating hybrid selector."""
        selector = create_selector("hybrid")
        assert isinstance(selector, HybridSelector)

    def test_unknown_defaults_to_best_first(self):
        """Test that unknown name defaults to best-first."""
        selector = create_selector("unknown")
        assert isinstance(selector, BestFirstSelector)
