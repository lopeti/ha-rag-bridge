"""Legacy settings module - DEPRECATED

Use ha_rag_bridge.config instead.
"""

from ha_rag_bridge.config import get_settings

_settings = get_settings()
HTTP_TIMEOUT = _settings.http_timeout
