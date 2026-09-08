import logging
from abc import ABC, abstractmethod

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

logger = logging.getLogger(__name__)


class DataClient(ABC):
    """Interface for historical data access — the model receives DataFrames,
    not a specific backend client."""

    @abstractmethod
    def get_hourly_demand(
        self,
        start_date: str,
        end_date: str,
        station_ids: list[str] | None = None,
    ) -> pd.DataFrame: ...

    @abstractmethod
    def get_top_station_ids(
        self, start_date: str, end_date: str, limit: int
    ) -> list[str]: ...

    @abstractmethod
    def get_stations(self) -> pd.DataFrame: ...


class BigQueryClient(DataClient):
    TRIPS_TABLE = "bigquery-public-data.new_york_citibike.citibike_trips"
    STATIONS_TABLE = "bigquery-public-data.new_york_citibike.citibike_stations"

    def __init__(self, project: str | None = None) -> None:
        self._client = bigquery.Client(project=project)

    def get_top_station_ids(
        self, start_date: str, end_date: str, limit: int
    ) -> list[str]:
        query = f"""
        SELECT start_station_id AS station_id, COUNT(*) AS cnt
        FROM `{self.TRIPS_TABLE}`
        WHERE starttime >= DATETIME(@start_date)
          AND starttime < DATETIME(@end_date)
        GROUP BY 1
        ORDER BY cnt DESC
        LIMIT {int(limit)}
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_date", "STRING", start_date),
                bigquery.ScalarQueryParameter("end_date", "STRING", end_date),
            ]
        )
        df = self._client.query(query, job_config=job_config).to_dataframe()
        ids = df["station_id"].dropna().astype(str).tolist()
        logger.info("Top %d stations by trip volume", len(ids))
        return ids

    def get_hourly_demand(
        self,
        start_date: str,
        end_date: str,
        station_ids: list[str] | None = None,
    ) -> pd.DataFrame:
        station_filter = ""
        params = [
            bigquery.ScalarQueryParameter("start_date", "STRING", start_date),
            bigquery.ScalarQueryParameter("end_date", "STRING", end_date),
        ]
        if station_ids is not None:
            station_filter = "AND {col} IN UNNEST(@station_ids)"
            params.append(
                bigquery.ArrayQueryParameter("station_ids", "INT64", station_ids)
            )

        pickups_sql = f"""
        SELECT
            CAST(start_station_id AS STRING) AS station_id,
            DATETIME_TRUNC(starttime, HOUR) AS hour_start,
            COUNT(*) AS pickups
        FROM `{self.TRIPS_TABLE}`
        WHERE starttime >= DATETIME(@start_date)
          AND starttime < DATETIME(@end_date)
          {station_filter.format(col="start_station_id")}
        GROUP BY 1, 2
        """

        dropoffs_sql = f"""
        SELECT
            CAST(end_station_id AS STRING) AS station_id,
            DATETIME_TRUNC(stoptime, HOUR) AS hour_start,
            COUNT(*) AS dropoffs
        FROM `{self.TRIPS_TABLE}`
        WHERE starttime >= DATETIME(@start_date)
          AND starttime < DATETIME(@end_date)
          {station_filter.format(col="end_station_id")}
        GROUP BY 1, 2
        """

        job_config = bigquery.QueryJobConfig(query_parameters=params)

        pickups_df = self._client.query(
            pickups_sql, job_config=job_config
        ).to_dataframe()
        logger.info("Fetched %d pickup aggregates from BigQuery", len(pickups_df))

        dropoffs_df = self._client.query(
            dropoffs_sql, job_config=job_config
        ).to_dataframe()
        logger.info("Fetched %d dropoff aggregates from BigQuery", len(dropoffs_df))

        pickups_df["station_id"] = pickups_df["station_id"].astype(str)
        dropoffs_df["station_id"] = dropoffs_df["station_id"].astype(str)
        pickups_df["hour_start"] = pd.to_datetime(pickups_df["hour_start"])
        dropoffs_df["hour_start"] = pd.to_datetime(dropoffs_df["hour_start"])

        demand = pickups_df.merge(
            dropoffs_df, on=["station_id", "hour_start"], how="outer"
        )
        demand["pickups"] = demand["pickups"].fillna(0).astype(int)
        demand["dropoffs"] = demand["dropoffs"].fillna(0).astype(int)
        demand["net_flow"] = demand["dropoffs"] - demand["pickups"]

        logger.info(
            "Hourly demand: %d rows, %d stations, %s to %s",
            len(demand),
            demand["station_id"].nunique(),
            demand["hour_start"].min(),
            demand["hour_start"].max(),
        )
        return demand.sort_values(["station_id", "hour_start"]).reset_index(drop=True)

    def get_stations(self) -> pd.DataFrame:
        query = f"""
        SELECT station_id, name, latitude, longitude, capacity
        FROM `{self.STATIONS_TABLE}`
        """
        df = self._client.query(query).to_dataframe()
        logger.info("Fetched %d stations from BigQuery", len(df))
        return df
