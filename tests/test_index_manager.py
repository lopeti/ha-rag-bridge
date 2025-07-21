from ha_rag_bridge.db.index import IndexManager
from unittest.mock import MagicMock


def test_hnsw_created():
    coll = MagicMock()
    coll.indexes.return_value = []
    coll.indexes.create.hnsw = MagicMock()
    mgr = IndexManager(coll)
    mgr.ensure_vector("vec", dimensions=3)
    coll.indexes.create.hnsw.assert_called_once_with(
        fields=["vec"], dimensions=3, similarity="cosine"
    )
