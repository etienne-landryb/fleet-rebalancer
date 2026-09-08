"""Train the demand forecaster on BigQuery trip data.

Queries pre-aggregated hourly demand from BigQuery, engineers features,
trains an XGBoost model, evaluates against persistence and seasonal-naive
baselines on a temporal split, and saves the model + SHAP plots.

Usage (from Anaconda Prompt):
    conda activate rebalancer
    python scripts/train_model.py

Optional arguments:
    --start  Training window start (default: 2017-06-01)
    --end    Training window end   (default: 2018-05-01)
    --out    Output directory       (default: models/)
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rebalancer.data.bigquery_client import BigQueryClient
from rebalancer.ml.baselines import PersistenceBaseline, SeasonalNaiveBaseline
from rebalancer.ml.explain_shap import compute_shap_values, save_shap_summary
from rebalancer.ml.features import (
    FEATURE_COLS,
    TARGET_COL,
    build_features,
    temporal_train_test_split,
)
from rebalancer.ml.forecaster import XGBoostForecaster, evaluate

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train demand forecaster")
    p.add_argument("--start", default="2017-06-01", help="Training window start")
    p.add_argument("--end", default="2018-05-01", help="Training window end")
    p.add_argument("--out", default="models", help="Output directory")
    p.add_argument(
        "--station-limit",
        type=int,
        default=50,
        help="Max stations to include (controls BQ cost)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    bq = BigQueryClient()

    # --- 1. Find top stations by trip volume ---
    logger.info("Finding top %d stations ...", args.station_limit)
    station_ids = bq.get_top_station_ids(
        start_date=args.start, end_date=args.end, limit=args.station_limit
    )
    logger.info("Top stations: %s", station_ids[:5])

    # --- 2. Fetch pre-aggregated hourly demand ---
    logger.info("Querying hourly demand from %s to %s ...", args.start, args.end)
    demand_df = bq.get_hourly_demand(
        start_date=args.start, end_date=args.end, station_ids=station_ids
    )
    logger.info("Fetched %d demand rows", len(demand_df))

    if demand_df.empty:
        logger.error("No demand data returned — check date range and BQ access")
        sys.exit(1)

    # --- 3. Station metadata from BQ ---
    stations_df = bq.get_stations()
    logger.info("Fetched %d station metadata rows", len(stations_df))

    if "latitude" in stations_df.columns:
        stations_df = stations_df.rename(
            columns={"latitude": "lat", "longitude": "lon"}
        )

    # --- 4. Build features ---
    features_df = build_features(demand_df, stations_df)
    logger.info("Feature matrix: %d rows", len(features_df))

    if features_df.empty:
        logger.error("Feature matrix is empty — not enough data for lag features")
        sys.exit(1)

    # --- 5. Temporal split ---
    train_df, test_df = temporal_train_test_split(features_df)

    X_train = train_df[FEATURE_COLS]
    y_train = train_df[TARGET_COL]
    X_test = test_df[FEATURE_COLS]
    y_test = test_df[TARGET_COL]

    logger.info("Train: %d rows, Test: %d rows", len(X_train), len(X_test))
    logger.info(
        "Temporal split — train ends %s, test starts %s",
        train_df["hour_start"].max(),
        test_df["hour_start"].min(),
    )

    # --- Target diagnostics ---
    print("\n" + "=" * 60)
    print("TARGET VARIABLE DISTRIBUTION (net_flow)")
    print("=" * 60)
    for label, series in [("Train", y_train), ("Test", y_test)]:
        print(
            f"  {label:5s}: n={len(series):,}  "
            f"mean={series.mean():.4f}  std={series.std():.4f}  "
            f"min={series.min():.0f}  max={series.max():.0f}  "
            f"zero%={100 * (series == 0).mean():.1f}%"
        )

    active_mask = (y_test != 0) | (X_test["net_flow_lag1"] != 0)
    X_test_active = X_test[active_mask]
    y_test_active = y_test[active_mask]
    print(
        f"\n  Active test rows (target!=0 or lag1!=0): "
        f"{len(y_test_active):,} / {len(y_test):,} "
        f"({100 * len(y_test_active) / len(y_test):.1f}%)"
    )
    print("=" * 60)

    test_zero_pct = 100 * (y_test == 0).mean()
    if test_zero_pct > 95:
        logger.error(
            "Test set is degenerate (%.1f%% zeros) — check date range and split logic",
            test_zero_pct,
        )
        sys.exit(1)

    # --- 6. Train XGBoost ---
    xgb_model = XGBoostForecaster()
    xgb_model.fit(X_train, y_train)

    # --- 7. Evaluate against baselines ---
    persistence = PersistenceBaseline().fit(X_train, y_train)
    seasonal = SeasonalNaiveBaseline().fit(X_train, y_train)

    forecasters = {
        "Persistence (lag-1)": persistence,
        "Seasonal-naive (lag-168)": seasonal,
        "XGBoost": xgb_model,
    }

    metrics_all = evaluate(forecasters, X_test, y_test)
    metrics_active = evaluate(forecasters, X_test_active, y_test_active)

    print("\n" + "=" * 60)
    print(f"Metrics — ALL test rows ({args.start} to {args.end})")
    print(f"Top {args.station_limit} stations | Train/test split: 80/20 by time")
    print("=" * 60)
    print(metrics_all.to_string())
    print("=" * 60)

    print("\n" + "=" * 60)
    print("Metrics — ACTIVE test rows only (target!=0 or lag1!=0)")
    print(f"  ({len(y_test_active):,} of {len(y_test):,} rows)")
    print("=" * 60)
    print(metrics_active.to_string())
    print("=" * 60)

    # --- Sample predictions for sanity check ---
    print("\n" + "=" * 60)
    print("SAMPLE PREDICTIONS (5 active test rows)")
    print("=" * 60)
    sample_idx = X_test_active.head(5).index
    sample = pd.DataFrame({"actual": y_test.loc[sample_idx]})
    for name, model in forecasters.items():
        preds = model.predict(X_test)
        sample[name] = pd.Series(preds, index=X_test.index).loc[sample_idx]
    print(sample.to_string())
    print("=" * 60 + "\n")

    metrics_path = out_dir / "metrics.csv"
    metrics_active.to_csv(metrics_path)
    logger.info("Saved active-rows metrics to %s", metrics_path)

    # --- 8. Save model ---
    model_path = out_dir / "xgboost_demand.joblib"
    xgb_model.save(model_path)

    # --- 9. SHAP ---
    logger.info("Computing SHAP values ...")
    shap_values = compute_shap_values(xgb_model.model, X_test)
    save_shap_summary(shap_values, out_dir / "shap_summary.png")

    print("Done. Artifacts saved to:", out_dir.resolve())


if __name__ == "__main__":
    main()
