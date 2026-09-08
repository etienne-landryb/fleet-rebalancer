import logging

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

logger = logging.getLogger(__name__)

DEMAND_COLS = ["pickups", "dropoffs", "net_flow"]
LAG_HOURS = [1, 24, 168]

FEATURE_COLS = [
    "hour",
    "day_of_week",
    "is_weekend",
    "is_holiday",
    "capacity",
    "pickups_lag1",
    "dropoffs_lag1",
    "net_flow_lag1",
    "pickups_lag24",
    "dropoffs_lag24",
    "net_flow_lag24",
    "pickups_lag168",
    "dropoffs_lag168",
    "net_flow_lag168",
]
TARGET_COL = "net_flow"


def build_hourly_demand(demand_df: pd.DataFrame) -> pd.DataFrame:
    """Fill gaps in pre-aggregated hourly demand so every station has
    a row for every hour in the observed window."""
    df = demand_df.copy()
    df["station_id"] = df["station_id"].astype(str)
    df["hour_start"] = pd.to_datetime(df["hour_start"])

    all_stations = sorted(df["station_id"].unique())
    all_hours = pd.date_range(
        start=df["hour_start"].min(),
        end=df["hour_start"].max(),
        freq="h",
    )

    idx = pd.MultiIndex.from_product(
        [all_stations, all_hours], names=["station_id", "hour_start"]
    )
    grid = pd.DataFrame(index=idx).reset_index()
    grid = grid.merge(df, on=["station_id", "hour_start"], how="left")
    grid["pickups"] = grid["pickups"].fillna(0).astype(int)
    grid["dropoffs"] = grid["dropoffs"].fillna(0).astype(int)
    grid["net_flow"] = grid["dropoffs"] - grid["pickups"]

    logger.info(
        "Built hourly demand grid: %d rows, %d stations, %s to %s",
        len(grid),
        grid["station_id"].nunique(),
        grid["hour_start"].min(),
        grid["hour_start"].max(),
    )
    return grid.sort_values(["station_id", "hour_start"]).reset_index(drop=True)


def add_calendar_features(demand_df: pd.DataFrame) -> pd.DataFrame:
    df = demand_df.copy()
    df["hour"] = df["hour_start"].dt.hour
    df["day_of_week"] = df["hour_start"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)

    date_range = (df["hour_start"].min(), df["hour_start"].max())
    cal = USFederalHolidayCalendar()
    holidays = set(cal.holidays(start=date_range[0], end=date_range[1]).date)
    df["is_holiday"] = df["hour_start"].dt.date.isin(holidays).astype(int)

    return df


def add_lag_features(
    demand_df: pd.DataFrame, lags: list[int] | None = None
) -> pd.DataFrame:
    if lags is None:
        lags = LAG_HOURS
    df = demand_df.sort_values(["station_id", "hour_start"]).copy()

    for lag in lags:
        for col in DEMAND_COLS:
            df[f"{col}_lag{lag}"] = df.groupby("station_id")[col].shift(lag)

    return df


def add_station_features(
    demand_df: pd.DataFrame, stations_df: pd.DataFrame
) -> pd.DataFrame:
    stations = stations_df[["station_id", "capacity"]].copy()
    stations["station_id"] = stations["station_id"].astype(str)
    df = demand_df.copy()
    df["station_id"] = df["station_id"].astype(str)
    return df.merge(stations, on="station_id", how="left")


def build_features(
    demand_df: pd.DataFrame,
    stations_df: pd.DataFrame,
    lags: list[int] | None = None,
) -> pd.DataFrame:
    """Full pipeline: pre-aggregated demand -> feature matrix ready for modeling."""
    demand = build_hourly_demand(demand_df)
    demand = add_calendar_features(demand)
    demand = add_lag_features(demand, lags)
    demand = add_station_features(demand, stations_df)
    demand = demand.dropna(subset=[c for c in demand.columns if "lag" in c])
    logger.info("Feature matrix: %d rows after dropping incomplete lags", len(demand))
    return demand.reset_index(drop=True)


def temporal_train_test_split(
    df: pd.DataFrame,
    time_col: str = "hour_start",
    test_fraction: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by time — train on earlier data, test on later."""
    cutoff = df[time_col].quantile(1 - test_fraction)
    train = df[df[time_col] < cutoff].copy()
    test = df[df[time_col] >= cutoff].copy()
    logger.info(
        "Temporal split: train=%d rows (before %s), test=%d rows",
        len(train),
        cutoff,
        len(test),
    )
    return train, test
