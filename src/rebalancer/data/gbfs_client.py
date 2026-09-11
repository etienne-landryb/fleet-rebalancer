import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests
import truststore

truststore.inject_into_ssl()

logger = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 10
FEED_TIMEOUT = 30


@dataclass(frozen=True)
class StationInfo:
    station_id: str
    name: str
    lat: float
    lon: float
    capacity: int


@dataclass(frozen=True)
class StationStatus:
    station_id: str
    num_bikes_available: int
    num_docks_available: int
    is_renting: bool
    is_returning: bool
    last_reported: int


def _parse_last_reported(value: Any) -> int:
    """Normalize last_reported to Unix epoch seconds.

    GBFS v1/v2 defines this field as an integer epoch timestamp, but GBFS
    v3.0 redefined it as an ISO 8601 string. Accept both so systems on
    either spec version don't have every station row rejected.
    """
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    raise ValueError(f"Unparseable last_reported value: {value!r}")


class GBFSClient:
    """Fetch and validate GBFS feeds for a bike-share system."""

    def __init__(self, discovery_url: str, system_id: str) -> None:
        self.discovery_url = discovery_url
        self.system_id = system_id
        self._feeds: dict[str, str] = {}

    def discover(self) -> dict[str, str]:
        resp = requests.get(self.discovery_url, timeout=DISCOVERY_TIMEOUT)
        resp.raise_for_status()
        body = resp.json()

        data = body.get("data", {})
        feeds_list: list[dict[str, Any]] = []

        # GBFS v3: feeds directly under data
        if "feeds" in data:
            feeds_list = data["feeds"]
        else:
            # GBFS v1/v2: feeds nested under a language key (e.g. "en")
            for lang_data in data.values():
                if isinstance(lang_data, dict) and "feeds" in lang_data:
                    feeds_list = lang_data["feeds"]
                    break

        if not feeds_list:
            raise ValueError(
                f"No feeds found in discovery response from {self.discovery_url}"
            )

        self._feeds = {f["name"]: f["url"] for f in feeds_list}
        logger.info("Discovered %d feeds for %s", len(self._feeds), self.system_id)
        return dict(self._feeds)

    def _ensure_discovered(self) -> None:
        if not self._feeds:
            self.discover()

    def _get_feed_url(self, feed_name: str) -> str:
        self._ensure_discovered()
        url = self._feeds.get(feed_name)
        if url is None:
            available = list(self._feeds.keys())
            raise ValueError(
                f"Feed '{feed_name}' not available. Available: {available}"
            )
        return url

    def fetch_station_information(self) -> list[StationInfo]:
        url = self._get_feed_url("station_information")
        resp = requests.get(url, timeout=FEED_TIMEOUT)
        resp.raise_for_status()
        body = resp.json()

        stations: list[StationInfo] = []
        for raw in body.get("data", {}).get("stations", []):
            try:
                station = StationInfo(
                    station_id=str(raw["station_id"]),
                    name=str(raw.get("name", "")),
                    lat=float(raw["lat"]),
                    lon=float(raw["lon"]),
                    capacity=int(raw.get("capacity", 0)),
                )
                stations.append(station)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("Skipping malformed station_information row: %s", exc)

        logger.info("Fetched %d stations from station_information", len(stations))
        return stations

    def fetch_station_status(self) -> list[StationStatus]:
        url = self._get_feed_url("station_status")
        resp = requests.get(url, timeout=FEED_TIMEOUT)
        resp.raise_for_status()
        body = resp.json()

        statuses: list[StationStatus] = []
        for raw in body.get("data", {}).get("stations", []):
            try:
                status = StationStatus(
                    station_id=str(raw["station_id"]),
                    num_bikes_available=int(raw.get("num_bikes_available", 0)),
                    num_docks_available=int(raw.get("num_docks_available", 0)),
                    is_renting=bool(raw.get("is_renting", False)),
                    is_returning=bool(raw.get("is_returning", False)),
                    last_reported=_parse_last_reported(raw.get("last_reported", 0)),
                )
                statuses.append(status)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("Skipping malformed station_status row: %s", exc)

        logger.info("Fetched %d stations from station_status", len(statuses))
        return statuses
