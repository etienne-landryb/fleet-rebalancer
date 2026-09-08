import numpy as np
import pandas as pd

from rebalancer.ml.forecaster import Forecaster


class PersistenceBaseline(Forecaster):
    """Predict that the next hour's demand equals the previous hour's."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "PersistenceBaseline":
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return X["net_flow_lag1"].values.astype(float)


class SeasonalNaiveBaseline(Forecaster):
    """Predict that demand equals the same hour one week ago."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "SeasonalNaiveBaseline":
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return X["net_flow_lag168"].values.astype(float)
