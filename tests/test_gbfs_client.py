import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from rebalancer.data.gbfs_client import GBFSClient, StationInfo, StationStatus

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(fixture_path: Path | None = None, data: dict | None = None):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    if fixture_path is not None:
        with open(fixture_path) as f:
            resp.json.return_value = json.load(f)
    elif data is not None:
        resp.json.return_value = data
    return resp


class TestDiscover:
    @patch("rebalancer.data.gbfs_client.requests.get")
    def test_discovers_feeds_from_v2_format(self, mock_get):
        mock_get.return_value = _mock_response(FIXTURES / "sample_discovery.json")
        client = GBFSClient("https://example.com/gbfs.json", "test")
        feeds = client.discover()

        assert "station_information" in feeds
        assert "station_status" in feeds
        assert len(feeds) == 3

    @patch("rebalancer.data.gbfs_client.requests.get")
    def test_discovers_feeds_from_v3_format(self, mock_get):
        mock_get.return_value = _mock_response(
            data={
                "data": {
                    "feeds": [
                        {"name": "station_information", "url": "https://x/si.json"},
                        {"name": "station_status", "url": "https://x/ss.json"},
                    ]
                }
            }
        )
        client = GBFSClient("https://example.com/gbfs.json", "test")
        feeds = client.discover()
        assert len(feeds) == 2

    @patch("rebalancer.data.gbfs_client.requests.get")
    def test_raises_on_empty_discovery(self, mock_get):
        mock_get.return_value = _mock_response(data={"data": {}})
        client = GBFSClient("https://example.com/gbfs.json", "test")
        try:
            client.discover()
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


class TestFetchStationInformation:
    @patch("rebalancer.data.gbfs_client.requests.get")
    def test_parses_valid_stations(self, mock_get):
        mock_get.side_effect = [
            _mock_response(FIXTURES / "sample_discovery.json"),
            _mock_response(FIXTURES / "sample_station_information.json"),
        ]
        client = GBFSClient("https://example.com/gbfs.json", "test")
        stations = client.fetch_station_information()

        assert len(stations) == 2
        assert isinstance(stations[0], StationInfo)
        assert stations[0].station_id == "1"
        assert stations[0].name == "Central Park S & 6 Ave"
        assert stations[0].capacity == 20
        assert stations[1].station_id == "2"

    @patch("rebalancer.data.gbfs_client.requests.get")
    def test_skips_malformed_rows(self, mock_get):
        mock_get.side_effect = [
            _mock_response(FIXTURES / "sample_discovery.json"),
            _mock_response(
                data={
                    "data": {
                        "stations": [
                            {
                                "station_id": "1",
                                "name": "Good",
                                "lat": 40.7,
                                "lon": -73.9,
                                "capacity": 20,
                            },
                            {"name": "Missing station_id"},
                            {"station_id": "3", "lat": "bad", "lon": -73.9},
                        ]
                    }
                }
            ),
        ]
        client = GBFSClient("https://example.com/gbfs.json", "test")
        stations = client.fetch_station_information()

        assert len(stations) == 1
        assert stations[0].station_id == "1"

    @patch("rebalancer.data.gbfs_client.requests.get")
    def test_handles_empty_stations_list(self, mock_get):
        mock_get.side_effect = [
            _mock_response(FIXTURES / "sample_discovery.json"),
            _mock_response(data={"data": {"stations": []}}),
        ]
        client = GBFSClient("https://example.com/gbfs.json", "test")
        assert client.fetch_station_information() == []


class TestFetchStationStatus:
    @patch("rebalancer.data.gbfs_client.requests.get")
    def test_parses_valid_statuses(self, mock_get):
        mock_get.side_effect = [
            _mock_response(FIXTURES / "sample_discovery.json"),
            _mock_response(FIXTURES / "sample_station_status.json"),
        ]
        client = GBFSClient("https://example.com/gbfs.json", "test")
        statuses = client.fetch_station_status()

        assert len(statuses) == 2
        assert isinstance(statuses[0], StationStatus)
        assert statuses[0].station_id == "1"
        assert statuses[0].num_bikes_available == 5
        assert statuses[0].num_docks_available == 15
        assert statuses[0].is_renting is True
        assert statuses[1].num_bikes_available == 18

    @patch("rebalancer.data.gbfs_client.requests.get")
    def test_skips_malformed_status_rows(self, mock_get):
        mock_get.side_effect = [
            _mock_response(FIXTURES / "sample_discovery.json"),
            _mock_response(
                data={
                    "data": {
                        "stations": [
                            {
                                "station_id": "1",
                                "num_bikes_available": 5,
                                "num_docks_available": 15,
                            },
                            {"num_bikes_available": "not_a_number"},
                        ]
                    }
                }
            ),
        ]
        client = GBFSClient("https://example.com/gbfs.json", "test")
        statuses = client.fetch_station_status()

        assert len(statuses) == 1
        assert statuses[0].station_id == "1"

    @patch("rebalancer.data.gbfs_client.requests.get")
    def test_parses_gbfs_v3_iso8601_last_reported(self, mock_get):
        mock_get.side_effect = [
            _mock_response(FIXTURES / "sample_discovery.json"),
            _mock_response(
                data={
                    "data": {
                        "stations": [
                            {
                                "station_id": "1",
                                "num_bikes_available": 5,
                                "num_docks_available": 15,
                                "last_reported": "2026-09-11T08:53:20.129Z",
                            }
                        ]
                    }
                }
            ),
        ]
        client = GBFSClient("https://example.com/gbfs.json", "test")
        statuses = client.fetch_station_status()

        assert len(statuses) == 1
        assert statuses[0].last_reported > 0


class TestAutoDiscover:
    @patch("rebalancer.data.gbfs_client.requests.get")
    def test_auto_discovers_on_first_fetch(self, mock_get):
        mock_get.side_effect = [
            _mock_response(FIXTURES / "sample_discovery.json"),
            _mock_response(FIXTURES / "sample_station_status.json"),
        ]
        client = GBFSClient("https://example.com/gbfs.json", "test")
        statuses = client.fetch_station_status()
        assert len(statuses) == 2
        assert mock_get.call_count == 2

    @patch("rebalancer.data.gbfs_client.requests.get")
    def test_raises_on_missing_feed(self, mock_get):
        mock_get.return_value = _mock_response(
            data={"data": {"en": {"feeds": [{"name": "system_info", "url": "x"}]}}}
        )
        client = GBFSClient("https://example.com/gbfs.json", "test")
        try:
            client.fetch_station_information()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "station_information" in str(e)
