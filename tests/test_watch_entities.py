import os
import asyncio
import json
from unittest.mock import MagicMock

import pytest

import scripts.watch_entities as watcher

os.environ.update(
    {
        "HA_URL": "http://ha",
        "HA_TOKEN": "token",
    }
)


class DummyWS:
    def __init__(self, messages):
        self.messages = messages
        self.sent = []

    async def send(self, msg):
        self.sent.append(msg)

    async def recv(self):
        if self.messages:
            return self.messages.pop(0)
        await asyncio.sleep(1)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


@pytest.mark.asyncio
async def test_update_triggers_ingest(monkeypatch):
    msg_auth_ok = json.dumps({"type": "auth_ok"})
    event_msg = json.dumps(
        {
            "type": "event",
            "event": {
                "event_type": "entity_registry_updated",
                "data": {"action": "update", "entity_id": "light.test"},
            },
        }
    )
    dummy_ws = DummyWS([msg_auth_ok, event_msg])

    async def connect_mock(*args, **kwargs):
        return dummy_ws

    class CM:
        async def __aenter__(self_inner):
            return await connect_mock()

        async def __aexit__(self_inner, exc_type, exc, tb):
            pass

    monkeypatch.setattr(watcher.websockets, "connect", lambda *a, **kw: CM())

    ingest_mock = MagicMock()
    monkeypatch.setattr(watcher, "ingest", ingest_mock)

    task = asyncio.create_task(watcher.watch())
    await asyncio.sleep(0.1)
    task.cancel()
    await task

    ingest_mock.assert_called_once_with("light.test")
