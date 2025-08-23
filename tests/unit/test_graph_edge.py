import os
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
import app.routers.graph as graph

client = TestClient(app)

os.environ.update(
    {
        "ARANGO_URL": "http://db",
        "ARANGO_USER": "root",
        "ARANGO_PASS": "pass",
    }
)

EDGE_PAYLOAD = {"_from": "area/nappali", "_to": "area/etkezo", "label": "area_adjacent"}


def setup_db(monkeypatch, insert_side_effect=None, has_side_effect=None):
    mock_edge_col = MagicMock()
    mock_edge_col.insert.side_effect = insert_side_effect
    mock_area_col = MagicMock()
    mock_area_col.has.side_effect = has_side_effect or (lambda *_: True)

    def get_collection(name):
        if name == "edge":
            return mock_edge_col
        return mock_area_col

    mock_db = MagicMock()
    mock_db.collection.side_effect = get_collection
    mock_arango = MagicMock()
    mock_arango.db.return_value = mock_db
    monkeypatch.setattr(graph, "ArangoClient", MagicMock(return_value=mock_arango))
    return mock_edge_col, mock_area_col


def test_add_edge_insert(monkeypatch):
    insert_result = {}
    mock_edge_col, _ = setup_db(monkeypatch, insert_side_effect=[insert_result])
    resp = client.post("/graph/edge", json=EDGE_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "inserted"
    assert data["edge_key"] == "area_nappali-area_etkezo-area_adjacent"
    mock_edge_col.insert.assert_called_once()


def test_add_edge_update(monkeypatch):
    insert_results = [{}, {"_old_rev": "1"}]
    mock_edge_col, _ = setup_db(monkeypatch, insert_side_effect=insert_results)
    resp1 = client.post("/graph/edge", json=EDGE_PAYLOAD)
    resp2 = client.post("/graph/edge", json=EDGE_PAYLOAD)
    assert resp1.json()["action"] == "inserted"
    assert resp2.json()["action"] == "updated"
    assert mock_edge_col.insert.call_count == 2


def test_add_edge_invalid_from(monkeypatch):
    mock_edge_col, mock_area_col = setup_db(monkeypatch, has_side_effect=[False, True])
    resp = client.post("/graph/edge", json=EDGE_PAYLOAD)
    assert resp.status_code == 422
    mock_edge_col.insert.assert_not_called()
