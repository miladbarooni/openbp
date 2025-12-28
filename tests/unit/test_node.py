"""Tests for BPNode and BranchingDecision."""

import pytest
import math

# Use pure Python implementations for testing without C++ build
from openbp.core.node import (
    BPNode,
    NodeStatus,
    BranchType,
    BranchingDecision,
)


class TestBranchingDecision:
    """Tests for BranchingDecision."""

    def test_variable_branch_creation(self):
        """Test creating a variable branching decision."""
        d = BranchingDecision.variable_branch(5, 2.5, True)

        assert d.type == BranchType.VARIABLE
        assert d.variable_index == 5
        assert d.bound_value == 2.5
        assert d.is_upper_bound is True

    def test_variable_branch_lower(self):
        """Test lower bound variable branching."""
        d = BranchingDecision.variable_branch(3, 1.0, False)

        assert d.type == BranchType.VARIABLE
        assert d.variable_index == 3
        assert d.bound_value == 1.0
        assert d.is_upper_bound is False

    def test_ryan_foster_same(self):
        """Test Ryan-Foster same column decision."""
        d = BranchingDecision.ryan_foster(1, 5, True)

        assert d.type == BranchType.RYAN_FOSTER
        assert d.item_i == 1
        assert d.item_j == 5
        assert d.same_column is True

    def test_ryan_foster_different(self):
        """Test Ryan-Foster different column decision."""
        d = BranchingDecision.ryan_foster(2, 7, False)

        assert d.type == BranchType.RYAN_FOSTER
        assert d.item_i == 2
        assert d.item_j == 7
        assert d.same_column is False

    def test_arc_branch_required(self):
        """Test arc branching with required arc."""
        d = BranchingDecision.arc_branch(10, 0, True)

        assert d.type == BranchType.ARC
        assert d.arc_index == 10
        assert d.source_node == 0
        assert d.arc_required is True

    def test_arc_branch_forbidden(self):
        """Test arc branching with forbidden arc."""
        d = BranchingDecision.arc_branch(15, 2, False)

        assert d.type == BranchType.ARC
        assert d.arc_index == 15
        assert d.source_node == 2
        assert d.arc_required is False

    def test_resource_branch(self):
        """Test resource branching decision."""
        d = BranchingDecision.resource_branch(0, 5.0, 10.0)

        assert d.type == BranchType.RESOURCE
        assert d.resource_index == 0
        assert d.lower_bound == 5.0
        assert d.upper_bound == 10.0


class TestBPNode:
    """Tests for BPNode."""

    def test_root_node_creation(self):
        """Test creating a root node."""
        node = BPNode()

        assert node.id == 0
        assert node.parent_id == -1
        assert node.depth == 0
        assert node.lower_bound == float("-inf")
        assert node.upper_bound == float("inf")
        assert node.status == NodeStatus.PENDING
        assert node.is_integer is False

    def test_node_with_id(self):
        """Test creating a node with specific ID."""
        node = BPNode(id=5, parent_id=2, depth=3)

        assert node.id == 5
        assert node.parent_id == 2
        assert node.depth == 3

    def test_node_bounds(self):
        """Test setting and getting bounds."""
        node = BPNode()
        node.lower_bound = 50.0
        node.upper_bound = 100.0
        node.lp_value = 75.0

        assert node.lower_bound == 50.0
        assert node.upper_bound == 100.0
        assert node.lp_value == 75.0

    def test_node_gap(self):
        """Test gap calculation."""
        node = BPNode()
        node.lower_bound = 90.0
        node.upper_bound = 100.0

        assert abs(node.gap - 0.1) < 1e-9

    def test_node_gap_zero_upper(self):
        """Test gap with zero upper bound."""
        node = BPNode()
        node.lower_bound = 0.0
        node.upper_bound = 0.0

        assert node.gap == 0.0

    def test_node_gap_infinite(self):
        """Test gap with infinite bounds."""
        node = BPNode()

        assert node.gap == float("inf")

    def test_node_status_transitions(self):
        """Test node status properties."""
        node = BPNode()

        # Initially pending
        assert node.status == NodeStatus.PENDING
        assert node.can_be_explored is True
        assert node.is_processed is False
        assert node.is_pruned is False

        # Processing
        node.status = NodeStatus.PROCESSING
        assert node.can_be_explored is False
        assert node.is_processed is False
        assert node.is_pruned is False

        # Branched
        node.status = NodeStatus.BRANCHED
        assert node.can_be_explored is False
        assert node.is_processed is True
        assert node.is_pruned is False

        # Pruned by bound
        node.status = NodeStatus.PRUNED_BOUND
        assert node.can_be_explored is False
        assert node.is_processed is True
        assert node.is_pruned is True

    def test_branching_decisions(self):
        """Test adding and retrieving branching decisions."""
        node = BPNode()

        # Add local decisions
        d1 = BranchingDecision.variable_branch(0, 1.0, True)
        d2 = BranchingDecision.ryan_foster(1, 2, True)

        node.add_local_decision(d1)
        node.add_local_decision(d2)

        assert len(node.local_decisions) == 2
        assert node.num_decisions == 2

    def test_inherited_decisions(self):
        """Test inherited decisions."""
        node = BPNode()

        inherited = [
            BranchingDecision.variable_branch(0, 1.0, True),
            BranchingDecision.variable_branch(1, 2.0, False),
        ]
        node.set_inherited_decisions(inherited)

        local = BranchingDecision.ryan_foster(3, 4, True)
        node.add_local_decision(local)

        assert len(node.inherited_decisions) == 2
        assert len(node.local_decisions) == 1
        assert node.num_decisions == 3

        all_decisions = node.all_decisions()
        assert len(all_decisions) == 3

    def test_prune_by_bound(self):
        """Test pruning by bound."""
        node = BPNode()
        node.lower_bound = 100.0

        # Should not prune when lower bound < global upper
        assert node.try_prune_by_bound(150.0) is False
        assert node.status == NodeStatus.PENDING

        # Should prune when lower bound >= global upper
        assert node.try_prune_by_bound(100.0) is True
        assert node.status == NodeStatus.PRUNED_BOUND

    def test_solution_storage(self):
        """Test storing and retrieving solutions."""
        node = BPNode()

        assert node.has_solution is False

        node.set_solution([0.0, 1.0, 1.0, 0.0])
        assert node.has_solution is True
        assert len(node.solution) == 4

        node.set_solution_columns([1, 2])
        assert len(node.solution_columns) == 2

    def test_children(self):
        """Test child node management."""
        node = BPNode()

        assert node.has_children is False
        assert len(node.children) == 0

        node.add_child(1)
        node.add_child(2)

        assert node.has_children is True
        assert len(node.children) == 2
        assert 1 in node.children
        assert 2 in node.children
