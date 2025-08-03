from __future__ import annotations

import os
from typing import Optional, Any

# Használjuk a mypy:ignore-t a cachetools importjánál
from cachetools import TTLCache, cached  # type: ignore

import httpx
from ha_rag_bridge.settings import HTTP_TIMEOUT
from influxdb_client import InfluxDBClient  # type: ignore

from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)

_CACHE = TTLCache(maxsize=1024, ttl=int(os.getenv("STATE_CACHE_TTL", "30")))


def _query_influx(entity_id: str) -> Optional[Any]:
    url = os.getenv("INFLUX_URL")
    token = os.getenv("INFLUX_TOKEN", "")
    username = os.getenv("INFLUX_USERNAME")
    password = os.getenv("INFLUX_PASSWORD")
    org = os.getenv("INFLUX_ORG", "homeassistant")
    bucket = os.getenv("INFLUX_BUCKET", "homeassistant")
    measurement = os.getenv("INFLUX_MEASUREMENT", "measurement")
    if not url:
        return None

    if token:
        auth_kwargs = {"token": token}
    elif username and password:
        auth_kwargs = {"username": username, "password": password}
    else:
        logger.warning("Influx auth missing; skipping query", entity_id=entity_id)
        return None

    query = (
        f'from(bucket: "{bucket}")\n'
        "  |> range(start: -5m)\n"
        + (
            f'  |> filter(fn: (r) => r["_measurement"] == "{measurement}")\n'
            if measurement
            else ""
        )
        + f'  |> filter(fn: (r) => r["entity_id"] == "{entity_id}")\n'
        "  |> last()"
    )

    try:
        with InfluxDBClient(url=url, org=org, timeout=5000, **auth_kwargs) as client:
            tables = client.query_api().query(query)
            for table in tables:
                for record in table.records:
                    value = record.get_value()
                    unit = record.values.get("unit_of_measurement")
                    return f"{value} {unit}".strip() if unit else value
    except Exception as exc:
        logger.warning("influx query failed", entity_id=entity_id, error=str(exc))
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
            with httpx.Client(
                base_url=base_url, headers=headers, timeout=HTTP_TIMEOUT
            ) as client:
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


@cached(_CACHE)
def get_last_state(entity_id: str) -> Optional[Any]:
    """Return the last value + unit, or None if unavailable."""
    value = _query_influx(entity_id)
    if value is not None:
        return value
    return _query_ha_state(entity_id)
