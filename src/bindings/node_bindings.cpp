/**
 * @file node_bindings.cpp
 * @brief pybind11 bindings for BPNode and related classes.
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "core/node.hpp"

namespace py = pybind11;

void init_node_bindings(py::module_& m) {
    using namespace openbp;

    // NodeStatus enum
    py::enum_<NodeStatus>(m, "NodeStatus", "Status of a B&P tree node")
        .value("PENDING", NodeStatus::PENDING, "Not yet processed")
        .value("PROCESSING", NodeStatus::PROCESSING, "Currently being processed")
        .value("BRANCHED", NodeStatus::BRANCHED, "Branched into children")
        .value("PRUNED_BOUND", NodeStatus::PRUNED_BOUND, "Pruned by bound")
        .value("PRUNED_INFEASIBLE", NodeStatus::PRUNED_INFEASIBLE, "LP relaxation infeasible")
        .value("INTEGER", NodeStatus::INTEGER, "Integer solution found")
        .value("FATHOMED", NodeStatus::FATHOMED, "Fathomed (other reason)")
        .export_values();

    // BranchType enum
    py::enum_<BranchType>(m, "BranchType", "Type of branching decision")
        .value("VARIABLE", BranchType::VARIABLE, "Standard variable branching")
        .value("RYAN_FOSTER", BranchType::RYAN_FOSTER, "Ryan-Foster branching for set partitioning")
        .value("ARC", BranchType::ARC, "Arc branching for routing problems")
        .value("RESOURCE", BranchType::RESOURCE, "Resource window branching")
        .value("CUSTOM", BranchType::CUSTOM, "User-defined branching")
        .export_values();

    // BranchingDecision struct
    py::class_<BranchingDecision>(m, "BranchingDecision", R"doc(
A single branching decision in the B&P tree.

Branching decisions are polymorphic - the interpretation depends on
the branch type. Different branching strategies can store their
decisions in a uniform container.

Factory methods:
    - variable_branch(var_idx, value, is_upper): Standard variable branching
    - ryan_foster(item_i, item_j, same_column): Ryan-Foster branching
    - arc_branch(arc, source, required): Arc branching
    - resource_branch(res_idx, lb, ub): Resource window branching
)doc")
        .def(py::init<>())
        .def_readwrite("type", &BranchingDecision::type, "Type of branching")

        // Variable branching fields
        .def_readwrite("variable_index", &BranchingDecision::variable_index)
        .def_readwrite("bound_value", &BranchingDecision::bound_value)
        .def_readwrite("is_upper_bound", &BranchingDecision::is_upper_bound)

        // Ryan-Foster fields
        .def_readwrite("item_i", &BranchingDecision::item_i)
        .def_readwrite("item_j", &BranchingDecision::item_j)
        .def_readwrite("same_column", &BranchingDecision::same_column)

        // Arc branching fields
        .def_readwrite("arc_index", &BranchingDecision::arc_index)
        .def_readwrite("source_node", &BranchingDecision::source_node)
        .def_readwrite("arc_required", &BranchingDecision::arc_required)

        // Resource branching fields
        .def_readwrite("resource_index", &BranchingDecision::resource_index)
        .def_readwrite("lower_bound", &BranchingDecision::lower_bound)
        .def_readwrite("upper_bound", &BranchingDecision::upper_bound)

        // Custom fields
        .def_readwrite("custom_int_data", &BranchingDecision::custom_int_data)
        .def_readwrite("custom_float_data", &BranchingDecision::custom_float_data)

        // Factory methods
        .def_static("variable_branch", &BranchingDecision::variable_branch,
            py::arg("var_idx"), py::arg("value"), py::arg("upper"),
            "Create a variable branching decision")
        .def_static("ryan_foster", &BranchingDecision::ryan_foster,
            py::arg("item_i"), py::arg("item_j"), py::arg("same"),
            "Create a Ryan-Foster branching decision")
        .def_static("arc_branch", &BranchingDecision::arc_branch,
            py::arg("arc"), py::arg("source"), py::arg("required"),
            "Create an arc branching decision")
        .def_static("resource_branch", &BranchingDecision::resource_branch,
            py::arg("res_idx"), py::arg("lb"), py::arg("ub"),
            "Create a resource branching decision")

        .def("__repr__", [](const BranchingDecision& d) {
            std::string type_str = branch_type_to_string(d.type);
            switch (d.type) {
                case BranchType::VARIABLE:
                    return "<BranchingDecision VARIABLE x[" + std::to_string(d.variable_index) + "] " +
                           (d.is_upper_bound ? "<=" : ">=") + " " + std::to_string(d.bound_value) + ">";
                case BranchType::RYAN_FOSTER:
                    return "<BranchingDecision RYAN_FOSTER (" + std::to_string(d.item_i) + "," +
                           std::to_string(d.item_j) + ") " + (d.same_column ? "SAME" : "DIFF") + ">";
                case BranchType::ARC:
                    return "<BranchingDecision ARC " + std::to_string(d.arc_index) +
                           (d.arc_required ? " REQUIRED" : " FORBIDDEN") + ">";
                default:
                    return "<BranchingDecision " + type_str + ">";
            }
        });

    // BPNode class
    py::class_<BPNode>(m, "BPNode", R"doc(
A node in the branch-and-price tree.

BPNode stores bounds, branching decisions, solution information,
and tree structure. It is designed for efficient tree traversal
and node management.

Attributes:
    id: Unique node identifier
    parent_id: Parent node ID (-1 for root)
    depth: Depth in tree (0 for root)
    lower_bound: Lower bound from LP relaxation
    upper_bound: Upper bound (from integer solutions)
    lp_value: LP objective value at this node
    status: Current node status
    is_integer: Whether LP solution is integer
)doc")
        .def(py::init<>(), "Create a root node")

        // Basic properties
        .def_property_readonly("id", &BPNode::id, "Unique node identifier")
        .def_property_readonly("parent_id", &BPNode::parent_id, "Parent node ID")
        .def_property_readonly("depth", &BPNode::depth, "Depth in tree")

        // Bounds
        .def_property("lower_bound", &BPNode::lower_bound, &BPNode::set_lower_bound,
            "Lower bound from LP relaxation")
        .def_property("upper_bound", &BPNode::upper_bound, &BPNode::set_upper_bound,
            "Upper bound")
        .def_property("lp_value", &BPNode::lp_value, &BPNode::set_lp_value,
            "LP objective value")
        .def_property_readonly("gap", &BPNode::gap, "Optimality gap")

        // Status
        .def_property("status", &BPNode::status, &BPNode::set_status, "Node status")
        .def_property("is_integer", &BPNode::is_integer, &BPNode::set_is_integer,
            "Whether LP solution is integer")
        .def_property_readonly("is_processed", &BPNode::is_processed,
            "Whether node has been processed")
        .def_property_readonly("is_pruned", &BPNode::is_pruned,
            "Whether node has been pruned")
        .def_property_readonly("can_be_explored", &BPNode::can_be_explored,
            "Whether node can still be explored")

        // Branching decisions
        .def_property_readonly("local_decisions", &BPNode::local_decisions,
            py::return_value_policy::reference,
            "Branching decisions at this node")
        .def_property_readonly("inherited_decisions", &BPNode::inherited_decisions,
            py::return_value_policy::reference,
            "Branching decisions inherited from ancestors")
        .def("all_decisions", &BPNode::all_decisions,
            "Get all branching decisions (inherited + local)")
        .def_property_readonly("num_decisions", &BPNode::num_decisions,
            "Total number of branching decisions")

        .def("add_local_decision", &BPNode::add_local_decision,
            py::arg("decision"),
            "Add a local branching decision")

        // Children
        .def_property_readonly("children", &BPNode::children,
            py::return_value_policy::reference,
            "Child node IDs")
        .def_property_readonly("has_children", &BPNode::has_children,
            "Whether node has children")

        // Solution
        .def("set_solution", [](BPNode& self, std::vector<double> sol) {
            self.set_solution(std::move(sol));
        }, py::arg("solution"), "Set the solution vector")
        .def_property_readonly("solution", &BPNode::solution,
            py::return_value_policy::reference,
            "Solution vector")
        .def_property_readonly("has_solution", &BPNode::has_solution,
            "Whether node has a solution stored")

        .def("set_solution_columns", [](BPNode& self, std::vector<int32_t> cols) {
            self.set_solution_columns(std::move(cols));
        }, py::arg("columns"), "Set the solution columns")
        .def_property_readonly("solution_columns", &BPNode::solution_columns,
            py::return_value_policy::reference,
            "Column indices in the solution")

        // Pruning
        .def("try_prune_by_bound", &BPNode::try_prune_by_bound,
            py::arg("global_upper"),
            "Try to prune by bound, returns true if pruned")

        .def("__repr__", [](const BPNode& n) {
            return "<BPNode id=" + std::to_string(n.id()) +
                   " depth=" + std::to_string(n.depth()) +
                   " lb=" + std::to_string(n.lower_bound()) +
                   " status=" + std::string(node_status_to_string(n.status())) + ">";
        });
}
