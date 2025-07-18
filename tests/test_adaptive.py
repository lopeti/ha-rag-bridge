import os
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
import app.main as main

client = TestClient(app)


def _setup_env():
    os.environ.update({
        "ARANGO_URL": "http://db",
        "ARANGO_USER": "root",
        "ARANGO_PASS": "pass",
        "EMBEDDING_BACKEND": "local",
    })


def test_adaptive_control_tools(monkeypatch):
    _setup_env()

    mock_backend = MagicMock()
    mock_backend.embed.return_value = [[0.0] * 1536]
    monkeypatch.setattr(main, "LocalBackend", MagicMock(return_value=mock_backend))

    monkeypatch.setattr(main, "ArangoClient", MagicMock())
    ents = [
        {"entity_id": "light.livingroom", "domain": "light"},
        {"entity_id": "sensor.kitchen_temp", "domain": "sensor"},
    ]
    monkeypatch.setattr(main, "retrieve_entities", MagicMock(return_value=ents))

    resp = client.post("/process-request", json={"user_message": "Kapcsold fel a nappali lámpát"})
    assert resp.status_code == 200
    data = resp.json()
    tool_names = [t["function"]["name"] for t in data.get("tools", [])]
    assert "homeassistant.turn_on" in tool_names
    assert "homeassistant.turn_off" in tool_names
    assert "Relevant domains: light,sensor" in data["messages"][0]["content"]


def test_adaptive_read_no_tools(monkeypatch):
    _setup_env()

    mock_backend = MagicMock()
    mock_backend.embed.return_value = [[0.0] * 1536]
    monkeypatch.setattr(main, "LocalBackend", MagicMock(return_value=mock_backend))

    monkeypatch.setattr(main, "ArangoClient", MagicMock())
    ents = [{"entity_id": "sensor.temp", "domain": "sensor"}]
    monkeypatch.setattr(main, "retrieve_entities", MagicMock(return_value=ents))
    monkeypatch.setattr(main, "get_last_state", MagicMock(return_value=None))

    resp = client.post("/process-request", json={"user_message": "Hány fok van a nappaliban?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tools"] == []
    assert "Relevant domains: sensor" in data["messages"][0]["content"]


def test_adaptive_retrieve_flow(monkeypatch):
    db = object()
    qa_mock = MagicMock(side_effect=[[], []])
    qtext_mock = MagicMock(return_value=[{"entity_id": f"e{i}"} for i in range(5)])
    monkeypatch.setattr(main, "query_arango", qa_mock)
    monkeypatch.setattr(main, "query_arango_text_only", qtext_mock)

    ents = main.retrieve_entities(db, [0.0], "msg")
    assert qa_mock.call_count == 2
    assert qa_mock.call_args_list[0][0][3] == 5
    assert qa_mock.call_args_list[1][0][3] == 15
    qtext_mock.assert_called_once_with(db, "msg", 10)
    assert len(ents) <= 10
