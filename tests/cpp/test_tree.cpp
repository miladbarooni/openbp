/**
 * @file test_tree.cpp
 * @brief Tests for BPTree.
 */

#include "core/tree.hpp"
#include <cassert>
#include <iostream>
#include <cmath>

using namespace openbp;

void test_tree_creation() {
    std::cout << "Testing BPTree creation..." << std::endl;

    BPTree tree(true);  // Minimization

    assert(tree.root() != nullptr);
    assert(tree.root_id() == 0);
    assert(tree.num_nodes() == 1);
    assert(tree.is_minimizing() == true);

    std::cout << "  PASSED" << std::endl;
}

void test_create_child() {
    std::cout << "Testing BPTree::create_child..." << std::endl;

    BPTree tree;
    auto* root = tree.root();

    auto decision = BranchingDecision::variable_branch(0, 1.0, true);
    auto* child = tree.create_child(root, decision);

    assert(child != nullptr);
    assert(child->id() == 1);
    assert(child->parent_id() == 0);
    assert(child->depth() == 1);
    assert(tree.num_nodes() == 2);
    assert(root->has_children() == true);

    std::cout << "  PASSED" << std::endl;
}

void test_create_children() {
    std::cout << "Testing BPTree::create_children..." << std::endl;

    BPTree tree;
    auto* root = tree.root();

    std::vector<BranchingDecision> decisions = {
        BranchingDecision::variable_branch(0, 1.0, true),
        BranchingDecision::variable_branch(0, 2.0, false),
    };

    auto children = tree.create_children(root, decisions);

    assert(children.size() == 2);
    assert(tree.num_nodes() == 3);
    assert(root->status() == NodeStatus::BRANCHED);

    std::cout << "  PASSED" << std::endl;
}

void test_inherited_decisions() {
    std::cout << "Testing inherited decisions..." << std::endl;

    BPTree tree;
    auto* root = tree.root();

    // First level
    auto d1 = BranchingDecision::variable_branch(0, 1.0, true);
    auto* child1 = tree.create_child(root, d1);

    // Second level
    auto d2 = BranchingDecision::ryan_foster(1, 2, true);
    auto* child2 = tree.create_child(child1, d2);

    assert(child2->inherited_decisions().size() == 1);
    assert(child2->local_decisions().size() == 1);
    assert(child2->num_decisions() == 2);

    std::cout << "  PASSED" << std::endl;
}

void test_node_lookup() {
    std::cout << "Testing node lookup..." << std::endl;

    BPTree tree;
    auto* root = tree.root();

    auto decision = BranchingDecision::variable_branch(0, 1.0, true);
    auto* child = tree.create_child(root, decision);

    assert(tree.node(0) == root);
    assert(tree.node(1) == child);
    assert(tree.node(999) == nullptr);

    assert(tree.has_node(0) == true);
    assert(tree.has_node(1) == true);
    assert(tree.has_node(999) == false);

    std::cout << "  PASSED" << std::endl;
}

void test_bounds() {
    std::cout << "Testing bounds management..." << std::endl;

    BPTree tree;

    tree.set_global_lower_bound(50.0);
    tree.set_global_upper_bound(100.0);

    assert(std::abs(tree.global_lower_bound() - 50.0) < 1e-9);
    assert(std::abs(tree.global_upper_bound() - 100.0) < 1e-9);
    assert(std::abs(tree.gap() - 0.5) < 1e-9);

    std::cout << "  PASSED" << std::endl;
}

void test_prune_by_bound() {
    std::cout << "Testing prune_by_bound..." << std::endl;

    BPTree tree;
    auto* root = tree.root();

    std::vector<BranchingDecision> decisions = {
        BranchingDecision::variable_branch(0, 1.0, true),
        BranchingDecision::variable_branch(0, 2.0, false),
    };

    auto children = tree.create_children(root, decisions);

    children[0]->set_lower_bound(100.0);
    children[1]->set_lower_bound(50.0);
    tree.set_global_upper_bound(75.0);

    int64_t pruned = tree.prune_by_bound();

    assert(pruned == 1);
    assert(children[0]->status() == NodeStatus::PRUNED_BOUND);
    assert(children[1]->can_be_explored() == true);

    std::cout << "  PASSED" << std::endl;
}

void test_get_open_nodes() {
    std::cout << "Testing get_open_nodes..." << std::endl;

    BPTree tree;
    auto* root = tree.root();

    std::vector<BranchingDecision> decisions = {
        BranchingDecision::variable_branch(0, 1.0, true),
        BranchingDecision::variable_branch(0, 2.0, false),
    };

    auto children = tree.create_children(root, decisions);

    auto open_nodes = tree.get_open_nodes();

    assert(open_nodes.size() == 2);
    // Root is branched, so not in open nodes

    std::cout << "  PASSED" << std::endl;
}

void test_incumbent() {
    std::cout << "Testing incumbent management..." << std::endl;

    BPTree tree;
    auto* root = tree.root();

    assert(tree.incumbent() == nullptr);

    root->set_lp_value(100.0);
    root->set_is_integer(true);
    tree.set_incumbent(root);

    assert(tree.incumbent() == root);
    assert(std::abs(tree.global_upper_bound() - 100.0) < 1e-9);

    std::cout << "  PASSED" << std::endl;
}

void test_path_to_root() {
    std::cout << "Testing get_path_to_root..." << std::endl;

    BPTree tree;
    auto* root = tree.root();

    auto d1 = BranchingDecision::variable_branch(0, 1.0, true);
    auto* child1 = tree.create_child(root, d1);

    auto d2 = BranchingDecision::variable_branch(1, 2.0, true);
    auto* child2 = tree.create_child(child1, d2);

    auto path = tree.get_path_to_root(child2->id());

    assert(path.size() == 3);
    assert(path[0] == 0);  // root
    assert(path[1] == 1);  // child1
    assert(path[2] == 2);  // child2

    std::cout << "  PASSED" << std::endl;
}

void test_statistics() {
    std::cout << "Testing statistics tracking..." << std::endl;

    BPTree tree;
    auto* root = tree.root();

    assert(tree.stats().nodes_created == 1);
    assert(tree.stats().nodes_open == 1);

    std::vector<BranchingDecision> decisions = {
        BranchingDecision::variable_branch(0, 1.0, true),
        BranchingDecision::variable_branch(0, 2.0, false),
    };

    tree.create_children(root, decisions);

    assert(tree.stats().nodes_created == 3);
    assert(tree.stats().nodes_branched == 1);
    assert(tree.stats().nodes_open == 2);
    assert(tree.stats().max_depth == 1);

    std::cout << "  PASSED" << std::endl;
}

int main() {
    std::cout << "=== BPTree Tests ===" << std::endl;

    test_tree_creation();
    test_create_child();
    test_create_children();
    test_inherited_decisions();
    test_node_lookup();
    test_bounds();
    test_prune_by_bound();
    test_get_open_nodes();
    test_incumbent();
    test_path_to_root();
    test_statistics();

    std::cout << "\nAll tests passed!" << std::endl;
    return 0;
}
