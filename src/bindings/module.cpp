/**
 * @file module.cpp
 * @brief Main pybind11 module definition for OpenBP.
 */

#include <pybind11/pybind11.h>

namespace py = pybind11;

// Forward declarations
void init_node_bindings(py::module_& m);
void init_tree_bindings(py::module_& m);
void init_selection_bindings(py::module_& m);

PYBIND11_MODULE(_core, m) {
    m.doc() = R"doc(
OpenBP C++ Core Module

High-performance implementations of branch-and-price tree structures
and algorithms.

This module provides:
- BPNode: Tree node with bounds, branching decisions, and status
- BPTree: Search tree management with node storage
- NodeSelector: Various node selection policies (best-first, depth-first, etc.)
- BranchingDecision: Representation of branching choices

These classes are designed to work with Python branching strategies
while providing high-performance tree traversal and node management.
)doc";

    // Version info
    m.attr("__version__") = "0.1.0";
    m.attr("HAS_CPP_BACKEND") = true;

    // Initialize bindings
    init_node_bindings(m);
    init_tree_bindings(m);
    init_selection_bindings(m);
}
