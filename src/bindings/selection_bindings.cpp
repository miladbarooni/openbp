/**
 * @file selection_bindings.cpp
 * @brief pybind11 bindings for node selection policies.
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "core/selection.hpp"

namespace py = pybind11;

void init_selection_bindings(py::module_& m) {
    using namespace openbp;

    // Abstract NodeSelector base (for type hints)
    py::class_<NodeSelector>(m, "NodeSelector", R"doc(
Abstract base class for node selection policies.

Node selectors determine the order in which B&P tree nodes
are explored. Different strategies trade off between:
- Finding good solutions quickly (depth-first)
- Proving optimality efficiently (best-first)
- Hybrid approaches

Available implementations:
- BestFirstSelector: Explore lowest bound first
- DepthFirstSelector: Explore deepest nodes first
- BestEstimateSelector: Use bound + depth estimate
- HybridSelector: Alternate between strategies
)doc")
        .def("add_node", &NodeSelector::add_node,
            py::arg("node"),
            "Add a node to the open queue")
        .def("add_nodes", &NodeSelector::add_nodes,
            py::arg("nodes"),
            "Add multiple nodes to the open queue")
        .def("select_next", &NodeSelector::select_next,
            py::return_value_policy::reference,
            "Select and remove the next node to explore")
        .def("peek_next", &NodeSelector::peek_next,
            py::return_value_policy::reference,
            "Peek at the next node without removing")
        .def("empty", &NodeSelector::empty,
            "Check if there are any open nodes")
        .def("size", &NodeSelector::size,
            "Get the number of open nodes")
        .def("prune", &NodeSelector::prune,
            "Remove pruned nodes, returns count")
        .def("on_bound_update", &NodeSelector::on_bound_update,
            py::arg("new_bound"),
            "Called when global upper bound is updated")
        .def("best_bound", &NodeSelector::best_bound,
            "Get the best (lowest) bound among open nodes")
        .def("get_open_node_ids", &NodeSelector::get_open_node_ids,
            "Get IDs of all open nodes")
        .def("clear", &NodeSelector::clear,
            "Clear all nodes from the selector");

    // BestFirstSelector
    py::class_<BestFirstSelector, NodeSelector>(m, "BestFirstSelector", R"doc(
Best-first (best-bound) node selection.

Always explores the node with the lowest lower bound.
This minimizes the number of nodes explored but may delay
finding good integer solutions.

Best for: Proving optimality on easy instances.
)doc")
        .def(py::init<>())
        .def("__repr__", [](const BestFirstSelector& s) {
            return "<BestFirstSelector size=" + std::to_string(s.size()) + ">";
        });

    // DepthFirstSelector
    py::class_<DepthFirstSelector, NodeSelector>(m, "DepthFirstSelector", R"doc(
Depth-first node selection (diving).

Explores deepest nodes first, which tends to find integer
solutions quickly. Uses best-bound as tiebreaker at same depth.

Best for: Finding good solutions on hard instances.
)doc")
        .def(py::init<>())
        .def("__repr__", [](const DepthFirstSelector& s) {
            return "<DepthFirstSelector size=" + std::to_string(s.size()) + ">";
        });

    // BestEstimateSelector
    py::class_<BestEstimateSelector, NodeSelector>(m, "BestEstimateSelector", R"doc(
Best-estimate node selection.

Uses a combination of lower bound and depth-based estimate
to prioritize nodes likely to lead to good solutions.

Args:
    estimate_weight: Weight for depth-based estimate (default 0.5)
                    Higher values favor deeper nodes.
)doc")
        .def(py::init<double>(),
            py::arg("estimate_weight") = 0.5)
        .def("__repr__", [](const BestEstimateSelector& s) {
            return "<BestEstimateSelector size=" + std::to_string(s.size()) + ">";
        });

    // HybridSelector
    py::class_<HybridSelector, NodeSelector>(m, "HybridSelector", R"doc(
Hybrid node selection with periodic diving.

Alternates between best-first and depth-first selection
to balance bound improvement and solution finding.

Args:
    dive_frequency: How often to start diving (every N nodes)
    dive_depth: How deep to dive before switching back
)doc")
        .def(py::init<int, int>(),
            py::arg("dive_frequency") = 5,
            py::arg("dive_depth") = 10)
        .def("__repr__", [](const HybridSelector& s) {
            return "<HybridSelector size=" + std::to_string(s.size()) + ">";
        });

    // Factory function
    m.def("create_selector", &create_selector,
        py::arg("name"),
        R"doc(
Create a node selector by name.

Args:
    name: Selector name - one of:
        - "best_first" or "BestFirst"
        - "depth_first" or "DepthFirst"
        - "best_estimate" or "BestEstimate"
        - "hybrid" or "Hybrid"

Returns:
    NodeSelector: The requested selector (defaults to best_first)
)doc");
}
