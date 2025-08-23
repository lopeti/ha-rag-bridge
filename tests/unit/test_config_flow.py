import pytest

from custom_components.ha_rag_expose_api.config_flow import ConfigFlow
from custom_components.ha_rag_expose_api.const import DOMAIN


class DummyConfigEntries:
    async def async_init(self, domain, context=None, data=None):
        flow = ConfigFlow()
        if context and context.get("source") == "import":
            return await flow.async_step_import(data or {})
        return await flow.async_step_user(data)


class DummyHass:
    def __init__(self) -> None:
        self.config_entries = DummyConfigEntries()


@pytest.mark.asyncio
async def test_setup_via_ui():
    hass = DummyHass()
    result = await hass.config_entries.async_init(
        DOMAIN, context={"source": "user"}, data={}
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "HA-RAG Expose API"


@pytest.mark.asyncio
async def test_duplicate_abort():
    hass = DummyHass()
    await hass.config_entries.async_init(DOMAIN, context={"source": "user"}, data={})
    result = await hass.config_entries.async_init(
        DOMAIN, context={"source": "user"}, data={}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
