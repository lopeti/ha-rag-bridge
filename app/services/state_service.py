from __future__ import annotations

import os
from typing import Optional, Any

import httpx
from influxdb_client import InfluxDBClient


def _query_influx(entity_id: str) -> Optional[Any]:
    url = os.getenv("INFLUX_URL")
    token = os.getenv("INFLUX_TOKEN")
    org = os.getenv("INFLUX_ORG", "homeassistant")
    bucket = os.getenv("INFLUX_BUCKET", "homeassistant")
    measurement = os.getenv("INFLUX_MEASUREMENT", "measurement")
    if not url or not token:
        return None

    query = (
        f'from(bucket: "{bucket}")\n'
        '  |> range(start: -5m)\n'
        f'  |> filter(fn: (r) => r["_measurement"] == "{measurement}")\n'
        f'  |> filter(fn: (r) => r["entity_id"] == "{entity_id}")\n'
        '  |> last()'
    )

    try:
        with InfluxDBClient(url=url, token=token, org=org, timeout=5000) as client:
            tables = client.query_api().query(query)
            for table in tables:
                for record in table.records:
                    value = record.get_value()
                    unit = record.values.get("unit_of_measurement")
                    return f"{value} {unit}".strip() if unit else value
    except Exception:
        return None
    return None


def _query_ha_state(entity_id: str) -> Optional[Any]:
    base_url = os.environ.get("HA_URL")
    token = os.environ.get("HA_TOKEN")
    if not base_url or not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}
    for attempt in range(2):
        try:
            with httpx.Client(base_url=base_url, headers=headers, timeout=5.0) as client:
                resp = client.get(f"/api/states/{entity_id}")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                data = resp.json()
                value = data.get("state")
                unit = data.get("attributes", {}).get("unit_of_measurement")
                if value in (None, "unknown", "unavailable"):
                    return None
                return f"{value} {unit}".strip() if unit else value
        except (httpx.TimeoutException, httpx.RequestError):
            if attempt == 1:
                return None
    return None


def get_last_state(entity_id: str) -> Optional[Any]:
    """Return the last value + unit, or None if unavailable."""
    value = _query_influx(entity_id)
    if value is not None:
        return value
    return _query_ha_state(entity_id)
