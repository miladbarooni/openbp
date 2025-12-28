#!/usr/bin/env python3
"""
Diagnose connection gap for isolated flights.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "opencg"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opencg.parsers import KasirzadehParser
from opencg.parsers.base import ParserConfig
from opencg.config import get_data_path


def main():
    data_path = get_data_path() / "kasirzadeh" / "instance1"

    # Raw parsing (before network construction)
    parser_config = ParserConfig(verbose=False, validate=True)
    kparser = KasirzadehParser(parser_config)

    # Parse bases
    bases_file = data_path / "listOfBases.csv"
    bases = kparser._parse_bases(bases_file)
    base_airports = {b.name for b in bases if b.is_base}
    print(f"Bases: {base_airports}")

    # Parse all flights
    flights = kparser._parse_all_days(data_path)
    print(f"Total flights: {len(flights)}")

    # Find the problem flight legs
    # Flight 870 = arc from node 1742 to 1743
    # Flight 882 = arc from node 1766 to 1767

    # We need to map flight index back to leg_id
    # The flights are indexed in order, so:
    flight_870 = flights[870] if len(flights) > 870 else None
    flight_882 = flights[882] if len(flights) > 882 else None

    print(f"\nFlight 870: {flight_870}")
    print(f"Flight 882: {flight_882}")

    # For flight 870: find what departures exist at its arrival airport
    # that could follow it
    if flight_870:
        arr_airport = flight_870.arr_airport
        arr_time = kparser._datetime_to_hours(flight_870.arr_datetime)
        print(f"\n=== FLIGHT 870 ===")
        print(f"Arrives at: {arr_airport}")
        print(f"Arrival time (hours): {arr_time}")
        print(f"Arrival datetime: {flight_870.arr_datetime}")

        # Find all departures from this airport
        departures = [(f.leg_id, f.dep_airport, kparser._datetime_to_hours(f.dep_datetime), f.dep_datetime)
                      for f in flights if f.dep_airport == arr_airport]
        departures.sort(key=lambda x: x[2])

        print(f"\nDepartures from {arr_airport}:")
        for leg_id, dep_apt, dep_time, dep_dt in departures:
            conn_time = dep_time - arr_time
            status = ""
            if 0.5 <= conn_time <= 4.0:
                status = "CONNECTION"
            elif 10.0 <= conn_time <= 24.0:
                status = "OVERNIGHT"
            elif conn_time < 0:
                status = "(before arrival)"
            elif conn_time < 0.5:
                status = "(too short)"
            elif 4.0 < conn_time < 10.0:
                status = "*** GAP ***"
            else:
                status = "(too long)"
            print(f"  {leg_id}: dep={dep_time:.2f}h, conn={conn_time:.2f}h {status}")

    # For flight 882: find what arrivals exist at its departure airport
    # that could precede it
    if flight_882:
        dep_airport = flight_882.dep_airport
        dep_time = kparser._datetime_to_hours(flight_882.dep_datetime)
        print(f"\n=== FLIGHT 882 ===")
        print(f"Departs from: {dep_airport}")
        print(f"Departure time (hours): {dep_time}")
        print(f"Departure datetime: {flight_882.dep_datetime}")

        # Find all arrivals at this airport
        arrivals = [(f.leg_id, f.arr_airport, kparser._datetime_to_hours(f.arr_datetime), f.arr_datetime)
                    for f in flights if f.arr_airport == dep_airport]
        arrivals.sort(key=lambda x: x[2])

        print(f"\nArrivals at {dep_airport}:")
        for leg_id, arr_apt, arr_time, arr_dt in arrivals:
            conn_time = dep_time - arr_time
            status = ""
            if 0.5 <= conn_time <= 4.0:
                status = "CONNECTION"
            elif 10.0 <= conn_time <= 24.0:
                status = "OVERNIGHT"
            elif conn_time < 0:
                status = "(after departure)"
            elif conn_time < 0.5:
                status = "(too short)"
            elif 4.0 < conn_time < 10.0:
                status = "*** GAP ***"
            else:
                status = "(too long)"
            print(f"  {leg_id}: arr={arr_time:.2f}h, conn={conn_time:.2f}h {status}")


if __name__ == "__main__":
    main()
