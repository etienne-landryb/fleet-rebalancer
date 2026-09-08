import numpy as np
import pandas as pd

from rebalancer.ml.baselines import PersistenceBaseline, SeasonalNaiveBaseline
from rebalancer.ml.forecaster import Forecaster


def _make_test_data() -> tuple[pd.DataFrame, pd.Series]:
    X = pd.DataFrame(
        {
            "net_flow_lag1": [3.0, -2.0, 5.0, 0.0],
            "net_flow_lag168": [1.0, -1.0, 4.0, 2.0],
            "pickups_lag1": [10, 8, 12, 5],
            "dropoffs_lag1": [13, 6, 17, 5],
        }
    )
    y = pd.Series([2.0, -3.0, 6.0, 1.0], name="net_flow")
    return X, y


class TestPersistenceBaseline:
    def test_implements_forecaster(self):
        assert isinstance(PersistenceBaseline(), Forecaster)

    def test_predicts_lag1(self):
        X, y = _make_test_data()
        model = PersistenceBaseline().fit(X, y)
        preds = model.predict(X)
        np.testing.assert_array_equal(preds, X["net_flow_lag1"].values)

    def test_fit_returns_self(self):
        X, y = _make_test_data()
        model = PersistenceBaseline()
        result = model.fit(X, y)
        assert result is model


class TestSeasonalNaiveBaseline:
    def test_implements_forecaster(self):
        assert isinstance(SeasonalNaiveBaseline(), Forecaster)

    def test_predicts_lag168(self):
        X, y = _make_test_data()
        model = SeasonalNaiveBaseline().fit(X, y)
        preds = model.predict(X)
        np.testing.assert_array_equal(preds, X["net_flow_lag168"].values)
