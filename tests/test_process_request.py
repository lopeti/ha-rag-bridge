import os
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
import app.main as main

client = TestClient(app)


def test_process_request(monkeypatch):
    os.environ.update({
        "ARANGO_URL": "http://db",
        "ARANGO_USER": "root",
        "ARANGO_PASS": "pass",
        "EMBEDDING_BACKEND": "local",
    })

    mock_backend = MagicMock()
    mock_backend.embed.return_value = [[0.0] * 1536]
    monkeypatch.setattr(main, "LocalBackend", MagicMock(return_value=mock_backend))

    docs = [
        {"entity_id": "sensor.kitchen_temp", "domain": "sensor"},
        {"entity_id": "light.livingroom", "domain": "light"},
        {"entity_id": "switch.bedroom", "domain": "switch"},
    ]

    mock_cursor = MagicMock()
    mock_cursor.__iter__.return_value = docs
    mock_db = MagicMock()
    mock_db.aql.execute.return_value = mock_cursor
    mock_arango = MagicMock()
    mock_arango.db.return_value = mock_db
    monkeypatch.setattr(main, "ArangoClient", MagicMock(return_value=mock_arango))

    resp = client.post("/process-request", json={"user_message": "Kapcsold le a nappali lámpát!"})
    assert resp.status_code == 200
    data = resp.json()
    system = data["messages"][0]["content"]
    assert "sensor.kitchen_temp" in system
    assert "light.livingroom" in system
    assert "switch.bedroom" in system
    assert "Relevant domains:" in system
    assert isinstance(data.get("tools"), list) and data["tools"]
