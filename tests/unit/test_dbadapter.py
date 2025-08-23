from unittest.mock import MagicMock

from ha_rag_bridge.db import BridgeDB


def test_ensure_col(monkeypatch):
    db = BridgeDB.__new__(BridgeDB)
    db.has_collection = MagicMock(return_value=False)
    created_col = MagicMock()
    db.create_collection = MagicMock(return_value=created_col)
    db.collection = MagicMock(return_value=MagicMock())

    assert db.ensure_col("sensors") is created_col
    db.create_collection.assert_called_with("sensors", edge=False)

    db.has_collection.return_value = True
    assert db.ensure_col("sensors") is db.collection.return_value


def test_get_col_none():
    db = BridgeDB.__new__(BridgeDB)
    db.has_collection = MagicMock(return_value=False)
    db.collection = MagicMock()

    assert db.get_col("nope") is None
    db.collection.assert_not_called()
