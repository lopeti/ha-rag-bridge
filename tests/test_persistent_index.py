import os
import pytest
from arango import ArangoClient

from ha_rag_bridge.db import BridgeDB
from ha_rag_bridge.db.index import IndexManager


def _db_available() -> bool:
    try:
        client = ArangoClient(hosts=os.getenv("ARANGO_URL", "http://localhost:8529"))
        db = client.db(
            "_system",
            username=os.getenv("ARANGO_USER", "root"),
            password=os.getenv("ARANGO_PASS", "pass"),
        )
        db.version()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def arango_db():
    if not _db_available():
        pytest.skip("ArangoDB not available")
    client = ArangoClient(hosts=os.getenv("ARANGO_URL", "http://localhost:8529"))
    db = client.db(
        "_system",
        username=os.getenv("ARANGO_USER", "root"),
        password=os.getenv("ARANGO_PASS", "pass"),
    )
    db.__class__ = BridgeDB
    return db


def test_persistent_index_created(arango_db):
    coll = arango_db.create_collection("events_test")
    IndexManager(coll).ensure_persistent(["time"])
    persistent_indexes = [i for i in coll.indexes().indexes if i.type == "persistent"]
    assert persistent_indexes, "No persistent index was created."
    idx = persistent_indexes[0]
    assert idx.fields == ["time"]
