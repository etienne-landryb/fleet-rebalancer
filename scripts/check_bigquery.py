"""Diagnose available date range in the BigQuery citibike_trips table."""

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from google.cloud import bigquery

TABLE = "bigquery-public-data.new_york_citibike.citibike_trips"


def main() -> None:
    client = bigquery.Client()

    queries = [
        ("Total trips", f"SELECT COUNT(*) AS total_trips FROM `{TABLE}`"),
        (
            "Date range",
            f"SELECT MIN(starttime) AS earliest, MAX(starttime) AS latest FROM `{TABLE}`",
        ),
        (
            "Trips since 2022",
            f"SELECT COUNT(*) AS cnt FROM `{TABLE}` WHERE starttime >= '2022-01-01'",
        ),
    ]

    for label, sql in queries:
        print(f"\n--- {label} ---")
        print(f"  {sql}")
        try:
            result = client.query(sql).to_dataframe()
            print(result.to_string(index=False))
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    main()
