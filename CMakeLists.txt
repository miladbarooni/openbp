cmake_minimum_required(VERSION 3.15)
project(openbp VERSION 0.1.0 LANGUAGES CXX)

# C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Compiler flags
set(CMAKE_CXX_FLAGS_DEBUG "-g -O0 -DDEBUG")
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG")

# Options
option(BUILD_PYTHON_BINDINGS "Build Python bindings using pybind11" ON)
option(BUILD_TESTS "Build C++ tests" ON)
option(BUILD_BENCHMARKS "Build benchmarks" OFF)

# Find packages
if(BUILD_PYTHON_BINDINGS)
    find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
    find_package(pybind11 CONFIG QUIET)

    if(NOT pybind11_FOUND)
        # Try to find pybind11 via Python
        execute_process(
            COMMAND ${Python3_EXECUTABLE} -c "import pybind11; print(pybind11.get_cmake_dir())"
            OUTPUT_VARIABLE pybind11_DIR
            OUTPUT_STRIP_TRAILING_WHITESPACE
            ERROR_QUIET
        )
        if(pybind11_DIR)
            find_package(pybind11 CONFIG REQUIRED PATHS ${pybind11_DIR})
        else()
            message(FATAL_ERROR "pybind11 not found. Install with: pip install pybind11")
        endif()
    endif()
endif()

# Find threading support
find_package(Threads REQUIRED)

# Include directories
include_directories(${CMAKE_SOURCE_DIR}/src)

# Core library (header-only)
add_library(openbp_core INTERFACE)
target_include_directories(openbp_core INTERFACE
    $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/src>
    $<INSTALL_INTERFACE:include>
)

# Python bindings
if(BUILD_PYTHON_BINDINGS)
    pybind11_add_module(_core
        src/bindings/module.cpp
        src/bindings/node_bindings.cpp
        src/bindings/tree_bindings.cpp
        src/bindings/selection_bindings.cpp
    )
    target_link_libraries(_core PRIVATE openbp_core Threads::Threads)

    # Install the module to the openbp package
    install(TARGETS _core
        LIBRARY DESTINATION openbp
        COMPONENT python
    )
endif()

# Tests
if(BUILD_TESTS)
    enable_testing()

    add_executable(test_node tests/cpp/test_node.cpp)
    target_link_libraries(test_node PRIVATE openbp_core)
    add_test(NAME test_node COMMAND test_node)

    add_executable(test_tree tests/cpp/test_tree.cpp)
    target_link_libraries(test_tree PRIVATE openbp_core)
    add_test(NAME test_tree COMMAND test_tree)
endif()

# Benchmarks
if(BUILD_BENCHMARKS)
    add_executable(bench_tree benchmarks/bench_tree.cpp)
    target_link_libraries(bench_tree PRIVATE openbp_core)
endif()

# Print configuration
message(STATUS "OpenBP C++ Configuration:")
message(STATUS "  Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  C++ standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  Python bindings: ${BUILD_PYTHON_BINDINGS}")
message(STATUS "  Tests: ${BUILD_TESTS}")
message(STATUS "  Benchmarks: ${BUILD_BENCHMARKS}")
