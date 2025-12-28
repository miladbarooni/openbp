/**
 * @file tree_bindings.cpp
 * @brief pybind11 bindings for BPTree and TreeStats.
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>

#include "core/tree.hpp"

namespace py = pybind11;

void init_tree_bindings(py::module_& m) {
    using namespace openbp;

    // TreeStats struct
    py::class_<TreeStats>(m, "TreeStats", R"doc(
Statistics about the branch-and-price tree.

Tracks node counts, bounds, and exploration progress.
)doc")
        .def(py::init<>())
        .def_readwrite("nodes_created", &TreeStats::nodes_created,
            "Total nodes created")
        .def_readwrite("nodes_processed", &TreeStats::nodes_processed,
            "Total nodes processed")
        .def_readwrite("nodes_pruned_bound", &TreeStats::nodes_pruned_bound,
            "Nodes pruned by bound")
        .def_readwrite("nodes_pruned_infeasible", &TreeStats::nodes_pruned_infeasible,
            "Nodes pruned for infeasibility")
        .def_readwrite("nodes_integer", &TreeStats::nodes_integer,
            "Nodes with integer solutions")
        .def_readwrite("nodes_branched", &TreeStats::nodes_branched,
            "Nodes that were branched")
        .def_readwrite("nodes_open", &TreeStats::nodes_open,
            "Currently open nodes")
        .def_readwrite("max_depth", &TreeStats::max_depth,
            "Maximum tree depth reached")
        .def_readwrite("best_lower_bound", &TreeStats::best_lower_bound,
            "Best lower bound")
        .def_readwrite("best_upper_bound", &TreeStats::best_upper_bound,
            "Best upper bound (incumbent)")
        .def("gap", &TreeStats::gap,
            "Current optimality gap")
        .def("__repr__", [](const TreeStats& s) {
            return "<TreeStats nodes=" + std::to_string(s.nodes_created) +
                   " open=" + std::to_string(s.nodes_open) +
                   " gap=" + std::to_string(s.gap() * 100) + "%>";
        });

    // BPTree class
    py::class_<BPTree>(m, "BPTree", R"doc(
The branch-and-price search tree.

Manages node storage, tree structure, and global bounds.
Provides efficient node creation, access, and traversal.

Example:
    tree = BPTree(minimize=True)
    root = tree.root()
    root.lower_bound = 50.0

    # Create children
    d1 = BranchingDecision.variable_branch(0, 1.5, True)  # x[0] <= 1
    d2 = BranchingDecision.variable_branch(0, 1.5, False) # x[0] >= 2
    children = tree.create_children(root, [d1, d2])
)doc")
        .def(py::init<bool>(),
            py::arg("minimize") = true,
            "Create a new B&P tree")

        // Root access
        .def("root", static_cast<BPNode* (BPTree::*)()>(&BPTree::root),
            py::return_value_policy::reference,
            "Get the root node")
        .def_property_readonly("root_id", &BPTree::root_id,
            "Root node ID")

        // Node access
        .def("node", static_cast<BPNode* (BPTree::*)(BPNode::NodeId)>(&BPTree::node),
            py::arg("id"),
            py::return_value_policy::reference,
            "Get a node by ID")
        .def("has_node", &BPTree::has_node,
            py::arg("id"),
            "Check if a node exists")
        .def_property_readonly("num_nodes", &BPTree::num_nodes,
            "Total number of nodes")

        // Node creation
        .def("create_child", &BPTree::create_child,
            py::arg("parent"), py::arg("decision"),
            py::return_value_policy::reference,
            "Create a child node with a branching decision")
        .def("create_children", &BPTree::create_children,
            py::arg("parent"), py::arg("decisions"),
            py::return_value_policy::reference,
            "Create multiple children with branching decisions")

        // Node status
        .def("mark_processed", &BPTree::mark_processed,
            py::arg("node"), py::arg("new_status"),
            "Mark a node as processed with new status")

        // Bounds
        .def_property("global_lower_bound",
            &BPTree::global_lower_bound, &BPTree::set_global_lower_bound,
            "Global lower bound")
        .def_property("global_upper_bound",
            &BPTree::global_upper_bound, &BPTree::set_global_upper_bound,
            "Global upper bound (incumbent)")
        .def_property_readonly("is_minimizing", &BPTree::is_minimizing,
            "Whether this is a minimization problem")
        .def("update_bounds", &BPTree::update_bounds,
            py::arg("node"),
            "Update bounds after processing a node")
        .def("compute_lower_bound", &BPTree::compute_lower_bound,
            py::arg("open_node_ids"),
            "Compute lower bound from open nodes")
        .def("prune_by_bound", &BPTree::prune_by_bound,
            "Prune all nodes by bound, returns count")
        .def("gap", &BPTree::gap,
            "Current optimality gap")

        // Open nodes
        .def("get_open_nodes", &BPTree::get_open_nodes,
            "Get IDs of all open nodes")
        .def_property_readonly("is_complete", &BPTree::is_complete,
            "Whether tree exploration is complete")

        // Statistics
        .def_property_readonly("stats",
            static_cast<const TreeStats& (BPTree::*)() const>(&BPTree::stats),
            py::return_value_policy::reference,
            "Tree statistics")

        // Incumbent
        .def("incumbent",
            static_cast<BPNode* (BPTree::*)()>(&BPTree::incumbent),
            py::return_value_policy::reference,
            "Get the incumbent node")
        .def("set_incumbent", &BPTree::set_incumbent,
            py::arg("node"),
            "Set the incumbent node")

        // Path operations
        .def("get_path_to_root", &BPTree::get_path_to_root,
            py::arg("target_id"),
            "Get node IDs from root to target")

        // Iteration
        .def("for_each_node", [](BPTree& tree, py::function callback) {
            tree.for_each_node([&callback](BPNode* node) {
                callback(node);
            });
        }, py::arg("callback"),
        "Iterate over all nodes")

        .def("__repr__", [](const BPTree& t) {
            return "<BPTree nodes=" + std::to_string(t.num_nodes()) +
                   " open=" + std::to_string(t.stats().nodes_open) +
                   " gap=" + std::to_string(t.gap() * 100) + "%>";
        });
}
