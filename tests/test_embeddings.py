import os

import httpx

from app.services.integrations.embeddings import GeminiBackend


def test_gemini_embed(monkeypatch):
    os.environ["GEMINI_API_KEY"] = "key"
    mock_resp = {"embeddings": [{"values": [0.1] * 1536}]}

    def fake_post(*args, **kwargs):
        class R:
            def json(self_inner):
                return mock_resp

        return R()

    monkeypatch.setattr(httpx, "post", fake_post)
    backend = GeminiBackend()
    vec = backend.embed(["hi"])[0]
    assert len(vec) == 1536
