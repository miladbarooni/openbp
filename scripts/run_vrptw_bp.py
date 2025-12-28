#!/usr/bin/env python3
"""
Script to run VRPTW Branch-and-Price solver with detailed logging.

Usage:
    python scripts/run_vrptw_bp.py [instance_file] [num_customers]

Examples:
    python scripts/run_vrptw_bp.py                          # Default: RC101, 25 customers
    python scripts/run_vrptw_bp.py RC101.txt 40             # RC101 with 40 customers
    python scripts/run_vrptw_bp.py R101.txt 50              # R101 with 50 customers
    python scripts/run_vrptw_bp.py /path/to/instance.txt    # Full path, all customers
"""

import sys
import os
import time
import argparse
from datetime import datetime

# Add paths for development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "opencg"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opencg.applications.vrp import VRPTWInstance, solve_vrptw, VRPTWConfig
from opencg.config import get_data_path
from openbp.applications.vrptw import solve_vrptw_bp, VRPTWBPConfig


class SmallVRPTWInstance:
    """Wrapper to create a smaller instance from a larger one."""

    def __init__(self, base_instance, num_customers=None):
        if num_customers is None:
            num_customers = base_instance.num_customers

        self.name = f"{base_instance.name}_{num_customers}"
        self.num_customers = num_customers
        self.depot = base_instance.depot
        self.customers = base_instance.customers[:num_customers]
        self.demands = base_instance.demands[:num_customers]
        self.time_windows = base_instance.time_windows[:num_customers]
        self.service_times = base_instance.service_times[:num_customers]
        self.vehicle_capacity = base_instance.vehicle_capacity
        self.depot_time_window = base_instance.depot_time_window
        self.num_vehicles = base_instance.num_vehicles
        self.total_demand = sum(self.demands)
        self.speed = base_instance.speed

    def distance(self, i, j):
        loc_i = self.depot if i == 0 else self.customers[i - 1]
        loc_j = self.depot if j == 0 else self.customers[j - 1]
        return ((loc_i[0] - loc_j[0])**2 + (loc_i[1] - loc_j[1])**2)**0.5

    def travel_time(self, i, j):
        return self.distance(i, j) / self.speed


def print_header(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_section(title):
    print()
    print("-" * 50)
    print(title)
    print("-" * 50)


def main():
    parser = argparse.ArgumentParser(description="Run VRPTW Branch-and-Price solver")
    parser.add_argument("instance", nargs="?", default="RC101.txt",
                        help="Instance file name or full path (default: RC101.txt)")
    parser.add_argument("num_customers", nargs="?", type=int, default=25,
                        help="Number of customers to use (default: 25)")
    parser.add_argument("--max-nodes", type=int, default=200,
                        help="Maximum B&B nodes to explore (default: 200)")
    parser.add_argument("--max-time", type=float, default=300.0,
                        help="Maximum time in seconds (default: 300)")
    parser.add_argument("--cg-iterations", type=int, default=100,
                        help="Max CG iterations for column pool (default: 100)")

    args = parser.parse_args()

    # Print run info
    print_header(f"VRPTW Branch-and-Price Solver")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")

    # Load instance
    print_section("Loading Instance")

    if os.path.isabs(args.instance) or os.path.exists(args.instance):
        instance_path = args.instance
    else:
        solomon_path = get_data_path() / "solomon"
        instance_path = solomon_path / args.instance

    print(f"Instance file: {instance_path}")

    try:
        base_instance = VRPTWInstance.from_solomon(str(instance_path))
        print(f"Loaded: {base_instance.name}")
        print(f"  Total customers in file: {base_instance.num_customers}")
        print(f"  Vehicle capacity: {base_instance.vehicle_capacity}")
        print(f"  Depot time window: {base_instance.depot_time_window}")
    except Exception as e:
        print(f"ERROR loading instance: {e}")
        sys.exit(1)

    # Create working instance
    if args.num_customers and args.num_customers < base_instance.num_customers:
        instance = SmallVRPTWInstance(base_instance, args.num_customers)
        print(f"\nUsing first {args.num_customers} customers")
    else:
        instance = base_instance
        print(f"\nUsing all {base_instance.num_customers} customers")

    print(f"\nWorking instance: {instance.name}")
    print(f"  Customers: {instance.num_customers}")
    print(f"  Total demand: {instance.total_demand}")
    print(f"  Min vehicles (by capacity): {int(instance.total_demand / instance.vehicle_capacity) + 1}")

    # Step 1: Run Column Generation
    print_section("Step 1: Column Generation (OpenCG)")

    cg_config = VRPTWConfig(
        max_iterations=args.cg_iterations,
        verbose=True,
    )

    print(f"Config: max_iterations={cg_config.max_iterations}")
    print()

    cg_start = time.time()
    cg_solution = solve_vrptw(instance, cg_config)
    cg_time = time.time() - cg_start

    print()
    print("CG Results:")
    print(f"  LP Objective: {cg_solution.total_distance:.4f}")
    print(f"  IP Objective: {cg_solution.total_distance_ip:.4f}")

    if cg_solution.total_distance > 0:
        cg_gap = (cg_solution.total_distance_ip - cg_solution.total_distance) / cg_solution.total_distance * 100
        print(f"  Integrality Gap: {cg_gap:.2f}%")
    else:
        cg_gap = 0

    print(f"  Number of routes: {len(cg_solution.routes)}")
    print(f"  Total columns generated: {cg_solution.num_columns}")
    print(f"  CG iterations: {cg_solution.iterations}")
    print(f"  Solve time: {cg_time:.2f}s")

    print("\nCG Routes:")
    for i, route in enumerate(cg_solution.routes):
        print(f"  Route {i+1}: {route}")

    # Step 2: Run Branch-and-Price
    print_section("Step 2: Branch-and-Price (OpenBP)")

    bp_config = VRPTWBPConfig(
        max_time=args.max_time,
        max_nodes=args.max_nodes,
        cg_max_iterations=args.cg_iterations,
        verbose=True,
    )

    print(f"Config:")
    print(f"  max_time: {bp_config.max_time}s")
    print(f"  max_nodes: {bp_config.max_nodes}")
    print(f"  cg_max_iterations: {bp_config.cg_max_iterations}")
    print()

    bp_start = time.time()
    bp_solution = solve_vrptw_bp(instance, bp_config)
    bp_time = time.time() - bp_start

    print()
    print("B&P Results:")
    print(f"  Status: {bp_solution.status.name}")
    print(f"  Objective: {bp_solution.objective:.4f}")
    print(f"  Lower Bound: {bp_solution.lower_bound:.4f}")
    print(f"  Gap: {bp_solution.gap * 100:.2f}%")
    print(f"  Nodes explored: {bp_solution.nodes_explored}")
    print(f"  Nodes pruned: {bp_solution.nodes_pruned}")
    print(f"  Max depth: {bp_solution.max_depth}")
    print(f"  Solve time: {bp_time:.2f}s")

    print("\nB&P Routes:")
    for i, route in enumerate(bp_solution.routes):
        print(f"  Route {i+1}: {route}")

    # Summary comparison
    print_header("Summary Comparison")

    print(f"{'Metric':<25} {'CG':<20} {'B&P':<20}")
    print("-" * 65)
    print(f"{'LP Relaxation':<25} {cg_solution.total_distance:<20.4f} {bp_solution.lower_bound:<20.4f}")
    print(f"{'Integer Solution':<25} {cg_solution.total_distance_ip:<20.4f} {bp_solution.objective:<20.4f}")
    print(f"{'Number of Routes':<25} {len(cg_solution.routes):<20} {len(bp_solution.routes):<20}")
    print(f"{'Solve Time (s)':<25} {cg_time:<20.2f} {bp_time:<20.2f}")

    improvement = cg_solution.total_distance_ip - bp_solution.objective
    if improvement > 0.01:
        print()
        print(f"*** B&P found BETTER solution: improvement = {improvement:.4f} ({improvement/cg_solution.total_distance_ip*100:.2f}%)")
    elif improvement < -0.01:
        print()
        print(f"*** CG IP was better (B&P may have hit limits)")
    else:
        print()
        print(f"*** B&P confirmed CG solution is OPTIMAL")

    print()
    print("=" * 70)
    print("Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()
