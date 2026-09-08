"""Query BigQuery for Citi Bike trip counts and print a summary.

Requires gcloud CLI authenticated:
    gcloud auth application-default login

Usage (from Anaconda Prompt):
    conda activate rebalancer
    python scripts/query_bigquery.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rebalancer.data.bigquery_client import BigQueryClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main() -> None:
    client = BigQueryClient()

    print("Querying top 10 stations by trip count (Oct 2023)...\n")
    df = client.get_trip_counts_by_station(
        start_date="2023-10-01",
        end_date="2023-11-01",
        limit=10,
    )
    print(df.to_string(index=False))
    print(f"\nTotal trips across top 10: {df['trip_count'].sum():,}")

    print("\nFetching station metadata from BigQuery...")
    stations_df = client.get_stations()
    print(f"Station count: {len(stations_df)}")
    if not stations_df.empty:
        print(stations_df.head().to_string(index=False))


if __name__ == "__main__":
    main()
