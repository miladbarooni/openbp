#!/usr/bin/env python3
"""
Diagnose connections from AIR15 back to bases.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "opencg"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opencg.parsers import KasirzadehParser
from opencg.parsers.base import ParserConfig
from opencg.config import get_data_path


def main():
    data_path = get_data_path() / "kasirzadeh" / "instance1"

    parser_config = ParserConfig(verbose=False, validate=True)
    kparser = KasirzadehParser(parser_config)

    # Parse all flights
    flights = kparser._parse_all_days(data_path)

    # Get bases
    bases_file = data_path / "listOfBases.csv"
    bases = kparser._parse_bases(bases_file)
    base_airports = {b.name for b in bases if b.is_base}

    # Flight 873 arrives at AIR15 on day 27 at 03:00
    target_airport = "AIR15"
    target_time = kparser._datetime_to_hours(flights[873].arr_datetime)
    print(f"Flight 873 arrives at {target_airport} at hour {target_time:.2f}")
    print(f"Looking for paths back to bases: {base_airports}")
    print()

    # Find all flights departing from AIR15 after flight 873 arrives
    departures = []
    for i, f in enumerate(flights):
        if f.dep_airport == target_airport:
            dep_time = kparser._datetime_to_hours(f.dep_datetime)
            conn_time = dep_time - target_time
            if 0.5 <= conn_time <= 24.0:  # Valid connection or overnight
                departures.append((i, f, conn_time))

    print(f"Flights departing from {target_airport} with valid connection:")
    for i, f, conn in departures:
        conn_type = "CONNECTION" if conn <= 4.0 else "OVERNIGHT"
        dest_type = "BASE" if f.arr_airport in base_airports else ""
        print(f"  Flight {i} ({f.leg_id}): {f.dep_airport} -> {f.arr_airport} "
              f"day {f.day} {f.dep_time}, conn={conn:.2f}h ({conn_type}) {dest_type}")

    # Check if any of these can eventually reach BASE1
    print()
    print("Tracing paths to BASE1:")
    print("-" * 70)

    visited = set()
    queue = []

    # Initialize with departures from AIR15
    for i, f, conn in departures:
        arr_time = kparser._datetime_to_hours(f.arr_datetime)
        queue.append((i, f, [(i, f)], arr_time))

    while queue:
        idx, flight, path, arr_time = queue.pop(0)

        if flight.arr_airport == "BASE1":
            print(f"\nFound path to BASE1 with {len(path)} flights:")
            for pi, pf in path:
                print(f"  Flight {pi} ({pf.leg_id}): {pf.dep_airport} -> {pf.arr_airport}")
            continue

        if len(path) >= 5:  # Limit path length
            continue

        key = (flight.arr_airport, int(arr_time))
        if key in visited:
            continue
        visited.add(key)

        # Find next flights
        for j, next_f in enumerate(flights):
            if next_f.dep_airport == flight.arr_airport:
                next_dep = kparser._datetime_to_hours(next_f.dep_datetime)
                conn = next_dep - arr_time
                if 0.5 <= conn <= 24.0:
                    next_arr = kparser._datetime_to_hours(next_f.arr_datetime)
                    queue.append((j, next_f, path + [(j, next_f)], next_arr))

    # Check if the issue is that AIR15 is isolated
    print()
    print(f"Checking all flights that involve {target_airport}:")
    arrivals_at = [(i, f) for i, f in enumerate(flights) if f.arr_airport == target_airport]
    departures_from = [(i, f) for i, f in enumerate(flights) if f.dep_airport == target_airport]

    print(f"  Arrivals at {target_airport}: {len(arrivals_at)}")
    for i, f in arrivals_at:
        print(f"    Flight {i} ({f.leg_id}): from {f.dep_airport} day {f.day}")

    print(f"\n  Departures from {target_airport}: {len(departures_from)}")
    for i, f in departures_from:
        print(f"    Flight {i} ({f.leg_id}): to {f.arr_airport} day {f.day}")


if __name__ == "__main__":
    main()
