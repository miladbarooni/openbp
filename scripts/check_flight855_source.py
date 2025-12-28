#!/usr/bin/env python3
"""
Check which source arcs can directly reach flight 855.
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

    # Get flight 855
    flight_855_arc = None
    for arc in network.arcs:
        if arc.arc_type == ArcType.FLIGHT and arc.index == 855:
            flight_855_arc = arc
            break

    if not flight_855_arc:
        print("Flight 855 not found!")
        return

    print(f"Flight 855: node {flight_855_arc.source} -> {flight_855_arc.target}")

    # Find incoming arcs to flight 855's source node
    incoming = [a for a in network.arcs if a.target == flight_855_arc.source]
    print(f"\nIncoming arcs to node {flight_855_arc.source}:")
    for arc in incoming:
        print(f"  Arc {arc.index}: from node {arc.source}, type={arc.arc_type.name}")
        if arc.arc_type == ArcType.SOURCE_ARC:
            base = arc.get_attribute('base')
            print(f"    This is a SOURCE_ARC from {base}!")

    # Check if there's a direct source arc
    direct_source = [a for a in incoming if a.arc_type == ArcType.SOURCE_ARC]
    if direct_source:
        print(f"\n*** There IS a direct source arc to flight 855! ***")
        for arc in direct_source:
            print(f"  Arc {arc.index}: base={arc.get_attribute('base')}")
    else:
        print(f"\nNo direct source arc - flight 855 must be reached via connections/overnights")

    # Check what those incoming arcs lead to
    print("\n--- Tracing back from flight 855 ---")
    for arc in incoming[:5]:
        print(f"\nArc {arc.index} ({arc.arc_type.name}) from node {arc.source}:")
        # What leads to this node?
        prev_incoming = [a for a in network.arcs if a.target == arc.source][:5]
        for prev_arc in prev_incoming:
            print(f"  <- Arc {prev_arc.index} ({prev_arc.arc_type.name}) from node {prev_arc.source}")
            if prev_arc.arc_type == ArcType.SOURCE_ARC:
                print(f"     *** SOURCE from {prev_arc.get_attribute('base')}! ***")


if __name__ == "__main__":
    main()
