import sys
import json
import subprocess
from pathlib import Path

import httpx
import pytest

import demo


@pytest.mark.asyncio
async def test_demo_success(monkeypatch, capsys):
    resp_request = {
        "messages": [
            {"role": "system", "content": "Relevant entities: light.test"},
            {"role": "user", "content": "Turn on"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "light.turn_on",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {"type": "string", "required": True}
                        },
                        "required": ["entity_id"],
                    },
                },
            }
        ],
    }

    async def handler(request):
        if request.url.path == "/process-request":
            return httpx.Response(200, json=resp_request)
        assert request.url.path == "/process-response"
        payload = json.loads(request.content.decode())
        tc = payload["choices"][0]["message"]["tool_calls"][0]
        assert tc["function"]["name"] == "light.turn_on"
        return httpx.Response(200, json={"status": "ok", "message": "OK"})

    transport = httpx.MockTransport(handler)

    class FakeHTTPX:
        def __init__(self, real):
            self._real = real
            self.Response = real.Response

        def AsyncClient(self, **kw):
            kw["transport"] = transport
            return self._real.AsyncClient(**kw)

    monkeypatch.setattr(demo, "httpx", FakeHTTPX(httpx))

    msg = await demo.run_demo("Turn on")
    assert msg == "OK"
    out = capsys.readouterr().out
    assert "/process-request" in out
    assert "/process-response" in out


def test_demo_argparse():
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "demo.py")],
        capture_output=True,
    )
    assert proc.returncode == 2
    assert b"usage" in proc.stderr.lower()
