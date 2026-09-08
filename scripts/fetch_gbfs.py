"""Fetch live GBFS data for Citi Bike NYC and print a summary.

Usage (from Anaconda Prompt):
    conda activate rebalancer
    python scripts/fetch_gbfs.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rebalancer.config import get_settings
from rebalancer.data.gbfs_client import GBFSClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main() -> None:
    settings = get_settings()
    client = GBFSClient(
        discovery_url=settings.gbfs_primary_discovery_url,
        system_id=settings.gbfs_primary_system_id,
    )

    feeds = client.discover()
    print(f"\nDiscovered {len(feeds)} feeds:")
    for name, url in sorted(feeds.items()):
        print(f"  {name}: {url}")

    stations = client.fetch_station_information()
    print(f"\nStation information: {len(stations)} stations")
    if stations:
        print(f"  First: {stations[0]}")
        print(f"  Last:  {stations[-1]}")
        capacities = [s.capacity for s in stations]
        print(f"  Total capacity: {sum(capacities)} docks")

    statuses = client.fetch_station_status()
    print(f"\nStation status: {len(statuses)} stations reporting")
    if statuses:
        total_bikes = sum(s.num_bikes_available for s in statuses)
        total_docks = sum(s.num_docks_available for s in statuses)
        renting = sum(1 for s in statuses if s.is_renting)
        print(f"  Total bikes available: {total_bikes}")
        print(f"  Total docks available: {total_docks}")
        print(f"  Stations renting: {renting}/{len(statuses)}")


if __name__ == "__main__":
    main()
