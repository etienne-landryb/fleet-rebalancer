import logging
from typing import Any

from supabase import Client, create_client

logger = logging.getLogger(__name__)

UPSERT_BATCH_SIZE = 500


class SupabaseClient:
    """Thin persistence layer — station metadata and rebalancing plans only."""

    def __init__(self, url: str, key: str) -> None:
        self._client: Client = create_client(url, key)

    def upsert_stations(self, system_id: str, stations: list[dict[str, Any]]) -> int:
        rows = [
            {
                "system_id": system_id,
                "station_id": str(s["station_id"]),
                "name": s.get("name", ""),
                "lat": s.get("lat"),
                "lon": s.get("lon"),
                "capacity": s.get("capacity", 0),
            }
            for s in stations
        ]
        total = 0
        for i in range(0, len(rows), UPSERT_BATCH_SIZE):
            batch = rows[i : i + UPSERT_BATCH_SIZE]
            self._client.table("stations").upsert(batch).execute()
            total += len(batch)

        logger.info("Upserted %d stations for system %s", total, system_id)
        return total

    def get_stations(self, system_id: str) -> list[dict[str, Any]]:
        resp = (
            self._client.table("stations")
            .select("*")
            .eq("system_id", system_id)
            .execute()
        )
        return resp.data

    def insert_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.table("plans").insert(plan).execute()
        return resp.data[0] if resp.data else {}

    def get_recent_plans(self, limit: int = 10) -> list[dict[str, Any]]:
        resp = (
            self._client.table("plans")
            .select("*")
            .neq("system_id", "test")
            .not_.is_("system_id", "null")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data
