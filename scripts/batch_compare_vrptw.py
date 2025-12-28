#!/usr/bin/env python3
"""
Batch comparison of VRPTW solvers across multiple instances.
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "opencg"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compare_vrptw_highs import (
    SmallVRPTWInstance,
    solve_vrptw_highs_mip,
)
from opencg.applications.vrp import VRPTWInstance, solve_vrptw, VRPTWConfig
from opencg.config import get_data_path
from openbp.applications.vrptw import solve_vrptw_bp, VRPTWBPConfig


def main():
    solomon_path = get_data_path() / "solomon"

    # Test configurations: (instance, num_customers)
    tests = [
        ("RC101.txt", 20),
        ("RC101.txt", 25),
        ("RC101.txt", 30),
        ("RC101.txt", 40),
        ("R101.txt", 20),
        ("R101.txt", 25),
        ("R101.txt", 30),
        ("R101.txt", 40),
    ]

    print("=" * 100)
    print("VRPTW Solver Comparison: OpenCG vs OpenBP vs HiGHS MIP")
    print("=" * 100)
    print()
    print(f"{'Instance':<15} {'n':<5} {'CG-LP':<10} {'CG-IP':<10} {'B&P':<10} {'HiGHS':<10} "
          f"{'CG(s)':<8} {'B&P(s)':<8} {'HiGHS(s)':<8} {'Best':<8}")
    print("-" * 100)

    for instance_name, num_customers in tests:
        instance_path = solomon_path / instance_name

        try:
            base = VRPTWInstance.from_solomon(str(instance_path))
            instance = SmallVRPTWInstance(base, num_customers)

            # CG
            cg_start = time.time()
            cg_sol = solve_vrptw(instance, VRPTWConfig(max_iterations=100, verbose=False))
            cg_time = time.time() - cg_start

            # B&P
            bp_start = time.time()
            bp_sol = solve_vrptw_bp(instance, VRPTWBPConfig(max_nodes=500, max_time=60, verbose=False))
            bp_time = time.time() - bp_start

            # HiGHS
            highs_result = solve_vrptw_highs_mip(instance, max_time=60, verbose=False)

            # Find best
            objectives = [
                ('CG', cg_sol.total_distance_ip),
                ('B&P', bp_sol.objective),
                ('HiGHS', highs_result['objective']),
            ]
            best = min(objectives, key=lambda x: x[1] if x[1] < float('inf') else 1e10)

            bp_obj_str = f"{bp_sol.objective:.2f}" if bp_sol.objective < float('inf') else "inf"
            highs_obj_str = f"{highs_result['objective']:.2f}" if highs_result['objective'] < float('inf') else "inf"

            print(f"{instance_name:<15} {num_customers:<5} {cg_sol.total_distance:<10.2f} "
                  f"{cg_sol.total_distance_ip:<10.2f} {bp_obj_str:<10} {highs_obj_str:<10} "
                  f"{cg_time:<8.2f} {bp_time:<8.2f} {highs_result['time']:<8.2f} {best[0]:<8}")

        except Exception as e:
            print(f"{instance_name:<15} {num_customers:<5} ERROR: {e}")

    print("-" * 100)
    print()
    print("Legend:")
    print("  CG-LP   = Column Generation LP relaxation")
    print("  CG-IP   = Column Generation + IP rounding")
    print("  B&P     = Branch-and-Price (optimal)")
    print("  HiGHS   = Direct MIP formulation")
    print("  Best    = Method with best objective")


if __name__ == "__main__":
    main()
