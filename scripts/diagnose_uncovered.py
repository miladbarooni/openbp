#!/usr/bin/env python3
"""
Diagnose why certain flights remain uncovered in crew pairing.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "opencg"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opencg.parsers import KasirzadehParser
from opencg.parsers.base import ParserConfig
from opencg.config import get_data_path
from opencg.core.arc import ArcType
from opencg.applications.crew_pairing import solve_crew_pairing, CrewPairingConfig


def main():
    data_path = get_data_path() / "kasirzadeh" / "instance1"

    # Configure parser
    parser_config = ParserConfig(
        verbose=False,
        validate=True,
        options={
            'min_connection_time': 0.5,
            'max_connection_time': 4.0,
            'min_layover_time': 4.0,  # Close the gap
            'max_layover_time': 24.0,
            'max_duty_time': 14.0,
            'max_pairing_days': 5,
        }
    )
    kparser = KasirzadehParser(parser_config)
    problem = kparser.parse(data_path)

    print(f"Instance: {problem.name}")
    print(f"Flights: {len(problem.cover_constraints)}")
    print(f"Network nodes: {problem.network.num_nodes}")
    print(f"Network arcs: {problem.network.num_arcs}")
    print()

    # Run CG
    print("Running Column Generation...")
    config = CrewPairingConfig(
        max_iterations=50,
        pricing_max_columns=200,
        cols_per_source=5,
        time_per_source=0.1,
        verbose=False,
    )
    solution = solve_crew_pairing(problem, config)

    print(f"Objective: {solution.objective:.2f}")
    print(f"Coverage: {solution.coverage_pct:.1f}%")
    print(f"Uncovered: {len(solution.uncovered_flights)}")
    print()

    if not solution.uncovered_flights:
        print("All flights covered!")
        return

    print("=" * 70)
    print("Diagnosing uncovered flights")
    print("=" * 70)

    # Get flight arc info
    flight_arcs = {}
    for arc in problem.network.arcs:
        if arc.arc_type == ArcType.FLIGHT:
            flight_arcs[arc.index] = arc

    # Get source/sink arcs by base
    source_arcs_by_base = {}
    sink_arcs_by_base = {}
    for arc in problem.network.arcs:
        if arc.arc_type == ArcType.SOURCE_ARC:
            base = arc.get_attribute('base')
            if base:
                source_arcs_by_base.setdefault(base, []).append(arc)
        elif arc.arc_type == ArcType.SINK_ARC:
            base = arc.get_attribute('base')
            if base:
                sink_arcs_by_base.setdefault(base, []).append(arc)

    print(f"Bases: {list(source_arcs_by_base.keys())}")
    print()

    # For each uncovered flight, analyze reachability
    for flight_idx in sorted(solution.uncovered_flights):
        print(f"\n--- Flight {flight_idx} ---")

        if flight_idx not in flight_arcs:
            print(f"  WARNING: No arc for flight index {flight_idx}")
            continue

        arc = flight_arcs[flight_idx]
        print(f"  Arc: {arc.source} -> {arc.target}")
        print(f"  Cost: {arc.cost:.2f}")

        # Check attributes
        attrs = {}
        for attr in ['dep_airport', 'arr_airport', 'dep_time', 'arr_time']:
            val = arc.get_attribute(attr)
            if val:
                attrs[attr] = val
        print(f"  Attributes: {attrs}")

        # Check resource consumption
        resources = {}
        for res in problem.resources:
            val = arc.get_consumption(res.name, None)
            if val is not None:
                resources[res.name] = val
        print(f"  Resources: {resources}")

        # Find which bases have source arcs that can reach this flight's source node
        print(f"  Checking reachability from bases...")
        flight_source_node = arc.source
        flight_target_node = arc.target

        # Simple BFS from source arcs to flight source node
        reachable_from = []
        for base, base_source_arcs in source_arcs_by_base.items():
            for src_arc in base_source_arcs:
                # src_arc.target is where the source arc points to
                if can_reach(problem.network, src_arc.target, flight_source_node):
                    reachable_from.append(base)
                    break

        print(f"  Reachable from bases: {reachable_from}")

        # Check if flight target can reach any sink
        reachable_to = []
        for base, base_sink_arcs in sink_arcs_by_base.items():
            for snk_arc in base_sink_arcs:
                # snk_arc.source is where sink arc originates
                if can_reach(problem.network, flight_target_node, snk_arc.source):
                    reachable_to.append(base)
                    break

        print(f"  Can reach sinks for: {reachable_to}")

        # Check if any base can both reach and return
        roundtrip_bases = set(reachable_from) & set(reachable_to)
        print(f"  Roundtrip possible from: {roundtrip_bases}")


def can_reach(network, from_node, to_node, max_depth=50):
    """BFS to check if to_node is reachable from from_node."""
    if from_node == to_node:
        return True

    visited = {from_node}
    frontier = [from_node]
    depth = 0

    while frontier and depth < max_depth:
        depth += 1
        next_frontier = []
        for node in frontier:
            # Find all outgoing arcs from this node
            for arc in network.arcs:
                if arc.source == node and arc.target not in visited:
                    if arc.target == to_node:
                        return True
                    visited.add(arc.target)
                    next_frontier.append(arc.target)
        frontier = next_frontier

    return False


if __name__ == "__main__":
    main()
