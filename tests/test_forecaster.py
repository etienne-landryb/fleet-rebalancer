import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from rebalancer.ml.forecaster import Forecaster, XGBoostForecaster, evaluate


def _make_train_data(n: int = 200) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.RandomState(42)
    X = pd.DataFrame(
        {
            "hour": rng.randint(0, 24, n),
            "day_of_week": rng.randint(0, 7, n),
            "is_weekend": rng.randint(0, 2, n),
            "is_holiday": np.zeros(n, dtype=int),
            "capacity": rng.choice([20, 30, 40], n),
            "pickups_lag1": rng.randint(0, 20, n),
            "dropoffs_lag1": rng.randint(0, 20, n),
            "net_flow_lag1": rng.randint(-10, 10, n),
            "pickups_lag24": rng.randint(0, 20, n),
            "dropoffs_lag24": rng.randint(0, 20, n),
            "net_flow_lag24": rng.randint(-10, 10, n),
            "pickups_lag168": rng.randint(0, 20, n),
            "dropoffs_lag168": rng.randint(0, 20, n),
            "net_flow_lag168": rng.randint(-10, 10, n),
        }
    )
    y = pd.Series(rng.randint(-10, 10, n).astype(float), name="net_flow")
    return X, y


class TestXGBoostForecaster:
    def test_implements_forecaster(self):
        assert isinstance(XGBoostForecaster(), Forecaster)

    def test_fit_predict(self):
        X, y = _make_train_data()
        model = XGBoostForecaster(n_estimators=10)
        model.fit(X, y)
        preds = model.predict(X)
        assert len(preds) == len(X)
        assert preds.dtype == np.float32 or preds.dtype == np.float64

    def test_fit_returns_self(self):
        X, y = _make_train_data(n=50)
        model = XGBoostForecaster(n_estimators=5)
        result = model.fit(X, y)
        assert result is model

    def test_save_load_roundtrip(self):
        X, y = _make_train_data(n=50)
        model = XGBoostForecaster(n_estimators=5)
        model.fit(X, y)
        original_preds = model.predict(X)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.joblib"
            model.save(path)
            assert path.exists()

            loaded = XGBoostForecaster.load(path)
            loaded_preds = loaded.predict(X)
            np.testing.assert_array_almost_equal(original_preds, loaded_preds)
            assert loaded.feature_names == list(X.columns)


class TestEvaluate:
    def test_returns_metrics_for_all_models(self):
        X, y = _make_train_data(n=100)
        model = XGBoostForecaster(n_estimators=5).fit(X, y)

        from rebalancer.ml.baselines import PersistenceBaseline

        metrics = evaluate(
            {"XGBoost": model, "Persistence": PersistenceBaseline()},
            X,
            y,
        )
        assert "MAE" in metrics.columns
        assert "RMSE" in metrics.columns
        assert "XGBoost" in metrics.index
        assert "Persistence" in metrics.index

    def test_perfect_model_has_zero_error(self):
        X = pd.DataFrame(
            {"net_flow_lag1": [1.0, 2.0, 3.0], "net_flow_lag168": [1.0, 2.0, 3.0]}
        )
        y = pd.Series([1.0, 2.0, 3.0])

        from rebalancer.ml.baselines import PersistenceBaseline

        metrics = evaluate({"Persistence": PersistenceBaseline()}, X, y)
        assert metrics.loc["Persistence", "MAE"] == 0.0
        assert metrics.loc["Persistence", "RMSE"] == 0.0
