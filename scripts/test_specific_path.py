#!/usr/bin/env python3
"""
Test if a specific path covering flights 855 and 873 is feasible.
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

    # Configure with relaxed constraints
    parser_config = ParserConfig(
        verbose=False,
        validate=True,
        options={
            'min_connection_time': 0.5,
            'max_connection_time': 4.0,
            'min_layover_time': 4.0,
            'max_layover_time': 24.0,
            'max_duty_time': 14.0,
            'max_flight_time': 10.0,
            'max_pairing_days': 7,
        }
    )
    kparser = KasirzadehParser(parser_config)
    problem = kparser.parse(data_path)

    print(f"Instance: {problem.name}")
    print(f"Resources:")
    for r in problem.resources:
        if hasattr(r, 'max_value'):
            print(f"  {r.name}: max={r.max_value}")
    print()

    # Build adjacency maps
    network = problem.network
    outgoing = {}
    for arc in network.arcs:
        outgoing.setdefault(arc.source, []).append(arc)

    # Get source arcs for BASE1
    source_arcs_base1 = [a for a in network.arcs
                         if a.arc_type == ArcType.SOURCE_ARC and a.get_attribute('base') == 'BASE1']
    print(f"Source arcs for BASE1: {len(source_arcs_base1)}")

    # Get flight arcs
    flight_arcs = {a.index: a for a in network.arcs if a.arc_type == ArcType.FLIGHT}

    # Get the specific flight arcs we need
    flight_855_arc = flight_arcs.get(855)
    flight_873_arc = flight_arcs.get(873)
    flight_909_arc = flight_arcs.get(909)

    print(f"\nFlight 855: arc {855}, nodes {flight_855_arc.source} -> {flight_855_arc.target}" if flight_855_arc else "Flight 855 not found")
    print(f"Flight 873: arc {873}, nodes {flight_873_arc.source} -> {flight_873_arc.target}" if flight_873_arc else "Flight 873 not found")
    print(f"Flight 909: arc {909}, nodes {flight_909_arc.source} -> {flight_909_arc.target}" if flight_909_arc else "Flight 909 not found")

    if not flight_855_arc or not flight_873_arc or not flight_909_arc:
        print("Some flight arcs not found!")
        return

    # Check if there's a source arc that leads to flight 855
    print("\n--- Checking path: SOURCE -> flight 855 ---")
    for src_arc in source_arcs_base1[:5]:
        print(f"Source arc {src_arc.index}: node 0 -> node {src_arc.target}")

        # Can we reach flight 855's source node from this source arc?
        target_node = src_arc.target
        flight_855_source = flight_855_arc.source

        # BFS
        visited = {target_node}
        queue = [(target_node, [src_arc], 0.0, 0.0, 1.0)]  # (node, path, duty, flight_time, duty_days)

        found = False
        while queue and not found:
            node, path, duty, flight_time, duty_days = queue.pop(0)

            if node == flight_855_source:
                print(f"  Can reach flight 855 via {len(path)} arcs")
                print(f"  Resources at flight 855 source: duty={duty:.2f}, flight={flight_time:.2f}, days={duty_days:.2f}")

                # Now trace through the full path
                # Add flight 855
                duty += flight_855_arc.get_consumption('duty_time', 0)
                flight_time += flight_855_arc.get_consumption('flight_time', 0)
                duty_days += flight_855_arc.get_consumption('duty_days', 0)
                print(f"  After flight 855: duty={duty:.2f}, flight={flight_time:.2f}, days={duty_days:.2f}")

                # Check connection to flight 873
                arr_node = flight_855_arc.target
                dep_node = flight_873_arc.source

                # Find connection arc
                for conn_arc in outgoing.get(arr_node, []):
                    if conn_arc.target == dep_node:
                        print(f"  Connection to flight 873: {conn_arc.arc_type.name}")
                        conn_duty = conn_arc.get_consumption('duty_time', 0)
                        conn_flight = conn_arc.get_consumption('flight_time', 0)
                        conn_days = conn_arc.get_consumption('duty_days', 0)
                        print(f"  Connection consumes: duty={conn_duty:.2f}, flight={conn_flight:.2f}, days={conn_days:.2f}")

                        duty += conn_duty
                        flight_time += conn_flight
                        duty_days += conn_days
                        print(f"  After connection: duty={duty:.2f}, flight={flight_time:.2f}, days={duty_days:.2f}")

                        # Check resource limits
                        if duty > 14.0:
                            print(f"  *** EXCEEDS DUTY LIMIT! ***")
                        if flight_time > 10.0:
                            print(f"  *** EXCEEDS FLIGHT LIMIT! ***")
                        if duty_days > 7.0:
                            print(f"  *** EXCEEDS DAYS LIMIT! ***")

                        # Add flight 873
                        duty += flight_873_arc.get_consumption('duty_time', 0)
                        flight_time += flight_873_arc.get_consumption('flight_time', 0)
                        duty_days += flight_873_arc.get_consumption('duty_days', 0)
                        print(f"  After flight 873: duty={duty:.2f}, flight={flight_time:.2f}, days={duty_days:.2f}")

                        if duty > 14.0:
                            print(f"  *** EXCEEDS DUTY LIMIT! ***")
                        if flight_time > 10.0:
                            print(f"  *** EXCEEDS FLIGHT LIMIT! ***")

                found = True
                break

            if len(path) > 10:
                continue

            for next_arc in outgoing.get(node, []):
                next_node = next_arc.target
                if next_node in visited:
                    continue

                new_duty = duty + next_arc.get_consumption('duty_time', 0)
                new_flight = flight_time + next_arc.get_consumption('flight_time', 0)
                new_days = duty_days + next_arc.get_consumption('duty_days', 0)

                # Clamp negative values to 0 (reset behavior)
                if new_duty < 0:
                    new_duty = 0
                if new_flight < 0:
                    new_flight = 0

                # Check limits
                if new_duty > 14.0 or new_flight > 10.0 or new_days > 7.0:
                    continue

                visited.add(next_node)
                queue.append((next_node, path + [next_arc], new_duty, new_flight, new_days))


if __name__ == "__main__":
    main()
