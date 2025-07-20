import os
import glob
import importlib.util
from time import perf_counter
from arango import ArangoClient

from ha_rag_bridge.utils.env import env_true
from ha_rag_bridge.logging import get_logger

SCHEMA_LATEST = 2

logger = get_logger(__name__)


def bootstrap() -> None:
    """Ensure database collections and indexes exist."""
    if not env_true("AUTO_BOOTSTRAP", True):
        logger.info("bootstrap disabled")
        return

    try:
        arango_url = os.environ["ARANGO_URL"]
        user = os.environ["ARANGO_USER"]
        password = os.environ["ARANGO_PASS"]
    except KeyError as exc:  # pragma: no cover - missing env
        logger.warning("bootstrap skipped", missing=str(exc))
        return

    db_name = os.getenv("ARANGO_DB", "ha_graph")
    embed_dim = int(os.getenv("EMBED_DIM", "1536"))

    client = ArangoClient(hosts=arango_url)
    sys_db = client.db("_system", username=user, password=password)
    if not sys_db.has_database(db_name):
        sys_db.create_database(db_name)

    db = client.db(db_name, username=user, password=password)

    # Run pending migrations based on stored schema version
    version = 0
    if db.has_collection("_meta"):
        meta_col = db.collection("_meta")
        doc = meta_col.get("schema_version")
        if doc:
            version = int(doc.get("value", 0))
    else:
        db.create_collection("_meta")
        meta_col = db.collection("_meta")

    if version < SCHEMA_LATEST:
        for num in range(version + 1, SCHEMA_LATEST + 1):
            for path in sorted(glob.glob(f"migrations/{num:02d}__*.py")):
                spec = importlib.util.spec_from_file_location("migration", path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "run"):
                        mod.run(db)
        version = SCHEMA_LATEST

    doc_cols = [
        "area",
        "device",
        "entity",
        "automation",
        "scene",
        "person",
        "event",
        "knowledge",
        "document",
    ]
    for name in doc_cols:
        if not db.has_collection(name):
            db.create_collection(name)
    if not db.has_collection("edge"):
        db.create_collection("edge", edge=True)

    entity = db.collection("entity")
    idx = next(
        (i for i in entity.indexes() if i["type"] == "hnsw" and i["fields"] == ["embedding"]),
        None,
    )
    if idx and idx.get("dimensions") != embed_dim:
        entity.delete_index(idx["id"])
        idx = None
    if not idx:
        entity.add_index({
            "type": "hnsw",
            "fields": ["embedding"],
            "dimensions": embed_dim,
            "metric": "cosine",
        })

    if not any(i["type"] == "hash" and i["fields"] == ["entity_id"] for i in entity.indexes()):
        entity.add_hash_index(fields=["entity_id"], unique=True)

    if not db.has_view("v_meta"):
        db.create_arangosearch_view(
            "v_meta",
            properties={
                "links": {
                    "entity": {
                        "includeAllFields": False,
                        "storeValues": "none",
                        "fields": {
                            "text": {"analyzers": ["text_en"]},
                            "embedding": {
                                "analyzers": ["vector"],
                                "vector": {"dimension": embed_dim, "metric": "cosine"},
                            },
                        },
                        "features": ["frequency", "norm", "position"],
                    }
                }
            },
        )

    if not db.has_view("v_manual"):
        db.create_arangosearch_view(
            "v_manual",
            properties={
                "links": {
                    "document": {
                        "includeAllFields": False,
                        "storeValues": "none",
                        "fields": {
                            "text": {"analyzers": ["text_en"]},
                            "embedding": {
                                "analyzers": ["vector"],
                                "vector": {"dimension": embed_dim, "metric": "cosine"},
                            },
                        },
                        "features": ["frequency", "norm", "position"],
                    }
                }
            },
        )

    meta_col.insert({"_key": "schema_version", "value": SCHEMA_LATEST}, overwrite=True)
    logger.info("bootstrap finished")

if __name__ == "__main__":
    bootstrap()

