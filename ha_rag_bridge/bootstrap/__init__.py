import os
import glob
import importlib.util
from arango import ArangoClient
from ha_rag_bridge.db import BridgeDB
from ha_rag_bridge.db.index import IndexManager

from .naming import safe_create_collection, is_valid, to_valid_name

from ha_rag_bridge.utils.env import env_true
from ha_rag_bridge.logging import get_logger

SCHEMA_LATEST = 3

logger = get_logger(__name__)


def run(
    plan,
    *,
    dry_run: bool = False,
    force: bool = False,
    skip_invalid: bool = False,
    rename_invalid: bool = False,
) -> int:
    """Ensure database collections and indexes exist."""
    from .plan_validator import validate_plan

    if plan is not None:
        validate_plan(plan)
    if not env_true("AUTO_BOOTSTRAP", True):
        logger.info("bootstrap disabled")
        return 0

    if dry_run:
        logger.info("dry run - no changes")
        return 0

    try:
        _bootstrap_impl(
            force=force,
            skip_invalid=skip_invalid,
            rename_invalid=rename_invalid,
        )
    except ValueError:
        raise
    except Exception as exc:  # pragma: no cover - unexpected
        logger.error("bootstrap failed", error=str(exc))
        return 1
    return 0


def bootstrap() -> None:
    run(None)


def _bootstrap_impl(
    *, force: bool = False, skip_invalid: bool = False, rename_invalid: bool = False
) -> None:
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
    db.__class__ = BridgeDB

    # Run pending migrations based on stored schema version
    meta_col = db.ensure_col("meta")
    doc = meta_col.get("schema_version")
    if doc is None:
        meta_col.insert({"_key": "schema_version", "value": 0})
        version = 0
    else:
        version = int(getattr(doc, "value", 0))

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
    existing = {c["name"] for c in db.collections()}
    for orig in doc_cols:
        name = orig
        if not is_valid(name):
            if rename_invalid:
                name = to_valid_name(name, existing)
                logger.warning("renamed invalid collection", old=orig, new=name)
            elif skip_invalid:
                logger.warning("skip invalid collection", name=orig)
                continue
            else:
                raise ValueError(f"illegal collection name '{name}'")
        if not db.has_collection(name):
            safe_create_collection(db, name)
            existing.add(name)
    if not db.has_collection("edge"):
        safe_create_collection(db, "edge", edge=True)

    entity = db.collection("entity")
    idx = next(
        (
            i
            for i in entity.indexes()
            if i["type"] == "vector" and i["fields"] == ["embedding"]
        ),
        None,
    )
    if idx and idx.get("dimensions") != embed_dim:
        entity.delete_index(idx["id"])
        idx = None
    mgr = IndexManager(entity, db)
    if not idx:
        mgr.ensure_vector("embedding", dimensions=embed_dim)

    mgr.ensure_hash(["entity_id"], unique=True)

    events = db.collection("event")
    ev_mgr = IndexManager(events, db)
    ev_mgr.ensure_persistent(["time"])
    ev_mgr.ensure_ttl("ts", 30 * 24 * 3600)

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
