import os
from fastapi.testclient import TestClient
from app.main import app
import app.routers.admin as admin
from unittest.mock import patch, MagicMock


def test_admin_status(monkeypatch):
    os.environ["ADMIN_TOKEN"] = "test"
    mock_db = MagicMock()
    mock_db.has_collection.return_value = False
    mock_arango = MagicMock()
    mock_arango.db.return_value = mock_db
    monkeypatch.setattr(admin, "ArangoClient", MagicMock(return_value=mock_arango))
    client = TestClient(app)
    resp = client.get("/admin/status", headers={"X-Admin-Token": "test"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["vector_dim"] == int(os.getenv("EMBED_DIM", "1536"))


def test_admin_migrate(monkeypatch):
    os.environ["ADMIN_TOKEN"] = "test"
    with patch("app.routers.admin.bootstrap") as boot:
        client = TestClient(app)
        resp = client.post("/admin/migrate", headers={"X-Admin-Token": "test"})
        assert resp.status_code == 204
        boot.assert_called_once()
