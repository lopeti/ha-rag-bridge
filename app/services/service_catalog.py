from __future__ import annotations

import os
import time
import asyncio
from typing import Dict

from ha_rag_bridge.logging import get_logger
from ha_rag_bridge.config import get_settings

import httpx

logger = get_logger(__name__)


class ServiceCatalog:
    """Cache Home Assistant services fetched from /api/services."""

    def __init__(self, ttl: int = 6 * 3600) -> None:
        self.ttl = ttl
        self._cache: Dict[str, Dict[str, dict]] = {}
        self._ts = 0.0
        self._lock = asyncio.Lock()

    async def refresh(self) -> None:
        """Fetch and cache available services from Home Assistant."""
        base_url = os.environ.get("HA_URL")
        token = os.environ.get("HA_TOKEN")
        if not base_url or not token:
            logger.warning(
                "service catalog empty",
                missing_url=not bool(base_url),
                missing_token=not bool(token),
            )
            self._cache = {}
            self._ts = time.time()
            return

        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(
            base_url=base_url, headers=headers, timeout=get_settings().http_timeout
        ) as client:
            resp = await client.get("/api/services")
            resp.raise_for_status()
            data = resp.json()

        catalog: Dict[str, Dict[str, dict]] = {}
        for item in data:
            domain = item.get("domain")
            services = item.get("services", {})
            if not domain:
                continue
            cat_services: Dict[str, dict] = {}
            for name, spec in services.items():
                fields = spec.get("fields", {})
                cat_services[name] = {"fields": fields}
            catalog[domain] = cat_services

        self._cache = catalog
        self._ts = time.time()
        logger.debug("service catalog refreshed", domains=len(catalog))

    async def _ensure_fresh(self) -> None:
        if time.time() - self._ts > self.ttl:
            async with self._lock:
                if time.time() - self._ts > self.ttl:
                    await self.refresh()

    async def get_service(self, domain: str, name: str) -> dict | None:
        await self._ensure_fresh()
        return self._cache.get(domain, {}).get(name)

    async def get_domain_services(self, domain: str) -> Dict[str, dict]:
        await self._ensure_fresh()
        return self._cache.get(domain, {})
