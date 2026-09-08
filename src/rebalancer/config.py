from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_db_url: str = ""

    # LLM (Groq)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"

    # GBFS
    gbfs_primary_discovery_url: str = "https://gbfs.citibikenyc.com/gbfs/gbfs.json"
    gbfs_primary_system_id: str = "citi-bike-nyc"

    # Weather (optional)
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"

    # Runtime
    forecast_horizon_min: int = 45
    imbalance_threshold: float = 0.30
    max_replan: int = 3
    van_count: int = 2
    van_capacity: int = 20
    shift_budget_min: int = 120
    pg_window_hours: int = 72


def get_settings() -> Settings:
    return Settings()
