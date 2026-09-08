import numpy as np
import pandas as pd

from rebalancer.ml.features import (
    TARGET_COL,
    add_calendar_features,
    add_lag_features,
    add_station_features,
    build_features,
    build_hourly_demand,
    temporal_train_test_split,
)


def _make_demand(n_days: int = 10, stations: list[str] | None = None) -> pd.DataFrame:
    """Generate pre-aggregated hourly demand data for testing."""
    if stations is None:
        stations = ["A", "B", "C"]
    rng = np.random.RandomState(42)
    rows = []
    base = pd.Timestamp("2023-10-01")
    for station in stations:
        for day in range(n_days):
            for hour in range(24):
                ts = base + pd.Timedelta(days=day, hours=hour)
                pickups = rng.randint(0, 10)
                dropoffs = rng.randint(0, 10)
                rows.append(
                    {
                        "station_id": station,
                        "hour_start": ts,
                        "pickups": pickups,
                        "dropoffs": dropoffs,
                        "net_flow": dropoffs - pickups,
                    }
                )
    return pd.DataFrame(rows)


def _make_stations(stations: list[str] | None = None) -> pd.DataFrame:
    if stations is None:
        stations = ["A", "B", "C"]
    return pd.DataFrame(
        {
            "station_id": stations,
            "capacity": [20, 30, 25],
        }
    )


class TestBuildHourlyDemand:
    def test_output_columns(self):
        demand = _make_demand(n_days=2)
        result = build_hourly_demand(demand)
        assert "station_id" in result.columns
        assert "hour_start" in result.columns
        assert "pickups" in result.columns
        assert "dropoffs" in result.columns
        assert "net_flow" in result.columns

    def test_net_flow_is_dropoffs_minus_pickups(self):
        demand = _make_demand(n_days=2)
        result = build_hourly_demand(demand)
        np.testing.assert_array_equal(
            result["net_flow"].values,
            (result["dropoffs"] - result["pickups"]).values,
        )

    def test_complete_index(self):
        demand = _make_demand(n_days=2, stations=["X", "Y"])
        result = build_hourly_demand(demand)
        n_stations = result["station_id"].nunique()
        n_hours = result["hour_start"].nunique()
        assert len(result) == n_stations * n_hours

    def test_fills_gaps_with_zero(self):
        demand = pd.DataFrame(
            {
                "station_id": ["A", "A", "B"],
                "hour_start": pd.to_datetime(
                    ["2023-10-01 00:00", "2023-10-01 02:00", "2023-10-01 01:00"]
                ),
                "pickups": [5, 3, 2],
                "dropoffs": [2, 1, 4],
                "net_flow": [-3, -2, 2],
            }
        )
        result = build_hourly_demand(demand)
        assert len(result) == 2 * 3  # 2 stations x 3 hours
        filled = result[
            (result["station_id"] == "A")
            & (result["hour_start"] == pd.Timestamp("2023-10-01 01:00"))
        ]
        assert filled.iloc[0]["pickups"] == 0
        assert filled.iloc[0]["dropoffs"] == 0


class TestCalendarFeatures:
    def test_adds_calendar_columns(self):
        demand = _make_demand(n_days=2)
        result = add_calendar_features(build_hourly_demand(demand))
        assert "hour" in result.columns
        assert "day_of_week" in result.columns
        assert "is_weekend" in result.columns
        assert "is_holiday" in result.columns

    def test_weekend_flag(self):
        demand = _make_demand(n_days=10)
        result = add_calendar_features(build_hourly_demand(demand))
        weekend_rows = result[result["day_of_week"].isin([5, 6])]
        assert (weekend_rows["is_weekend"] == 1).all()
        weekday_rows = result[~result["day_of_week"].isin([5, 6])]
        assert (weekday_rows["is_weekend"] == 0).all()


class TestLagFeatures:
    def test_adds_lag_columns(self):
        demand = _make_demand(n_days=10)
        result = add_lag_features(build_hourly_demand(demand), lags=[1, 24])
        assert "net_flow_lag1" in result.columns
        assert "pickups_lag24" in result.columns

    def test_lag1_is_previous_hour(self):
        demand = _make_demand(n_days=3, stations=["A"])
        grid = build_hourly_demand(demand)
        grid = grid.sort_values(["station_id", "hour_start"]).reset_index(drop=True)
        result = add_lag_features(grid, lags=[1])
        valid = result.dropna(subset=["net_flow_lag1"])
        assert len(valid) == len(grid) - 1
        np.testing.assert_array_equal(
            valid["net_flow_lag1"].values,
            grid["net_flow"].iloc[:-1].values,
        )


class TestStationFeatures:
    def test_merges_capacity(self):
        demand = _make_demand(n_days=2)
        stations = _make_stations()
        result = add_station_features(build_hourly_demand(demand), stations)
        assert "capacity" in result.columns
        assert result["capacity"].notna().all()


class TestBuildFeatures:
    def test_full_pipeline_produces_feature_cols(self):
        demand = _make_demand(n_days=10)
        stations = _make_stations()
        result = build_features(demand, stations, lags=[1, 24])
        for col in ["hour", "day_of_week", "is_weekend", "capacity"]:
            assert col in result.columns
        assert TARGET_COL in result.columns

    def test_no_nans_in_lag_columns(self):
        demand = _make_demand(n_days=10)
        stations = _make_stations()
        result = build_features(demand, stations, lags=[1, 24])
        lag_cols = [c for c in result.columns if "lag" in c]
        assert result[lag_cols].notna().all().all()


class TestTemporalSplit:
    def test_train_before_test(self):
        demand = _make_demand(n_days=10)
        stations = _make_stations()
        features = build_features(demand, stations, lags=[1, 24])
        train, test = temporal_train_test_split(features)
        assert train["hour_start"].max() <= test["hour_start"].min()

    def test_no_overlap(self):
        demand = _make_demand(n_days=10)
        stations = _make_stations()
        features = build_features(demand, stations, lags=[1, 24])
        train, test = temporal_train_test_split(features)
        overlap = set(train.index) & set(test.index)
        assert len(overlap) == 0

    def test_approximate_split_ratio(self):
        demand = _make_demand(n_days=30)
        stations = _make_stations()
        features = build_features(demand, stations, lags=[1, 24])
        train, test = temporal_train_test_split(features, test_fraction=0.2)
        ratio = len(test) / (len(train) + len(test))
        assert 0.1 < ratio < 0.35
