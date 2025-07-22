from ha_rag_bridge.db.index import IndexManager
from unittest.mock import MagicMock


def test_hnsw_created():
    coll = MagicMock()
    coll.indexes.return_value = []
    coll.add_index = MagicMock()
    coll.count.return_value = 0
    mgr = IndexManager(coll)
    mgr.ensure_vector("vec", dimensions=3)
    coll.add_index.assert_called_once_with(
        {
            "type": "vector",
            "fields": ["vec"],
            "params": {
                "metric": "cosine",
                "dimension": 3,
                "nLists": 1,
                "defaultNProbe": 1,
            },
        }
    )
