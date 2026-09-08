import logging
from abc import ABC, abstractmethod
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

logger = logging.getLogger(__name__)


class Forecaster(ABC):
    """Interface for demand forecasters — the graph receives predictions,
    not a specific model."""

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "Forecaster": ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray: ...


class XGBoostForecaster(Forecaster):
    def __init__(self, **params: object) -> None:
        defaults: dict[str, object] = {
            "n_estimators": 200,
            "max_depth": 6,
            "learning_rate": 0.1,
            "objective": "reg:squarederror",
            "random_state": 42,
        }
        defaults.update(params)
        self.model = xgb.XGBRegressor(**defaults)
        self.feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "XGBoostForecaster":
        self.feature_names = list(X.columns)
        self.model.fit(X, y)
        logger.info("Trained XGBoost on %d rows, %d features", len(X), len(X.columns))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict(X)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"model": self.model, "feature_names": self.feature_names},
            path,
        )
        logger.info("Saved model to %s", path)

    @classmethod
    def load(cls, path: str | Path) -> "XGBoostForecaster":
        data = joblib.load(path)
        instance = cls()
        instance.model = data["model"]
        instance.feature_names = data["feature_names"]
        logger.info("Loaded model from %s", path)
        return instance


def evaluate(
    forecasters: dict[str, Forecaster],
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> pd.DataFrame:
    """Evaluate multiple forecasters and return a metrics table."""
    from sklearn.metrics import mean_absolute_error, root_mean_squared_error

    rows = []
    for name, model in forecasters.items():
        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        rmse = root_mean_squared_error(y_test, preds)
        rows.append({"model": name, "MAE": round(mae, 4), "RMSE": round(rmse, 4)})

    return pd.DataFrame(rows).set_index("model")
