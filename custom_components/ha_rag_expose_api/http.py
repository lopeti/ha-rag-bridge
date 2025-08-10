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

    class _FallbackView:
        """Fallback class used when Home Assistant is not installed."""

        url: str = ""
        name: str = ""
        requires_auth: bool = True

        async def get(self, request):
            raise NotImplementedError

        def json(self, result: dict, status_code: int = 200):  # type: ignore[override]
            return result

    HomeAssistantView = _FallbackView


class StaticEntitiesView(HomeAssistantView):
    """Return dummy data describing entities."""

    url = "/api/rag/static/entities"
    name = "api:rag:static_entities"
    requires_auth = False

    async def get(self, request):  # pragma: no cover - no real request in tests
        if _helpers is None:
            return self.json({"areas": [], "devices": [], "entities": []})

        hass = request.app["hass"]
        # Check if 'all' parameter is provided to return all entities/devices
        query = getattr(request, "query", None)
        if query is None:
            include_all = True
        else:
            include_all = query.get("all", "").lower() in ("true", "1", "yes")
        data = _collect_static(hass, include_all=include_all)
        return self.json(data)


class StateEntitiesView(HomeAssistantView):
    """Placeholder for state data."""

    url = "/api/rag/state/entities"
    name = "api:rag:state_entities"
    requires_auth = False

    async def get(self, request):  # pragma: no cover - no real request in tests
        return self.json({"error": "not implemented"}, status_code=501)


class UpdateFriendlyNameView(HomeAssistantView):
    """Update entity friendly names via entity registry."""

    url = "/api/rag/update_friendly_name"
    name = "api:rag:update_friendly_name"
    requires_auth = True

    async def post(self, request):  # pragma: no cover - no real request in tests
        if _helpers is None:
            return self.json({"error": "Home Assistant helpers not available"}, status_code=500)

        hass = request.app["hass"]
        try:
            data = await request.json()
        except Exception:
            return self.json({"error": "Invalid JSON"}, status_code=400)

        entity_id = data.get("entity_id")
        friendly_name = data.get("friendly_name")
        
        if not entity_id or not friendly_name:
            return self.json({
                "error": "entity_id and friendly_name are required"
            }, status_code=400)

        # Get entity registry
        entity_mod = _helpers[2]  # entity_registry from _helpers tuple
        entity_reg = entity_mod.async_get(hass)
        
        # Check if entity exists
        entity_entry = entity_reg.async_get(entity_id)
        if not entity_entry:
            return self.json({
                "error": f"Entity {entity_id} not found in registry"
            }, status_code=404)
        
        try:
            # Update the entity name (friendly_name)
            updated_entry = entity_reg.async_update_entity(
                entity_id,
                name=friendly_name
            )
            
            return self.json({
                "success": True,
                "entity_id": entity_id,
                "old_name": entity_entry.name,
                "new_name": updated_entry.name,
                "message": f"Updated friendly name for {entity_id}"
            })
            
        except Exception as exc:
            return self.json({
                "error": f"Failed to update entity: {str(exc)}"
            }, status_code=500)


class BatchUpdateFriendlyNamesView(HomeAssistantView):
    """Batch update multiple entity friendly names."""

    url = "/api/rag/batch_update_friendly_names"
    name = "api:rag:batch_update_friendly_names"
    requires_auth = True

    async def post(self, request):  # pragma: no cover - no real request in tests
        if _helpers is None:
            return self.json({"error": "Home Assistant helpers not available"}, status_code=500)

        hass = request.app["hass"]
        try:
            data = await request.json()
        except Exception:
            return self.json({"error": "Invalid JSON"}, status_code=400)

        updates = data.get("updates", [])
        if not isinstance(updates, list):
            return self.json({"error": "updates must be a list"}, status_code=400)

        # Get entity registry
        entity_mod = _helpers[2]  # entity_registry
        entity_reg = entity_mod.async_get(hass)
        
        results = []
        errors = []
        
        for update in updates:
            entity_id = update.get("entity_id")
            friendly_name = update.get("friendly_name")
            
            if not entity_id or not friendly_name:
                errors.append(f"Missing entity_id or friendly_name in update: {update}")
                continue
            
            # Check if entity exists
            entity_entry = entity_reg.async_get(entity_id)
            if not entity_entry:
                errors.append(f"Entity {entity_id} not found in registry")
                continue
            
            try:
                # Update the entity name
                updated_entry = entity_reg.async_update_entity(
                    entity_id,
                    name=friendly_name
                )
                
                results.append({
                    "entity_id": entity_id,
                    "old_name": entity_entry.name,
                    "new_name": updated_entry.name,
                    "success": True
                })
                
            except Exception as exc:
                errors.append(f"Failed to update {entity_id}: {str(exc)}")
        
        return self.json({
            "success": len(errors) == 0,
            "updated": len(results),
            "results": results,
            "errors": errors
        })


def _collect_static(
    hass: Any, include_all: bool = False
) -> dict[str, list[dict[str, Any]]]:
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

    entities = []
    exposed_device_ids = set()

    # Try to import async_should_expose for both new and old Home Assistant versions
    try:
        from homeassistant.components.homeassistant.exposed_entities import (
            async_should_expose,
        )
    except ImportError:
        try:
            from homeassistant.helpers.entity import async_should_expose  # 2023.5-ig
        except ImportError:
            async_should_expose = None  # végső fallback
    for ent in entity_reg.entities.values():
        # Always calculate the actual exposed status based on HA settings
        actual_is_exposed = False

        if async_should_expose is not None:
            # Use Home Assistant's rule system (UI settings + defaults)
            actual_is_exposed = async_should_expose(hass, "conversation", ent.entity_id)
        else:
            # Fallback: only expose if options["conversation"]["should_expose"] is True
            if hasattr(ent, "options") and isinstance(ent.options, dict):
                actual_is_exposed = ent.options.get("conversation", {}).get(
                    "should_expose", False
                )

        # Include entity if it's exposed OR if include_all is True
        if actual_is_exposed or include_all:
            entities.append(
                {
                    "entity_id": ent.entity_id,
                    "platform": ent.platform,
                    "device_id": ent.device_id,
                    "area_id": ent.area_id,
                    "domain": ent.domain,
                    "original_name": ent.original_name,
                    "friendly_name": ent.name,  # Add friendly name from entity registry
                    "exposed": actual_is_exposed,  # Always show the actual HA exposed status
                }
            )
            # Track devices that have at least one exposed entity
            if ent.device_id and actual_is_exposed:
                exposed_device_ids.add(ent.device_id)

    # Only include devices that have at least one exposed entity (or all if include_all is True)
    devices = []
    for device in device_reg.devices.values():
        if include_all or device.id in exposed_device_ids:
            devices.append(
                {
                    "id": device.id,
                    "name": device.name,
                    "model": device.model,
                    "manufacturer": device.manufacturer,
                    "area_id": device.area_id,
                }
            )

    return {"areas": areas, "devices": devices, "entities": entities}
