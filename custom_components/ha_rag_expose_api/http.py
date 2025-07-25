"""HTTP views for the HA-RAG Expose API component."""

from __future__ import annotations

from typing import Any

try:
    from homeassistant.helpers import (
        area_registry,
        device_registry,
        entity_registry,
    )
except Exception:  # pragma: no cover - Home Assistant not available
    _helpers = None
else:
    _helpers = (area_registry, device_registry, entity_registry)

try:
    from homeassistant.components.http import HomeAssistantView
except Exception:  # pragma: no cover - Home Assistant not available
    class HomeAssistantView:
        """Fallback class used when Home Assistant is not installed."""

        url: str = ""
        name: str = ""
        requires_auth: bool = True

        async def get(self, request):
            raise NotImplementedError

        def json(self, result: dict, status_code: int = 200):  # type: ignore[override]
            return result


class StaticEntitiesView(HomeAssistantView):
    """Return dummy data describing entities."""

    url = "/api/rag/static/entities"
    name = "api:rag:static_entities"
    requires_auth = False

    async def get(self, request):  # pragma: no cover - no real request in tests
        if _helpers is None:
            return self.json({"areas": [], "devices": [], "entities": []})

        hass = request.app["hass"]
        data = _collect_static(hass)
        return self.json(data)


class StateEntitiesView(HomeAssistantView):
    """Placeholder for state data."""

    url = "/api/rag/state/entities"
    name = "api:rag:state_entities"
    requires_auth = False

    async def get(self, request):  # pragma: no cover - no real request in tests
        return self.json({"error": "not implemented"}, status_code=501)


def _collect_static(hass: Any) -> dict[str, list[dict[str, Any]]]:
    """Collect static registry data from Home Assistant."""
    area_mod, device_mod, entity_mod = _helpers  # type: ignore[misc]
    area_reg = area_mod.async_get(hass)
    device_reg = device_mod.async_get(hass)
    entity_reg = entity_mod.async_get(hass)

    areas = [
        {
            "id": area.id,
            "name": area.name,
            "floor": getattr(area, "floor_id", getattr(area, "floor", None)),
            "aliases": list(getattr(area, "aliases", [])),
        }
        for area in area_reg.async_list_areas()
    ]

    devices = [
        {
            "id": device.id,
            "name": device.name,
            "model": device.model,
            "manufacturer": device.manufacturer,
            "area_id": device.area_id,
        }
        for device in device_reg.devices.values()
    ]

    entities = [
        {
            "entity_id": ent.entity_id,
            "platform": ent.platform,
            "device_id": ent.device_id,
            "area_id": ent.area_id,
            "domain": ent.domain,
            "original_name": ent.original_name,
        }
        for ent in entity_reg.entities.values()
    ]

    return {"areas": areas, "devices": devices, "entities": entities}
