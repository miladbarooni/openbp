#!/usr/bin/env python3
"""
Diagnose resource constraints for remaining uncovered flights.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "opencg"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opencg.parsers import KasirzadehParser
from opencg.parsers.base import ParserConfig
from opencg.config import get_data_path
from opencg.core.arc import ArcType


def main():
    data_path = get_data_path() / "kasirzadeh" / "instance1"

    # Configure parser
    parser_config = ParserConfig(
        verbose=False,
        validate=True,
        options={
            'min_connection_time': 0.5,
            'max_connection_time': 4.0,
            'min_layover_time': 4.0,
            'max_layover_time': 24.0,
            'max_duty_time': 14.0,
            'max_pairing_days': 5,
        }
    )
    kparser = KasirzadehParser(parser_config)
    problem = kparser.parse(data_path)

    print(f"Instance: {problem.name}")
    print(f"Resources: {[r.name for r in problem.resources]}")
    print()

    # Get resource limits
    for r in problem.resources:
        if hasattr(r, 'max_value'):
            print(f"  {r.name}: max={r.max_value}")

    # Problem flights
    problem_flights = [855, 873]

    # Get flight arcs
    flight_arcs = {}
    for arc in problem.network.arcs:
        if arc.arc_type == ArcType.FLIGHT:
            flight_arcs[arc.index] = arc

    # Build adjacency
    outgoing = {}
    incoming = {}
    for arc in problem.network.arcs:
        outgoing.setdefault(arc.source, []).append(arc)
        incoming.setdefault(arc.target, []).append(arc)

    # Get source and sink arcs
    source_arcs = [a for a in problem.network.arcs if a.arc_type == ArcType.SOURCE_ARC]
    sink_arcs = [a for a in problem.network.arcs if a.arc_type == ArcType.SINK_ARC]

    print(f"\nSource arcs: {len(source_arcs)}")
    print(f"Sink arcs: {len(sink_arcs)}")

    for flight_idx in problem_flights:
        print(f"\n{'='*70}")
        print(f"FLIGHT {flight_idx}")
        print(f"{'='*70}")

        arc = flight_arcs.get(flight_idx)
        if not arc:
            print("  Not found")
            continue

        print(f"Arc: node {arc.source} -> node {arc.target}")
        print(f"Resources consumed by this flight:")
        for r in problem.resources:
            val = arc.get_consumption(r.name, 0)
            print(f"  {r.name}: {val:.2f}")

        # Find shortest path from any source to this flight
        print(f"\nFinding shortest paths to this flight...")

        # BFS from source arcs
        for src_arc in source_arcs[:3]:  # Check first 3 bases
            base = src_arc.get_attribute('base')
            print(f"\n  From {base}:")

            # BFS to find path to flight source
            start_node = src_arc.target
            target_node = arc.source

            # Track: (node, path_arcs, total_duty, total_flight_time)
            queue = [(start_node, [src_arc], 0.0, 0.0)]
            visited = {start_node}
            found_path = None

            while queue and not found_path:
                node, path, duty, flight_time = queue.pop(0)

                if node == target_node:
                    found_path = (path, duty, flight_time)
                    break

                for next_arc in outgoing.get(node, []):
                    next_node = next_arc.target
                    if next_node in visited:
                        continue

                    # Calculate new resource values
                    new_duty = duty + next_arc.get_consumption('duty_time', 0)
                    new_flight = flight_time + next_arc.get_consumption('flight_time', 0)

                    # Skip if over limits (would be pruned by SPPRC)
                    if new_duty > 14.0:  # max_duty_time
                        continue

                    visited.add(next_node)
                    queue.append((next_node, path + [next_arc], new_duty, new_flight))

                    if len(queue) > 10000:  # Limit search
                        break

            if found_path:
                path, duty, flight_time = found_path
                print(f"    Path found with {len(path)} arcs")
                print(f"    Duty before flight: {duty:.2f}h")
                print(f"    Flight time before: {flight_time:.2f}h")

                # Add the target flight
                total_duty = duty + arc.get_consumption('duty_time', 0)
                print(f"    Duty after flight: {total_duty:.2f}h")

                # Now check if we can reach a sink from the flight's arrival
                print(f"    Checking path to sink...")

                # BFS from flight arrival to sink
                arr_node = arc.target
                queue2 = [(arr_node, total_duty)]
                visited2 = {arr_node}
                found_sink = None

                while queue2 and not found_sink:
                    node, duty = queue2.pop(0)

                    for next_arc in outgoing.get(node, []):
                        if next_arc.arc_type == ArcType.SINK_ARC:
                            if next_arc.get_attribute('base') == base:
                                found_sink = (next_arc, duty)
                                break

                        next_node = next_arc.target
                        if next_node in visited2:
                            continue

                        new_duty = duty + next_arc.get_consumption('duty_time', 0)
                        if new_duty > 14.0:
                            continue

                        visited2.add(next_node)
                        queue2.append((next_node, new_duty))

                if found_sink:
                    sink_arc, final_duty = found_sink
                    print(f"    Can reach sink! Final duty: {final_duty:.2f}h")
                else:
                    print(f"    CANNOT reach sink from {base} within duty limits!")
            else:
                print(f"    No feasible path found to flight source")


if __name__ == "__main__":
    main()
