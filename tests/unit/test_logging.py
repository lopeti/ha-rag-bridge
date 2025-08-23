import json
import logging
from fastapi.testclient import TestClient

from ha_rag_bridge.logging import get_logger
from app.main import app


def test_logger_json(caplog):
    logger = get_logger(__name__)
    with caplog.at_level(logging.INFO):
        logger.info("test", foo=1)
    line = caplog.text.strip().splitlines()[-1]
    json_part = line[line.find("{") :]
    data = json.loads(json_part)
    assert data["event"] == "test"
    assert data["foo"] == 1


def test_request_id(caplog, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "x")
    client = TestClient(app)
    # avoid hitting Arango in bootstrap
    monkeypatch.setattr("app.routers.admin.bootstrap", lambda: None)

    class DummyCol:
        def indexes(self):
            return []

        def add_index(self, *a, **k):
            pass

        def delete_index(self, *a, **k):
            pass

    class DummyDB:
        def collections(self):
            return []

        def collection(self, name):
            return DummyCol()

    dummy_client = type("C", (), {"db": lambda self, *a, **k: DummyDB()})()
    monkeypatch.setattr("app.routers.admin.ArangoClient", lambda *a, **k: dummy_client)
    monkeypatch.setenv("ARANGO_URL", "http://db")
    monkeypatch.setenv("ARANGO_USER", "root")
    monkeypatch.setenv("ARANGO_PASS", "pass")
    with caplog.at_level(logging.INFO):
        client.post("/admin/reindex", headers={"X-Admin-Token": "x"}, json={})
    lines = [
        json.loads(line[line.find("{") :])
        for line in caplog.text.strip().splitlines()
        if "req_id" in line
    ]
    req_ids = {line.get("req_id") for line in lines}
    assert len(req_ids) == 1
