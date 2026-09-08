"""Fetch GBFS station info and upsert to Supabase.

Usage (from Anaconda Prompt):
    conda activate rebalancer
    python scripts/upsert_stations.py
"""

import logging
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rebalancer.config import get_settings
from rebalancer.data.gbfs_client import GBFSClient
from rebalancer.data.supabase_client import SupabaseClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main() -> None:
    settings = get_settings()

    if not settings.supabase_url or not settings.supabase_key:
        print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    gbfs = GBFSClient(
        discovery_url=settings.gbfs_primary_discovery_url,
        system_id=settings.gbfs_primary_system_id,
    )
    stations = gbfs.fetch_station_information()
    print(f"Fetched {len(stations)} stations from GBFS")

    supa = SupabaseClient(url=settings.supabase_url, key=settings.supabase_key)
    rows = [asdict(s) for s in stations]
    count = supa.upsert_stations(
        system_id=settings.gbfs_primary_system_id,
        stations=rows,
    )
    print(f"Upserted {count} rows to Supabase")

    stored = supa.get_stations(settings.gbfs_primary_system_id)
    print(f"Verified: {len(stored)} stations in Supabase")


if __name__ == "__main__":
    main()
