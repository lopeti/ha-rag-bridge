from __future__ import annotations

import os
from typing import Optional, Any

# Használjuk a mypy:ignore-t a cachetools importjánál
from cachetools import TTLCache, cached  # type: ignore

import httpx
from ha_rag_bridge.settings import HTTP_TIMEOUT

try:
    # Try InfluxDB v2.x client first
    from influxdb_client import InfluxDBClient  # type: ignore

    INFLUX_V2_AVAILABLE = True
except ImportError:
    INFLUX_V2_AVAILABLE = False

try:
    # InfluxDB v1.x client
    from influxdb import InfluxDBClient as InfluxDBClientV1  # type: ignore

    INFLUX_V1_AVAILABLE = True
except ImportError:
    INFLUX_V1_AVAILABLE = False

from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)

_CACHE = TTLCache(maxsize=1024, ttl=int(os.getenv("STATE_CACHE_TTL", "30")))


def _detect_influx_version(url: str) -> Optional[str]:
    """Detect InfluxDB version by checking headers."""
    try:
        import httpx

        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{url}/ping")
            if "X-Influxdb-Version" in resp.headers:
                version = resp.headers["X-Influxdb-Version"]
                if version.startswith("1."):
                    return "v1"
                elif version.startswith("2."):
                    return "v2"
    except Exception:
        pass
    return None


def _query_influx_v1(
    entity_id: str,
    url: str,
    username: str,
    password: str,
    database: str,
    measurement: str,
) -> Optional[Any]:
    """Query InfluxDB v1.x using SQL-like syntax."""
    if not INFLUX_V1_AVAILABLE:
        return None

    try:
        from urllib.parse import urlparse

        parsed_url = urlparse(url)

        client = InfluxDBClientV1(
            host=parsed_url.hostname,
            port=parsed_url.port or 8086,
            username=username,
            password=password,
            database=database,
            timeout=5,
        )

        # InfluxDB v1.x SQL query
        if measurement:
            query = f'SELECT last("value") FROM "{measurement}" WHERE "entity_id" = \'{entity_id}\' AND time >= now() - 5m'
        else:
            query = f'SELECT last("value") FROM /.*/ WHERE "entity_id" = \'{entity_id}\' AND time >= now() - 5m'

        result = client.query(query)

        if result and len(result) > 0:
            points = list(result.get_points())
            if points and len(points) > 0:
                value = points[0].get("last")
                if value is not None:
                    return str(value)
    except Exception as exc:
        logger.debug("influx v1 query failed", entity_id=entity_id, error=str(exc))
        return None
    return None


def _query_influx_v2(
    entity_id: str, url: str, token: str, org: str, bucket: str, measurement: str
) -> Optional[Any]:
    """Query InfluxDB v2.x using Flux language."""
    if not INFLUX_V2_AVAILABLE:
        return None

    try:
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

        with InfluxDBClient(url=url, token=token, org=org, timeout=5000) as client:
            tables = client.query_api().query(query)
            for table in tables:
                for record in table.records:
                    value = record.get_value()
                    unit = record.values.get("unit_of_measurement")
                    return f"{value} {unit}".strip() if unit else value
    except Exception as exc:
        logger.debug("influx v2 query failed", entity_id=entity_id, error=str(exc))
        return None
    return None


def _query_influx(entity_id: str) -> Optional[Any]:
    url = os.getenv("INFLUX_URL")
    if not url:
        return None

    token = os.getenv("INFLUX_TOKEN", "")
    username = os.getenv("INFLUX_USER")
    password = os.getenv("INFLUX_PASS")
    org = os.getenv("INFLUX_ORG", "homeassistant")
    bucket = os.getenv("INFLUX_BUCKET", "homeassistant")
    database = os.getenv(
        "INFLUX_DB", "homeassistant"
    )  # v1.x uses database instead of bucket
    measurement = os.getenv("INFLUX_MEASUREMENT", "")

    # Detect InfluxDB version
    version = _detect_influx_version(url)

    if version == "v1":
        if not username or not password:
            logger.debug("influx v1 auth missing", entity_id=entity_id)
            return None
        return _query_influx_v1(
            entity_id, url, username, password, database, measurement
        )
    elif version == "v2":
        if not token:
            logger.debug("influx v2 token missing", entity_id=entity_id)
            return None
        return _query_influx_v2(entity_id, url, token, org, bucket, measurement)
    else:
        logger.debug("influx version detection failed", entity_id=entity_id, url=url)
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


def get_fresh_state(entity_id: str) -> Optional[Any]:
    """Return the fresh value + unit without caching, or None if unavailable."""
    value = _query_influx(entity_id)
    if value is not None:
        return value
    return _query_ha_state(entity_id)
