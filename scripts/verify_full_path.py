#!/usr/bin/env python3
"""
Verify the full path: SOURCE -> 855 -> 873 -> 909 -> SINK is feasible.
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

    network = problem.network

    # Build arc lookup
    arc_by_idx = {a.index: a for a in network.arcs}
    arcs_from = {}
    for arc in network.arcs:
        arcs_from.setdefault(arc.source, []).append(arc)

    # Get flight arcs
    flight_arcs = {a.index: a for a in network.arcs if a.arc_type == ArcType.FLIGHT}

    # Key arcs
    flight_855 = flight_arcs[855]
    flight_873 = flight_arcs[873]
    flight_909 = flight_arcs[909]

    print("Verifying path: SOURCE -> 855 -> 873 -> 909 -> SINK")
    print("=" * 70)

    # Find the source arc to flight 855
    source_arc = None
    for arc in network.arcs:
        if arc.arc_type == ArcType.SOURCE_ARC and arc.target == flight_855.source:
            if arc.get_attribute('base') == 'BASE1':
                source_arc = arc
                break

    if not source_arc:
        print("No source arc found!")
        return

    print(f"\n1. Source arc: {source_arc.index} (BASE1)")
    print(f"   From node {source_arc.source} to node {source_arc.target}")

    # Track resources
    duty = 0.0
    flight_time = 0.0
    duty_days = 1.0  # Start at day 1

    # Add source arc resources
    duty += source_arc.get_consumption('duty_time', 0)
    flight_time += source_arc.get_consumption('flight_time', 0)
    duty_days += source_arc.get_consumption('duty_days', 0)
    print(f"   Resources: duty={duty:.2f}, flight={flight_time:.2f}, days={duty_days:.2f}")

    # Flight 855
    print(f"\n2. Flight 855: node {flight_855.source} -> {flight_855.target}")
    duty += flight_855.get_consumption('duty_time', 0)
    flight_time += flight_855.get_consumption('flight_time', 0)
    duty_days += flight_855.get_consumption('duty_days', 0)
    print(f"   Resources: duty={duty:.2f}, flight={flight_time:.2f}, days={duty_days:.2f}")
    check_limits(duty, flight_time, duty_days)

    # Find connection to flight 873
    conn_to_873 = None
    for arc in arcs_from.get(flight_855.target, []):
        if arc.target == flight_873.source:
            conn_to_873 = arc
            break

    if not conn_to_873:
        print("\n*** NO CONNECTION from flight 855 to flight 873! ***")
        print(f"   Flight 855 ends at node {flight_855.target}")
        print(f"   Flight 873 starts at node {flight_873.source}")

        # What arcs go from flight 855's target?
        print(f"\n   Arcs from node {flight_855.target}:")
        for arc in arcs_from.get(flight_855.target, [])[:10]:
            print(f"     Arc {arc.index} ({arc.arc_type.name}): to node {arc.target}")
        return

    print(f"\n3. Connection: arc {conn_to_873.index} ({conn_to_873.arc_type.name})")
    print(f"   From node {conn_to_873.source} to node {conn_to_873.target}")
    conn_duty = conn_to_873.get_consumption('duty_time', 0)
    conn_flight = conn_to_873.get_consumption('flight_time', 0)
    conn_days = conn_to_873.get_consumption('duty_days', 0)
    print(f"   Arc consumes: duty={conn_duty:.2f}, flight={conn_flight:.2f}, days={conn_days:.2f}")

    duty += conn_duty
    flight_time += conn_flight
    duty_days += conn_days

    # Handle resets
    if duty < 0:
        print(f"   Duty reset! Was {duty:.2f}, clamping to 0")
        duty = 0
    if flight_time < 0:
        print(f"   Flight time reset! Was {flight_time:.2f}, clamping to 0")
        flight_time = 0

    print(f"   Resources: duty={duty:.2f}, flight={flight_time:.2f}, days={duty_days:.2f}")
    check_limits(duty, flight_time, duty_days)

    # Flight 873
    print(f"\n4. Flight 873: node {flight_873.source} -> {flight_873.target}")
    duty += flight_873.get_consumption('duty_time', 0)
    flight_time += flight_873.get_consumption('flight_time', 0)
    duty_days += flight_873.get_consumption('duty_days', 0)
    print(f"   Resources: duty={duty:.2f}, flight={flight_time:.2f}, days={duty_days:.2f}")
    check_limits(duty, flight_time, duty_days)

    # Find connection to flight 909
    conn_to_909 = None
    for arc in arcs_from.get(flight_873.target, []):
        if arc.target == flight_909.source:
            conn_to_909 = arc
            break

    if not conn_to_909:
        print("\n*** NO CONNECTION from flight 873 to flight 909! ***")
        return

    print(f"\n5. Overnight: arc {conn_to_909.index} ({conn_to_909.arc_type.name})")
    print(f"   From node {conn_to_909.source} to node {conn_to_909.target}")
    conn_duty = conn_to_909.get_consumption('duty_time', 0)
    conn_flight = conn_to_909.get_consumption('flight_time', 0)
    conn_days = conn_to_909.get_consumption('duty_days', 0)
    print(f"   Arc consumes: duty={conn_duty:.2f}, flight={conn_flight:.2f}, days={conn_days:.2f}")

    duty += conn_duty
    flight_time += conn_flight
    duty_days += conn_days

    if duty < 0:
        print(f"   Duty reset! Clamping to 0")
        duty = 0
    if flight_time < 0:
        print(f"   Flight time reset! Clamping to 0")
        flight_time = 0

    print(f"   Resources: duty={duty:.2f}, flight={flight_time:.2f}, days={duty_days:.2f}")
    check_limits(duty, flight_time, duty_days)

    # Flight 909
    print(f"\n6. Flight 909: node {flight_909.source} -> {flight_909.target}")
    duty += flight_909.get_consumption('duty_time', 0)
    flight_time += flight_909.get_consumption('flight_time', 0)
    duty_days += flight_909.get_consumption('duty_days', 0)
    print(f"   Resources: duty={duty:.2f}, flight={flight_time:.2f}, days={duty_days:.2f}")
    check_limits(duty, flight_time, duty_days)

    # Find sink arc
    sink_arc = None
    for arc in arcs_from.get(flight_909.target, []):
        if arc.arc_type == ArcType.SINK_ARC and arc.get_attribute('base') == 'BASE1':
            sink_arc = arc
            break

    if not sink_arc:
        print("\n*** NO SINK ARC from flight 909 to BASE1! ***")
        return

    print(f"\n7. Sink arc: {sink_arc.index} (BASE1)")
    print(f"   From node {sink_arc.source} to node {sink_arc.target}")

    print("\n" + "=" * 70)
    print("PATH IS FEASIBLE!")
    print(f"Final resources: duty={duty:.2f}, flight={flight_time:.2f}, days={duty_days:.2f}")


def check_limits(duty, flight_time, duty_days):
    if duty > 14.0:
        print(f"   *** EXCEEDS DUTY LIMIT (14h)! ***")
    if flight_time > 10.0:
        print(f"   *** EXCEEDS FLIGHT TIME LIMIT (10h)! ***")
    if duty_days > 7.0:
        print(f"   *** EXCEEDS DAYS LIMIT (7)! ***")


if __name__ == "__main__":
    main()
