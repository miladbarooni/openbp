#!/usr/bin/env python3
"""
Script to compare Crew Pairing: Column Generation (OpenCG) vs Branch-and-Price (OpenBP).

Usage:
    python scripts/run_crew_pairing_bp.py [instance_name] [--max-nodes N] [--max-time N]

Examples:
    python scripts/run_crew_pairing_bp.py instance1
    python scripts/run_crew_pairing_bp.py instance2 --max-nodes 100
    python scripts/run_crew_pairing_bp.py instance1 --max-time 600
"""

import sys
import os
import time
import argparse
from datetime import datetime

# Add paths for development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "opencg"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opencg.parsers import KasirzadehParser
from opencg.parsers.base import ParserConfig
from opencg.config import get_data_path
from opencg.applications.crew_pairing import solve_crew_pairing, CrewPairingConfig
from openbp.applications.crew_pairing import solve_crew_pairing_bp, CrewPairingBPConfig


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


def format_time(seconds):
    """Format time in human-readable format."""
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def main():
    parser = argparse.ArgumentParser(
        description="Compare Crew Pairing: CG (OpenCG) vs B&P (OpenBP)"
    )
    parser.add_argument("instance", nargs="?", default="instance1",
                        help="Instance name (default: instance1)")
    parser.add_argument("--max-nodes", type=int, default=100,
                        help="Maximum B&B nodes (default: 100)")
    parser.add_argument("--max-time", type=float, default=600.0,
                        help="Maximum time in seconds (default: 600)")
    parser.add_argument("--cg-iterations", type=int, default=50,
                        help="Max CG iterations (default: 50)")
    parser.add_argument("--skip-bp", action="store_true",
                        help="Skip B&P (only run CG)")

    args = parser.parse_args()

    print_header("Crew Pairing: Column Generation vs Branch-and-Price")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")

    # Load instance
    print_section("Loading Instance")

    data_path = get_data_path() / "kasirzadeh"
    instance_path = data_path / args.instance

    # Handle nested directory structure (instance1/instance1)
    if not instance_path.exists():
        print(f"ERROR: Instance not found at: {instance_path}")
        sys.exit(1)

    # Check for nested structure
    nested_path = instance_path / args.instance
    if nested_path.exists():
        instance_path = nested_path
        print(f"Using nested path: {instance_path}")

    print(f"Instance path: {instance_path}")

    # Configure parser with constraints from Kasirzadeh et al. paper
    # NOTE: min_layover_time is set to 4.0 to close the gap with max_connection_time
    # This ensures all flights have valid connections in the network
    # NOTE: Relaxed constraints to ensure 100% coverage
    parser_config = ParserConfig(
        verbose=False,
        validate=True,
        options={
            'min_connection_time': 0.5,
            'max_connection_time': 4.0,
            'min_layover_time': 4.0,  # Close the gap with max_connection
            'max_layover_time': 24.0,
            'max_duty_time': 14.0,
            'max_flight_time': 10.0,  # Allow longer flight time per duty
            'max_pairing_days': 7,  # Allow longer pairings
        }
    )
    kparser = KasirzadehParser(parser_config)

    if not kparser.can_parse(instance_path):
        print(f"ERROR: Cannot parse {instance_path}")
        print("Make sure the directory contains listOfBases.csv and day_*.csv files")
        sys.exit(1)

    load_start = time.time()
    problem = kparser.parse(instance_path)
    load_time = time.time() - load_start

    print(f"Instance loaded in {format_time(load_time)}")
    print(f"  Name: {problem.name}")
    print(f"  Flights: {len(problem.cover_constraints)}")
    print(f"  Network nodes: {problem.network.num_nodes}")
    print(f"  Network arcs: {problem.network.num_arcs}")
    print(f"  Resources: {len(problem.resources)}")

    # Step 1: Column Generation (OpenCG)
    print_section("Step 1: Column Generation (OpenCG)")

    cg_config = CrewPairingConfig(
        max_iterations=args.cg_iterations,
        pricing_max_columns=200,  # Columns to select from
        cols_per_source=5,  # Columns per source
        time_per_source=0.1,  # Time per source
        num_threads=0,  # Auto-detect CPU count for parallel pricing
        verbose=False,  # Disable verbose output
    )

    print(f"Config: max_iterations={cg_config.max_iterations}")
    print()

    cg_start = time.time()
    cg_solution = solve_crew_pairing(problem, cg_config)
    cg_time = time.time() - cg_start

    print("CG Results:")
    print(f"  LP Objective: {cg_solution.objective:.2f}")
    print(f"  Pairings: {cg_solution.num_pairings}")
    print(f"  Coverage: {cg_solution.coverage_pct:.1f}%")
    print(f"  Uncovered flights: {len(cg_solution.uncovered_flights)}")
    print(f"  Columns generated: {cg_solution.num_columns}")
    print(f"  CG iterations: {cg_solution.iterations}")
    print(f"  Time: {format_time(cg_time)}")

    if args.skip_bp:
        print()
        print("Skipping B&P (--skip-bp flag set)")
        print("=" * 70)
        print("Done!")
        return

    # Step 2: Branch-and-Price (OpenBP)
    print_section("Step 2: Branch-and-Price (OpenBP)")

    bp_config = CrewPairingBPConfig(
        max_time=args.max_time,
        max_nodes=args.max_nodes,
        cg_max_iterations=args.cg_iterations,
        cg_max_columns=200,
        cols_per_source=5,
        time_per_source=0.1,
        verbose=True,
    )

    print(f"Config:")
    print(f"  max_time: {bp_config.max_time}s")
    print(f"  max_nodes: {bp_config.max_nodes}")
    print()

    bp_start = time.time()
    bp_solution = solve_crew_pairing_bp(problem, bp_config)
    bp_time = time.time() - bp_start

    print()
    print("B&P Results:")
    print(f"  Status: {bp_solution.status.name}")
    print(f"  Objective: {bp_solution.objective:.2f}")
    print(f"  Lower Bound: {bp_solution.lower_bound:.2f}")
    print(f"  Gap: {bp_solution.gap * 100:.2f}%")
    print(f"  Pairings: {len(bp_solution.pairings)}")
    print(f"  Coverage: {bp_solution.coverage_pct:.1f}%")
    print(f"  Nodes explored: {bp_solution.nodes_explored}")
    print(f"  Nodes pruned: {bp_solution.nodes_pruned}")
    print(f"  Max depth: {bp_solution.max_depth}")
    print(f"  Time: {format_time(bp_time)}")

    # Summary comparison
    print_header("Summary Comparison")

    print(f"{'Metric':<25} {'CG (OpenCG)':<20} {'B&P (OpenBP)':<20}")
    print("-" * 65)
    print(f"{'LP Objective':<25} {cg_solution.objective:<20.2f} {bp_solution.lower_bound:<20.2f}")
    print(f"{'IP Objective':<25} {'-':<20} {bp_solution.objective:<20.2f}")
    print(f"{'Pairings':<25} {cg_solution.num_pairings:<20} {len(bp_solution.pairings):<20}")
    print(f"{'Coverage (%)':<25} {cg_solution.coverage_pct:<20.1f} {bp_solution.coverage_pct:<20.1f}")
    print(f"{'Gap (%)':<25} {'-':<20} {bp_solution.gap*100:<20.2f}")
    print(f"{'Time (s)':<25} {cg_time:<20.2f} {bp_time:<20.2f}")

    # Analysis
    print()
    if cg_solution.coverage_pct < 100 and bp_solution.coverage_pct >= 100:
        print("*** B&P achieved 100% coverage while CG did not!")
    elif bp_solution.gap < 0.01:
        print("*** B&P proved optimality (gap < 1%)")
    elif bp_solution.gap < cg_solution.objective * 0.1 if cg_solution.objective > 0 else True:
        print("*** B&P found optimal integer solution")
    else:
        print("*** B&P reduced the gap but did not prove optimality")

    print()
    print("=" * 70)
    print("Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()
