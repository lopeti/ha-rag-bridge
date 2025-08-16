import os
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
import app.main as main

client = TestClient(app)


def setup_env():
    os.environ.update(
        {
            "ARANGO_URL": "http://db",
            "ARANGO_USER": "root",
            "ARANGO_PASS": "pass",
            "EMBEDDING_BACKEND": "local",
        }
    )


def test_manual_hints(monkeypatch):
    setup_env()
    mock_backend = MagicMock()
    mock_backend.embed.return_value = [[0.0] * 1536]
    monkeypatch.setattr(main, "LocalBackend", MagicMock(return_value=mock_backend))

    monkeypatch.setattr(
        main,
        "retrieve_entities",
        MagicMock(
            return_value=[
                {"entity_id": "light.test", "domain": "light", "device_id": "dev1"}
            ]
        ),
    )

    monkeypatch.setattr(
        main, "query_manual", MagicMock(return_value=["hint1", "hint2"])
    )

    mock_db = MagicMock()
    mock_db.aql.execute.return_value = iter(["gree_manual"])
    mock_arango = MagicMock()
    mock_arango.db.return_value = mock_db
    monkeypatch.setattr(main, "ArangoClient", MagicMock(return_value=mock_arango))
    monkeypatch.setattr(main, "get_last_state", MagicMock(return_value=None))

    class DummyCat:
        async def get_domain_services(self, domain):
            return {}

    monkeypatch.setattr(main, "service_catalog", DummyCat())

    resp = client.post("/process-request", json={"user_message": "How to?"})
    assert resp.status_code == 200
    system = resp.json()["messages"][0]["content"]
    assert "Manual hints:" in system
    assert "hint1" in system
    assert "hint2" in system
