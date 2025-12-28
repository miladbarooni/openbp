"""Tests for BPTree."""

import pytest

from openbp.core.tree import BPTree, TreeStats
from openbp.core.node import BPNode, NodeStatus, BranchingDecision


class TestTreeStats:
    """Tests for TreeStats."""

    def test_initial_stats(self):
        """Test initial statistics values."""
        stats = TreeStats()

        assert stats.nodes_created == 0
        assert stats.nodes_processed == 0
        assert stats.nodes_open == 0
        assert stats.max_depth == 0
        assert stats.best_lower_bound == float("-inf")
        assert stats.best_upper_bound == float("inf")

    def test_gap_calculation(self):
        """Test gap calculation."""
        stats = TreeStats()
        stats.best_lower_bound = 90.0
        stats.best_upper_bound = 100.0

        assert abs(stats.gap() - 0.1) < 1e-9

    def test_gap_infinite(self):
        """Test gap with infinite bounds."""
        stats = TreeStats()

        assert stats.gap() == float("inf")


class TestBPTree:
    """Tests for BPTree."""

    def test_tree_creation(self):
        """Test creating a tree."""
        tree = BPTree(minimize=True)

        assert tree.root() is not None
        assert tree.root_id == 0
        assert tree.num_nodes == 1
        assert tree.is_minimizing is True

    def test_tree_maximization(self):
        """Test creating a maximization tree."""
        tree = BPTree(minimize=False)

        assert tree.is_minimizing is False

    def test_root_node(self):
        """Test root node properties."""
        tree = BPTree()
        root = tree.root()

        assert root.id == 0
        assert root.parent_id == -1
        assert root.depth == 0
        assert root.can_be_explored is True

    def test_create_child(self):
        """Test creating a child node."""
        tree = BPTree()
        root = tree.root()

        decision = BranchingDecision.variable_branch(0, 1.0, True)
        child = tree.create_child(root, decision)

        assert child is not None
        assert child.id == 1
        assert child.parent_id == 0
        assert child.depth == 1
        assert len(child.local_decisions) == 1
        assert child.local_decisions[0].type == decision.type

        assert tree.num_nodes == 2
        assert root.has_children is True
        assert child.id in root.children

    def test_create_children(self):
        """Test creating multiple children."""
        tree = BPTree()
        root = tree.root()

        decisions = [
            BranchingDecision.variable_branch(0, 1.0, True),
            BranchingDecision.variable_branch(0, 2.0, False),
        ]
        children = tree.create_children(root, decisions)

        assert len(children) == 2
        assert children[0].id == 1
        assert children[1].id == 2
        assert tree.num_nodes == 3
        assert root.status == NodeStatus.BRANCHED

    def test_inherited_decisions(self):
        """Test that children inherit parent decisions."""
        tree = BPTree()
        root = tree.root()

        # First level
        d1 = BranchingDecision.variable_branch(0, 1.0, True)
        child1 = tree.create_child(root, d1)

        # Second level
        d2 = BranchingDecision.ryan_foster(1, 2, True)
        child2 = tree.create_child(child1, d2)

        assert len(child2.inherited_decisions) == 1
        assert len(child2.local_decisions) == 1
        assert child2.num_decisions == 2

    def test_node_lookup(self):
        """Test looking up nodes by ID."""
        tree = BPTree()
        root = tree.root()

        decision = BranchingDecision.variable_branch(0, 1.0, True)
        child = tree.create_child(root, decision)

        assert tree.node(0) is root
        assert tree.node(1) is child
        assert tree.node(999) is None

        assert tree.has_node(0) is True
        assert tree.has_node(1) is True
        assert tree.has_node(999) is False

    def test_bounds_management(self):
        """Test global bounds management."""
        tree = BPTree()

        tree.global_lower_bound = 50.0
        tree.global_upper_bound = 100.0

        assert tree.global_lower_bound == 50.0
        assert tree.global_upper_bound == 100.0
        assert abs(tree.gap() - 0.5) < 1e-9

    def test_update_bounds(self):
        """Test updating bounds from a node."""
        tree = BPTree()
        root = tree.root()

        root.lp_value = 80.0
        root.is_integer = True

        improved = tree.update_bounds(root)

        assert improved is True
        assert tree.global_upper_bound == 80.0

    def test_prune_by_bound(self):
        """Test pruning nodes by bound."""
        tree = BPTree()
        root = tree.root()

        decisions = [
            BranchingDecision.variable_branch(0, 1.0, True),
            BranchingDecision.variable_branch(0, 2.0, False),
        ]
        children = tree.create_children(root, decisions)

        # Set bounds
        children[0].lower_bound = 100.0
        children[1].lower_bound = 50.0
        tree.global_upper_bound = 75.0

        pruned = tree.prune_by_bound()

        assert pruned == 1
        assert children[0].status == NodeStatus.PRUNED_BOUND
        assert children[1].can_be_explored is True

    def test_get_open_nodes(self):
        """Test getting open nodes."""
        tree = BPTree()
        root = tree.root()

        decisions = [
            BranchingDecision.variable_branch(0, 1.0, True),
            BranchingDecision.variable_branch(0, 2.0, False),
        ]
        children = tree.create_children(root, decisions)

        open_nodes = tree.get_open_nodes()

        assert len(open_nodes) == 2
        assert children[0].id in open_nodes
        assert children[1].id in open_nodes
        assert root.id not in open_nodes  # Root is branched

    def test_mark_processed(self):
        """Test marking nodes as processed."""
        tree = BPTree()
        root = tree.root()

        assert tree.stats.nodes_processed == 0

        # Mark as INTEGER (nodes_branched is incremented by create_children, not mark_processed)
        tree.mark_processed(root, NodeStatus.INTEGER)

        assert root.status == NodeStatus.INTEGER
        assert tree.stats.nodes_processed == 1
        assert tree.stats.nodes_integer == 1

    def test_incumbent(self):
        """Test incumbent management."""
        tree = BPTree()
        root = tree.root()

        assert tree.incumbent() is None

        root.lp_value = 100.0
        root.is_integer = True
        tree.set_incumbent(root)

        assert tree.incumbent() is root
        assert tree.global_upper_bound == 100.0

    def test_path_to_root(self):
        """Test getting path from node to root."""
        tree = BPTree()
        root = tree.root()

        d1 = BranchingDecision.variable_branch(0, 1.0, True)
        child1 = tree.create_child(root, d1)

        d2 = BranchingDecision.variable_branch(1, 2.0, True)
        child2 = tree.create_child(child1, d2)

        path = tree.get_path_to_root(child2.id)

        assert path == [0, 1, 2]

    def test_is_complete(self):
        """Test checking if tree is complete."""
        tree = BPTree()
        root = tree.root()

        assert tree.is_complete is False

        tree.mark_processed(root, NodeStatus.INTEGER)

        assert tree.is_complete is True

    def test_statistics_tracking(self):
        """Test that statistics are tracked correctly."""
        tree = BPTree()
        root = tree.root()

        # Initial state
        assert tree.stats.nodes_created == 1
        assert tree.stats.nodes_open == 1

        # Create children
        decisions = [
            BranchingDecision.variable_branch(0, 1.0, True),
            BranchingDecision.variable_branch(0, 2.0, False),
        ]
        children = tree.create_children(root, decisions)

        assert tree.stats.nodes_created == 3
        assert tree.stats.nodes_branched == 1
        assert tree.stats.nodes_open == 2
        assert tree.stats.max_depth == 1

        # Prune one
        children[0].lower_bound = 100.0
        tree.global_upper_bound = 50.0
        tree.prune_by_bound()

        assert tree.stats.nodes_pruned_bound == 1
        assert tree.stats.nodes_open == 1
