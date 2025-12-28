#!/usr/bin/env python3
"""
Script to compare VRPTW B&P vs Branch-Price-and-Cut (BPC).

Usage:
    python scripts/run_vrptw_bpc.py [instance_file] [num_customers]

Examples:
    python scripts/run_vrptw_bpc.py RC101.txt 25
    python scripts/run_vrptw_bpc.py RC101.txt 40
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
from openbp.applications.vrptw_bpc import solve_vrptw_bpc, VRPTWBPCConfig


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
    parser = argparse.ArgumentParser(description="Compare VRPTW B&P vs BPC")
    parser.add_argument("instance", nargs="?", default="RC101.txt",
                        help="Instance file name (default: RC101.txt)")
    parser.add_argument("num_customers", nargs="?", type=int, default=25,
                        help="Number of customers (default: 25)")
    parser.add_argument("--max-nodes", type=int, default=200,
                        help="Maximum B&B nodes (default: 200)")
    parser.add_argument("--max-time", type=float, default=300.0,
                        help="Maximum time in seconds (default: 300)")

    args = parser.parse_args()

    print_header("VRPTW: B&P vs Branch-Price-and-Cut Comparison")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load instance
    print_section("Loading Instance")

    solomon_path = get_data_path() / "solomon"
    instance_path = solomon_path / args.instance

    print(f"Instance file: {instance_path}")

    base_instance = VRPTWInstance.from_solomon(str(instance_path))

    if args.num_customers < base_instance.num_customers:
        instance = SmallVRPTWInstance(base_instance, args.num_customers)
    else:
        instance = base_instance

    print(f"Instance: {instance.name}")
    print(f"  Customers: {instance.num_customers}")
    print(f"  Vehicle capacity: {instance.vehicle_capacity}")
    print(f"  Total demand: {instance.total_demand}")

    # Step 1: Column Generation baseline
    print_section("Step 1: Column Generation (OpenCG)")

    cg_start = time.time()
    cg_sol = solve_vrptw(instance, VRPTWConfig(max_iterations=100, verbose=False))
    cg_time = time.time() - cg_start

    print(f"  LP Objective: {cg_sol.total_distance:.2f}")
    print(f"  IP Objective: {cg_sol.total_distance_ip:.2f}")
    cg_gap = (cg_sol.total_distance_ip - cg_sol.total_distance) / cg_sol.total_distance * 100
    print(f"  Integrality Gap: {cg_gap:.2f}%")
    print(f"  Time: {cg_time:.2f}s")

    # Step 2: B&P (no cuts)
    print_section("Step 2: Branch-and-Price (no cuts)")

    bp_config = VRPTWBPConfig(
        max_time=args.max_time,
        max_nodes=args.max_nodes,
        verbose=True,
    )

    bp_start = time.time()
    bp_sol = solve_vrptw_bp(instance, bp_config)
    bp_time = time.time() - bp_start

    print()
    print(f"B&P Results:")
    print(f"  Objective: {bp_sol.objective:.2f}")
    print(f"  Lower Bound: {bp_sol.lower_bound:.2f}")
    print(f"  Gap: {bp_sol.gap*100:.2f}%")
    print(f"  Nodes: {bp_sol.nodes_explored}")
    print(f"  Time: {bp_time:.2f}s")

    # Step 3: BPC (with cuts)
    print_section("Step 3: Branch-Price-and-Cut (with capacity cuts)")

    bpc_config = VRPTWBPCConfig(
        max_time=args.max_time,
        max_nodes=args.max_nodes,
        enable_cuts=True,
        max_cuts_per_round=10,
        min_violation=0.1,
        max_subset_size=8,
        verbose=True,
    )

    bpc_start = time.time()
    bpc_sol = solve_vrptw_bpc(instance, bpc_config)
    bpc_time = time.time() - bpc_start

    print()
    print(f"BPC Results:")
    print(f"  Objective: {bpc_sol.objective:.2f}")
    print(f"  Lower Bound: {bpc_sol.lower_bound:.2f}")
    print(f"  Gap: {bpc_sol.gap*100:.2f}%")
    print(f"  Nodes: {bpc_sol.nodes_explored}")
    print(f"  Cuts added: {getattr(bpc_sol, 'total_cuts', 0)}")
    print(f"  Time: {bpc_time:.2f}s")

    # Summary
    print_header("Summary Comparison")

    print(f"{'Metric':<25} {'CG':<15} {'B&P':<15} {'BPC':<15}")
    print("-" * 70)
    print(f"{'LP Bound':<25} {cg_sol.total_distance:<15.2f} {'-':<15} {'-':<15}")
    print(f"{'Objective':<25} {cg_sol.total_distance_ip:<15.2f} {bp_sol.objective:<15.2f} {bpc_sol.objective:<15.2f}")
    print(f"{'Lower Bound':<25} {cg_sol.total_distance:<15.2f} {bp_sol.lower_bound:<15.2f} {bpc_sol.lower_bound:<15.2f}")
    print(f"{'Gap (%)':<25} {cg_gap:<15.2f} {bp_sol.gap*100:<15.2f} {bpc_sol.gap*100:<15.2f}")
    print(f"{'Nodes':<25} {1:<15} {bp_sol.nodes_explored:<15} {bpc_sol.nodes_explored:<15}")
    print(f"{'Cuts':<25} {0:<15} {0:<15} {getattr(bpc_sol, 'total_cuts', 0):<15}")
    print(f"{'Time (s)':<25} {cg_time:<15.2f} {bp_time:<15.2f} {bpc_time:<15.2f}")

    # Analysis
    print()
    if bpc_sol.nodes_explored < bp_sol.nodes_explored:
        reduction = (1 - bpc_sol.nodes_explored / bp_sol.nodes_explored) * 100
        print(f"*** Cuts reduced nodes by {reduction:.1f}%")
    elif bpc_sol.nodes_explored > bp_sol.nodes_explored:
        print(f"*** B&P explored fewer nodes (cuts didn't help for this instance)")
    else:
        print(f"*** Same number of nodes explored")

    print()
    print("=" * 70)
    print("Done!")


if __name__ == "__main__":
    main()
