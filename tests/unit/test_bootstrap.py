import os
from unittest.mock import MagicMock

import ha_rag_bridge.bootstrap as boot


def setup_env():
    os.environ["ARANGO_URL"] = "http://db"
    os.environ["ARANGO_USER"] = "root"
    os.environ["ARANGO_PASS"] = "pass"
    os.environ["AUTO_BOOTSTRAP"] = "1"


def test_bootstrap_idempotent(monkeypatch):
    setup_env()
    meta_col = MagicMock()
    meta_col.get.return_value = None
    db = MagicMock()
    db.ensure_col.return_value = meta_col
    db.collections.return_value = []
    db.has_view.return_value = True
    sys_db = MagicMock()
    sys_db.has_database.return_value = True
    client = MagicMock()

    def db_side(name, **kw):
        return sys_db if name == "_system" else db

    client.db.side_effect = db_side
    monkeypatch.setattr(boot, "ArangoClient", MagicMock(return_value=client))

    boot.bootstrap()
    assert meta_col.insert.called
    meta_col.get.return_value = type("Doc", (), {"value": boot.SCHEMA_LATEST})()
    boot.bootstrap()
    assert meta_col.insert.call_count == 3


def test_run_dry_run(monkeypatch):
    setup_env()
    called = False

    def fake_impl(*a, **k):
        nonlocal called
        called = True

    monkeypatch.setattr(boot, "_bootstrap_impl", fake_impl)
    code = boot.run(None, dry_run=True)
    assert code == 0
    assert not called
