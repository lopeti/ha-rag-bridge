import sys
import types
from unittest.mock import MagicMock

import ha_rag_bridge.bootstrap as boot

from tests.test_bootstrap import setup_env


def test_graph_bootstrap(monkeypatch):
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
    client.db.side_effect = lambda name, **kw: sys_db if name == "_system" else db

    monkeypatch.setattr(boot, "ArangoClient", MagicMock(return_value=client))

    fake_main = types.ModuleType("ha_rag_bridge.bootstrap.__main__")
    called = {}

    def fake_ensure():
        called["yes"] = True
        db.has_graph("ha_entity_graph")

    fake_main.ensure_arango_graph = fake_ensure
    sys.modules["ha_rag_bridge.bootstrap.__main__"] = fake_main

    boot.bootstrap()

    assert called.get("yes")
    db.has_graph.assert_called_once_with("ha_entity_graph")
