import os
import json
import httpx
from fastapi.testclient import TestClient
import app.main as main

def setup_env():
    os.environ.update({
        "HA_URL": "http://ha",
        "HA_TOKEN": "tok",
    })


def make_payload(content="OK", entity="light.test", func="homeassistant.turn_on"):
    return {
        "id": "1",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": func,
                                "arguments": json.dumps({"entity_id": entity})
                            }
                        }
                    ]
                }
            }
        ]
    }


def test_process_response_success(monkeypatch):
    setup_env()
    captured = []

    def handler(request):
        captured.append((request.url.path, json.loads(request.content.decode())))
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    class FakeHTTPX:
        def __init__(self, real):
            self._real = real
            self.Response = real.Response

        def AsyncClient(self, **kw):
            kw["transport"] = transport
            return self._real.AsyncClient(**kw)

    monkeypatch.setattr(main, "httpx", FakeHTTPX(httpx))

    client = TestClient(main.app)
    resp = client.post("/process-response", json=make_payload())
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "message": "OK"}
    assert captured == [("/api/services/homeassistant/turn_on", {"entity_id": "light.test"})]


def test_process_response_error(monkeypatch):
    setup_env()

    def handler(request):
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    class FakeHTTPX:
        def __init__(self, real):
            self._real = real
            self.Response = real.Response

        def AsyncClient(self, **kw):
            kw["transport"] = transport
            return self._real.AsyncClient(**kw)

    monkeypatch.setattr(main, "httpx", FakeHTTPX(httpx))

    client = TestClient(main.app)
    resp = client.post("/process-response", json=make_payload(entity="light.fail"))
    assert resp.status_code == 200
    assert resp.json() == {"status": "error", "message": "Nem sikerült végrehajtani: light.fail"}


