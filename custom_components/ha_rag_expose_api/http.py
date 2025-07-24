"""HTTP views for the HA-RAG Expose API component."""

from __future__ import annotations

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
        return self.json({"areas": [], "devices": [], "entities": []})


class StateEntitiesView(HomeAssistantView):
    """Placeholder for state data."""

    url = "/api/rag/state/entities"
    name = "api:rag:state_entities"
    requires_auth = False

    async def get(self, request):  # pragma: no cover - no real request in tests
        return self.json({"error": "not implemented"}, status_code=501)
