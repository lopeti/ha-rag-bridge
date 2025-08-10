"""HA-RAG Expose API custom component."""

from __future__ import annotations

from .http import StaticEntitiesView, StateEntitiesView, UpdateFriendlyNameView, BatchUpdateFriendlyNamesView


async def async_setup(hass, config):
    """Set up the component."""
    _register_views(hass)
    return True


async def async_setup_entry(hass, entry):
    """Set up from a config entry."""
    _register_views(hass)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return True


async def async_reload_entry(hass, entry):
    """Reload the config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


def _register_views(hass):
    """Register HTTP views with Home Assistant if possible."""
    http = getattr(hass, "http", None)
    if hasattr(http, "register_view"):
        http.register_view(StaticEntitiesView)
        http.register_view(StateEntitiesView)
        http.register_view(UpdateFriendlyNameView)
        http.register_view(BatchUpdateFriendlyNamesView)
