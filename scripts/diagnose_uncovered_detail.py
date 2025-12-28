#!/usr/bin/env python3
"""
Detailed diagnosis of isolated flights in the network.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "opencg"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opencg.parsers import KasirzadehParser
from opencg.parsers.base import ParserConfig
from opencg.config import get_data_path
from opencg.core.arc import ArcType
from opencg.core.node import NodeType


def main():
    data_path = get_data_path() / "kasirzadeh" / "instance1"

    # Configure parser
    parser_config = ParserConfig(
        verbose=False,
        validate=True,
        options={
            'min_connection_time': 0.5,
            'max_connection_time': 4.0,
            'min_layover_time': 10.0,
            'max_layover_time': 24.0,
            'max_duty_time': 14.0,
            'max_pairing_days': 5,
        }
    )
    kparser = KasirzadehParser(parser_config)
    problem = kparser.parse(data_path)

    network = problem.network

    # Find problem flights
    problem_flights = [870, 882]

    # Build adjacency info
    outgoing = {}  # node -> list of (arc_idx, target_node, arc_type)
    incoming = {}  # node -> list of (arc_idx, source_node, arc_type)

    for arc in network.arcs:
        s, t = arc.source, arc.target
        outgoing.setdefault(s, []).append((arc.index, t, arc.arc_type))
        incoming.setdefault(t, []).append((arc.index, s, arc.arc_type))

    # Find flight arcs
    flight_arcs = {}
    for arc in network.arcs:
        if arc.arc_type == ArcType.FLIGHT:
            flight_arcs[arc.index] = arc

    # Find sink nodes
    sink_nodes = set()
    for i in range(network.num_nodes):
        node = network.get_node(i)
        if node and node.node_type == NodeType.SINK:
            sink_nodes.add(i)

    print("=" * 70)
    print("Detailed Flight Analysis")
    print("=" * 70)

    for flight_idx in problem_flights:
        print(f"\n=== FLIGHT {flight_idx} ===")

        if flight_idx not in flight_arcs:
            print("  Not found")
            continue

        arc = flight_arcs[flight_idx]
        src, tgt = arc.source, arc.target

        print(f"Arc: node {src} -> node {tgt}")

        # What can reach the source node?
        print(f"\n  Incoming to node {src} (flight source):")
        inc = incoming.get(src, [])
        if not inc:
            print("    NONE - this flight has no incoming connections!")
        else:
            for arc_idx, from_node, arc_type in inc[:10]:
                print(f"    Arc {arc_idx}: from node {from_node}, type={arc_type.name}")
            if len(inc) > 10:
                print(f"    ... and {len(inc)-10} more")

        # What can the target node reach?
        print(f"\n  Outgoing from node {tgt} (flight target):")
        out = outgoing.get(tgt, [])
        if not out:
            print("    NONE - this flight has no outgoing connections!")
        else:
            for arc_idx, to_node, arc_type in out[:10]:
                print(f"    Arc {arc_idx}: to node {to_node}, type={arc_type.name}")
            if len(out) > 10:
                print(f"    ... and {len(out)-10} more")

        # For flight 870, check if any outgoing eventually reaches a sink
        if flight_idx == 870:
            print(f"\n  Checking if any path from node {tgt} reaches a sink...")
            visited = {tgt}
            frontier = [tgt]
            depth = 0
            found_sink = False
            while frontier and depth < 100:
                depth += 1
                next_frontier = []
                for n in frontier:
                    for _, to_node, at in outgoing.get(n, []):
                        if to_node in sink_nodes:
                            print(f"    Found sink node {to_node} at depth {depth}")
                            found_sink = True
                        elif at == ArcType.SINK_ARC:
                            print(f"    Found SINK_ARC at depth {depth} to node {to_node}")
                            found_sink = True
                        if to_node not in visited:
                            visited.add(to_node)
                            next_frontier.append(to_node)
                frontier = next_frontier
            if not found_sink:
                print(f"    NO path to any sink! Searched {len(visited)} nodes")

        # For flight 882, check if any base can reach its source
        if flight_idx == 882:
            print(f"\n  Checking if any source arc reaches node {src}...")
            # Find source arcs
            source_arcs = [a for a in network.arcs if a.arc_type == ArcType.SOURCE_ARC]
            print(f"    Found {len(source_arcs)} source arcs total")

            # BFS from each source arc
            for src_arc in source_arcs[:5]:  # Check first 5
                base = src_arc.get_attribute('base')
                start = src_arc.target  # Where the source arc leads to
                print(f"    Checking from {base} (source arc -> node {start})...")

                visited = {start}
                frontier = [start]
                depth = 0
                found = False
                while frontier and depth < 100:
                    depth += 1
                    next_frontier = []
                    for n in frontier:
                        for _, to_node, at in outgoing.get(n, []):
                            if to_node == src:
                                print(f"      FOUND at depth {depth}")
                                found = True
                                break
                            if to_node not in visited:
                                visited.add(to_node)
                                next_frontier.append(to_node)
                        if found:
                            break
                    if found:
                        break
                    frontier = next_frontier
                if not found:
                    print(f"      Not reachable from this source (searched {len(visited)} nodes)")


if __name__ == "__main__":
    main()
