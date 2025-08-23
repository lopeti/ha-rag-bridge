import os
import httpx
import pytest

from app.services.service_catalog import ServiceCatalog
from app.main import service_to_tool


@pytest.mark.asyncio
async def test_refresh_and_tool_schema(monkeypatch):
    os.environ.update({"HA_URL": "http://ha", "HA_TOKEN": "tok"})

    resp_data = [
        {
            "domain": "light",
            "services": {
                "turn_on": {
                    "fields": {
                        "entity_id": {"required": True, "type": "string"},
                        "brightness_pct": {"required": False, "type": "integer"},
                    }
                }
            },
        }
    ]

    async def handler(request):
        assert request.url.path == "/api/services"
        return httpx.Response(200, json=resp_data)

    transport = httpx.MockTransport(handler)

    class FakeHTTPX:
        def __init__(self, real):
            self._real = real
            self.Response = real.Response

        def AsyncClient(self, **kw):
            kw["transport"] = transport
            return self._real.AsyncClient(**kw)

    import app.services.service_catalog as sc

    monkeypatch.setattr(sc, "httpx", FakeHTTPX(httpx))

    cat = ServiceCatalog(ttl=60)
    await cat.refresh()
    spec = await cat.get_service("light", "turn_on")
    assert "brightness_pct" in spec["fields"]

    tool = service_to_tool("light", "turn_on", spec)
    assert tool["function"]["name"] == "light.turn_on"
    assert "brightness_pct" in tool["function"]["parameters"]["properties"]
    assert "entity_id" in tool["function"]["parameters"]["required"]


@pytest.mark.asyncio
async def test_service_catalog_ttl(monkeypatch):
    os.environ.update({"HA_URL": "http://ha", "HA_TOKEN": "tok"})
    calls = []

    async def handler(request):
        calls.append(1)
        return httpx.Response(200, json=[{"domain": "light", "services": {}}])

    transport = httpx.MockTransport(handler)

    class FakeHTTPX:
        def __init__(self, real):
            self._real = real
            self.Response = real.Response

        def AsyncClient(self, **kw):
            kw["transport"] = transport
            return self._real.AsyncClient(**kw)

    import app.services.service_catalog as sc

    monkeypatch.setattr(sc, "httpx", FakeHTTPX(httpx))

    cat = ServiceCatalog(ttl=10)
    await cat.get_domain_services("light")
    await cat.get_domain_services("light")
    assert len(calls) == 1
    cat._ts -= 11
    await cat.get_domain_services("light")
    assert len(calls) == 2
