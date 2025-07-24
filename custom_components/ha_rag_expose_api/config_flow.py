"""Config flow for the HA-RAG Expose API component."""

from __future__ import annotations

try:
    from homeassistant import config_entries
except Exception:  # pragma: no cover - Home Assistant not available
    from types import SimpleNamespace

    class DummyFlow:  # pragma: no cover - fallback
        async def async_show_form(self, step_id: str, data_schema=None):
            return {"type": "form", "step_id": step_id}

        async def async_create_entry(self, title: str, data: dict):
            return {"type": "create_entry", "title": title, "data": data}

    config_entries = SimpleNamespace(ConfigFlow=DummyFlow)

from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the component."""

    async def async_step_user(self, user_input=None):  # pragma: no cover - simple
        if user_input is not None:
            return self.async_create_entry(title="HA-RAG Expose API", data={})
        return self.async_show_form(step_id="user")
