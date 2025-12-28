#!/usr/bin/env python3
"""
Diagnose duty_days constraints for remaining uncovered flights.
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

    # Parse raw flights first
    parser_config = ParserConfig(verbose=False, validate=True)
    kparser = KasirzadehParser(parser_config)
    flights = kparser._parse_all_days(data_path)

    # Problem flights
    problem_flights = [855, 873]

    print("Flight details:")
    for idx in problem_flights:
        if idx < len(flights):
            f = flights[idx]
            print(f"\nFlight {idx}: {f.leg_id}")
            print(f"  Day: {f.day}")
            print(f"  Departure: {f.dep_airport} at {f.dep_date} {f.dep_time}")
            print(f"  Arrival: {f.arr_airport} at {f.arr_date} {f.arr_time}")
            print(f"  Duration: {f.duration_hours:.2f}h")

    # Check what flights can directly connect to/from these
    print("\n" + "="*70)
    print("Looking for same-day connections...")
    print("="*70)

    for idx in problem_flights:
        if idx >= len(flights):
            continue

        target = flights[idx]
        print(f"\nFlight {idx} ({target.leg_id}):")
        print(f"  Departs {target.dep_airport} at day {target.day}, {target.dep_time}")
        print(f"  Arrives {target.arr_airport} at day {target.day}, {target.arr_time}")

        # Find flights that could precede this one (same-day or day before)
        preceding = []
        for i, f in enumerate(flights):
            if f.arr_airport == target.dep_airport:
                # Check connection time
                arr_time = kparser._datetime_to_hours(f.arr_datetime)
                dep_time = kparser._datetime_to_hours(target.dep_datetime)
                conn = dep_time - arr_time

                if 0.5 <= conn <= 4.0:  # Valid connection
                    preceding.append((i, f, conn, "CONNECTION"))
                elif 4.0 < conn <= 24.0:  # Valid layover
                    preceding.append((i, f, conn, "OVERNIGHT"))

        print(f"\n  Flights that can precede (arrive at {target.dep_airport}):")
        if not preceding:
            print("    NONE!")
        else:
            for i, f, conn, conn_type in preceding[:10]:
                print(f"    Flight {i} ({f.leg_id}): {f.arr_airport} day {f.day} {f.arr_time} -> conn={conn:.2f}h ({conn_type})")

        # Find flights that could follow this one
        following = []
        for i, f in enumerate(flights):
            if f.dep_airport == target.arr_airport:
                arr_time = kparser._datetime_to_hours(target.arr_datetime)
                dep_time = kparser._datetime_to_hours(f.dep_datetime)
                conn = dep_time - arr_time

                if 0.5 <= conn <= 4.0:
                    following.append((i, f, conn, "CONNECTION"))
                elif 4.0 < conn <= 24.0:
                    following.append((i, f, conn, "OVERNIGHT"))

        print(f"\n  Flights that can follow (depart from {target.arr_airport}):")
        if not following:
            print("    NONE!")
        else:
            for i, f, conn, conn_type in following[:10]:
                print(f"    Flight {i} ({f.leg_id}): {f.dep_airport} day {f.day} {f.dep_time} -> conn={conn:.2f}h ({conn_type})")

    # Check if these flights START or END at a base
    bases_file = data_path / "listOfBases.csv"
    bases = kparser._parse_bases(bases_file)
    base_airports = {b.name for b in bases if b.is_base}
    print(f"\nBase airports: {base_airports}")

    for idx in problem_flights:
        if idx >= len(flights):
            continue
        f = flights[idx]
        print(f"\nFlight {idx}:")
        print(f"  Departs from {f.dep_airport}: {'BASE' if f.dep_airport in base_airports else 'not a base'}")
        print(f"  Arrives at {f.arr_airport}: {'BASE' if f.arr_airport in base_airports else 'not a base'}")


if __name__ == "__main__":
    main()
