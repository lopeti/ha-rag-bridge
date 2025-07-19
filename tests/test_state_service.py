import os
from unittest.mock import MagicMock

import app.services.state_service as ss


def setup_env():
    os.environ.update(
        {
            "HA_URL": "http://ha",
            "HA_TOKEN": "token",
            "INFLUX_URL": "http://db:8086",
            "INFLUX_TOKEN": "tok",
            "STATE_CACHE_TTL": "30",
        }
    )


def test_influx_success(monkeypatch):
    setup_env()
    ss.get_last_state.cache.clear()
    mock_record = MagicMock()
    mock_record.get_value.return_value = 23.9
    mock_record.values = {"unit_of_measurement": "°C"}
    table = MagicMock(records=[mock_record])
    query_api = MagicMock()
    query_api.query.return_value = [table]
    mock_client = MagicMock()
    mock_client.query_api.return_value = query_api
    cm = MagicMock()
    cm.__enter__.return_value = mock_client
    monkeypatch.setattr(ss, "InfluxDBClient", MagicMock(return_value=cm))
    val = ss.get_last_state("sensor.temp")
    assert val == "23.9 °C"


def test_fallback_to_ha(monkeypatch):
    setup_env()
    ss.get_last_state.cache.clear()
    monkeypatch.setattr(ss, "InfluxDBClient", MagicMock(side_effect=Exception))
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "state": "22",
        "attributes": {"unit_of_measurement": "°C"},
    }
    resp.raise_for_status.return_value = None
    client = MagicMock()
    client.get.return_value = resp
    client.__enter__.return_value = client
    monkeypatch.setattr(ss.httpx, "Client", MagicMock(return_value=client))
    val = ss.get_last_state("sensor.temp")
    assert val == "22 °C"


def test_cache_hit(monkeypatch):
    setup_env()
    ss.get_last_state.cache.clear()

    calls = []

    def fake_influx(eid):
        calls.append(eid)
        return "1"

    monkeypatch.setattr(ss, "_query_influx", fake_influx)
    monkeypatch.setattr(ss, "_query_ha_state", MagicMock(return_value=None))

    first = ss.get_last_state("sensor.temp")
    second = ss.get_last_state("sensor.temp")

    assert first == "1"
    assert second == "1"
    assert calls == ["sensor.temp"]


def test_empty_measurement_query(monkeypatch):
    setup_env()
    ss.get_last_state.cache.clear()
    os.environ["INFLUX_MEASUREMENT"] = ""

    captured = {}
    query_api = MagicMock()

    def fake_query(q):
        captured["query"] = q
        return []

    query_api.query.side_effect = fake_query
    mock_client = MagicMock()
    mock_client.query_api.return_value = query_api
    cm = MagicMock()
    cm.__enter__.return_value = mock_client
    monkeypatch.setattr(ss, "InfluxDBClient", MagicMock(return_value=cm))

    ss._query_influx("sensor.temp")

    assert "_measurement" not in captured["query"]
