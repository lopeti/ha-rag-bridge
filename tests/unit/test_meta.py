import os
from unittest.mock import MagicMock

import ha_rag_bridge.bootstrap as boot


def setup_env():
    os.environ["ARANGO_URL"] = "http://db"
    os.environ["ARANGO_USER"] = "root"
    os.environ["ARANGO_PASS"] = "pass"
    os.environ["AUTO_BOOTSTRAP"] = "1"


def test_meta_collection_created(monkeypatch):
    setup_env()
    meta_col = MagicMock()
    meta_col.get.return_value = None

    def ensure_col(name, *, edge=False):
        assert name == "meta"
        return meta_col

    db = MagicMock()
    db.ensure_col.side_effect = ensure_col
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
