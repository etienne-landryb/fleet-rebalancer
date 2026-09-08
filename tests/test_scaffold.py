from rebalancer import __version__
from rebalancer.config import Settings


def test_version():
    assert __version__ == "0.1.0"


def test_settings_defaults():
    settings = Settings()
    assert settings.gbfs_primary_system_id == "citi-bike-nyc"
    assert settings.forecast_horizon_min == 45
    assert settings.imbalance_threshold == 0.3
    assert settings.max_replan == 3
    assert settings.van_count == 2
    assert settings.van_capacity == 20
    assert settings.shift_budget_min == 120
