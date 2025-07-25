"""Config flow for the HA-RAG Expose API component."""

from __future__ import annotations

import inspect

try:
    from homeassistant import config_entries
except Exception:  # pragma: no cover - Home Assistant not available
    from types import SimpleNamespace

    class DummyFlow:  # pragma: no cover - fallback
        def __init_subclass__(cls, **kwargs):  # pragma: no cover
            return super().__init_subclass__()

        async def async_show_form(self, step_id: str, data_schema=None):
            return {"type": "form", "step_id": step_id}

        async def async_create_entry(self, title: str, data: dict):
            return {"type": "create_entry", "title": title, "data": data}

        async def async_set_unique_id(self, uid: str) -> None:  # pragma: no cover
            self._unique_id = uid

        def async_abort(self, reason: str):  # pragma: no cover
            return {"type": "abort", "reason": reason}

    config_entries = SimpleNamespace(ConfigFlow=DummyFlow)

from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the component."""

    _configured: bool = False

    async def _async_check_duplicate(self):
        await self.async_set_unique_id(DOMAIN)
        if ConfigFlow._configured:
            return self.async_abort(reason="already_configured")

    async def async_step_user(self, user_input=None):
        duplicate = await self._async_check_duplicate()
        if duplicate:
            return duplicate
        if user_input is not None:
            ConfigFlow._configured = True
            result = self.async_create_entry(title="HA-RAG Expose API", data={})
            if inspect.isawaitable(result):
                result = await result
            return result
        return self.async_show_form(step_id="user")

    async def async_step_import(self, user_input):
        duplicate = await self._async_check_duplicate()
        if duplicate:
            return duplicate
        ConfigFlow._configured = True
        result = self.async_create_entry(title="HA-RAG Expose API", data={})
        if inspect.isawaitable(result):
            result = await result
        return result
