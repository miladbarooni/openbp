/**
 * @file test_node.cpp
 * @brief Tests for BPNode and BranchingDecision.
 */

#include "core/node.hpp"
#include <cassert>
#include <iostream>
#include <cmath>

using namespace openbp;

void test_branching_decision() {
    std::cout << "Testing BranchingDecision..." << std::endl;

    // Variable branching
    auto d1 = BranchingDecision::variable_branch(5, 2.5, true);
    assert(d1.type == BranchType::VARIABLE);
    assert(d1.variable_index == 5);
    assert(std::abs(d1.bound_value - 2.5) < 1e-9);
    assert(d1.is_upper_bound == true);

    // Ryan-Foster
    auto d2 = BranchingDecision::ryan_foster(1, 5, true);
    assert(d2.type == BranchType::RYAN_FOSTER);
    assert(d2.item_i == 1);
    assert(d2.item_j == 5);
    assert(d2.same_column == true);

    // Arc branching
    auto d3 = BranchingDecision::arc_branch(10, 0, true);
    assert(d3.type == BranchType::ARC);
    assert(d3.arc_index == 10);
    assert(d3.source_node == 0);
    assert(d3.arc_required == true);

    // Resource branching
    auto d4 = BranchingDecision::resource_branch(0, 5.0, 10.0);
    assert(d4.type == BranchType::RESOURCE);
    assert(d4.resource_index == 0);
    assert(std::abs(d4.lower_bound - 5.0) < 1e-9);
    assert(std::abs(d4.upper_bound - 10.0) < 1e-9);

    std::cout << "  PASSED" << std::endl;
}

void test_node_creation() {
    std::cout << "Testing BPNode creation..." << std::endl;

    // Root node
    BPNode root;
    assert(root.id() == 0);
    assert(root.parent_id() == BPNode::INVALID_ID);
    assert(root.depth() == 0);
    assert(root.status() == NodeStatus::PENDING);
    assert(root.is_integer() == false);
    assert(root.can_be_explored() == true);

    // Child node
    auto decision = BranchingDecision::variable_branch(0, 1.0, true);
    BPNode child(1, 0, 1, decision);
    assert(child.id() == 1);
    assert(child.parent_id() == 0);
    assert(child.depth() == 1);
    assert(child.local_decisions().size() == 1);

    std::cout << "  PASSED" << std::endl;
}

void test_node_bounds() {
    std::cout << "Testing BPNode bounds..." << std::endl;

    BPNode node;
    node.set_lower_bound(90.0);
    node.set_upper_bound(100.0);

    assert(std::abs(node.lower_bound() - 90.0) < 1e-9);
    assert(std::abs(node.upper_bound() - 100.0) < 1e-9);
    assert(std::abs(node.gap() - 0.1) < 1e-9);

    std::cout << "  PASSED" << std::endl;
}

void test_node_status() {
    std::cout << "Testing BPNode status..." << std::endl;

    BPNode node;

    // Pending
    assert(node.status() == NodeStatus::PENDING);
    assert(node.can_be_explored() == true);
    assert(node.is_processed() == false);
    assert(node.is_pruned() == false);

    // Pruned
    node.set_status(NodeStatus::PRUNED_BOUND);
    assert(node.can_be_explored() == false);
    assert(node.is_processed() == true);
    assert(node.is_pruned() == true);

    std::cout << "  PASSED" << std::endl;
}

void test_prune_by_bound() {
    std::cout << "Testing BPNode::try_prune_by_bound..." << std::endl;

    BPNode node;
    node.set_lower_bound(100.0);

    // Should not prune
    assert(node.try_prune_by_bound(150.0) == false);
    assert(node.status() == NodeStatus::PENDING);

    // Should prune
    assert(node.try_prune_by_bound(100.0) == true);
    assert(node.status() == NodeStatus::PRUNED_BOUND);

    std::cout << "  PASSED" << std::endl;
}

void test_branching_decisions() {
    std::cout << "Testing BPNode branching decisions..." << std::endl;

    BPNode node;

    // Add local decisions
    node.add_local_decision(BranchingDecision::variable_branch(0, 1.0, true));
    node.add_local_decision(BranchingDecision::ryan_foster(1, 2, true));

    assert(node.local_decisions().size() == 2);
    assert(node.num_decisions() == 2);

    // Set inherited decisions
    std::vector<BranchingDecision> inherited;
    inherited.push_back(BranchingDecision::variable_branch(3, 2.0, false));
    node.set_inherited_decisions(std::move(inherited));

    assert(node.inherited_decisions().size() == 1);
    assert(node.num_decisions() == 3);

    auto all = node.all_decisions();
    assert(all.size() == 3);

    std::cout << "  PASSED" << std::endl;
}

void test_solution_storage() {
    std::cout << "Testing BPNode solution storage..." << std::endl;

    BPNode node;
    assert(node.has_solution() == false);

    std::vector<double> sol = {0.0, 1.0, 1.0, 0.0};
    node.set_solution(std::move(sol));

    assert(node.has_solution() == true);
    assert(node.solution().size() == 4);

    std::cout << "  PASSED" << std::endl;
}

int main() {
    std::cout << "=== BPNode Tests ===" << std::endl;

    test_branching_decision();
    test_node_creation();
    test_node_bounds();
    test_node_status();
    test_prune_by_bound();
    test_branching_decisions();
    test_solution_storage();

    std::cout << "\nAll tests passed!" << std::endl;
    return 0;
}
