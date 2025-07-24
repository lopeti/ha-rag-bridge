from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest

from custom_components.ha_rag_expose_api import async_setup


@pytest.mark.asyncio
async def test_async_setup_returns_true():
    assert await async_setup(object(), {}) is True
