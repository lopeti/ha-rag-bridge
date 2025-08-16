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

    db_name = os.getenv("ARANGO_DB", "homeassistant")
    backend_name = os.getenv("EMBEDDING_BACKEND", "local").lower()

    # Try to get actual dimension from embedding backend
    try:
        if backend_name == "local":
            # For LocalBackend, we need to initialize it to get the actual dimension
            from scripts.embedding_backends import LocalBackend

            # Check if model is already loaded to avoid reloading
            if LocalBackend._MODEL is not None:
                embed_dim = LocalBackend.DIMENSION
            else:
                # Initialize backend to get actual dimension
                backend = LocalBackend()
                embed_dim = backend.DIMENSION
        elif backend_name == "openai":
            from scripts.embedding_backends import OpenAIBackend

            embed_dim = OpenAIBackend.DIMENSION
        elif backend_name == "gemini":
            from scripts.embedding_backends import GeminiBackend

            embed_dim = GeminiBackend.DIMENSION
        else:
            # Fallback to environment variable
            embed_dim = int(os.getenv("EMBED_DIM", "384"))
    except Exception as exc:
        logger.warning(
            "Failed to detect embedding dimension from backend, falling back to EMBED_DIM env var",
            error=str(exc),
        )
        embed_dim = int(os.getenv("EMBED_DIM", "384"))

    logger.info(
        "Using embedding dimension for vector index",
        backend=backend_name,
        dimension=embed_dim,
    )

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

    # Ensure vector index exists on the entity collection
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
    if not idx:
        try:
            doc_count = entity.count()
            if doc_count == 0:
                logger.info("Skip vector index – no documents in entity")
            else:
                nLists = max(100, doc_count // 15)
                default_nprobe = min(20, nLists)
                entity.add_index(
                    {
                        "type": "vector",
                        "fields": ["embedding"],
                        "params": {
                            "dimension": embed_dim,
                            "metric": "cosine",
                            "nLists": nLists,
                            "defaultNProbe": default_nprobe,
                        },
                    }
                )
                logger.info(
                    "Created vector index on entity.embedding (nLists=%s, defaultNProbe=%s)",
                    nLists,
                    default_nprobe,
                )
        except Exception as exc:
            logger.error("Failed to create vector index: %s", exc)

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
        # Phase 1: Cluster-based RAG collections
        "cluster",
        "conversation_memory",
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

    # Phase 1: Create cluster_entity edge collection
    if not db.has_collection("cluster_entity"):
        safe_create_collection(db, "cluster_entity", edge=True)

    mgr = IndexManager(entity, db)
    mgr.ensure_hash(["entity_id"], unique=True)

    # Phase 1: Set up cluster collection indexes
    if db.has_collection("cluster"):
        cluster = db.collection("cluster")
        cluster_mgr = IndexManager(cluster, db)
        cluster_mgr.ensure_hash(["type"])

        # Create vector index for cluster embeddings
        idx = next(
            (
                i
                for i in cluster.indexes()
                if i["type"] == "vector" and i["fields"] == ["embedding"]
            ),
            None,
        )
        if idx and idx.get("dimensions") != embed_dim:
            cluster.delete_index(idx["id"])
            idx = None
        if not idx:
            try:
                doc_count = cluster.count()
                if (
                    doc_count >= 10
                ):  # Only create vector index if we have enough documents
                    nLists = max(
                        2, min(10, doc_count // 5)
                    )  # Much smaller nLists for fewer clusters
                    default_nprobe = min(5, nLists)
                    cluster.add_index(
                        {
                            "type": "vector",
                            "fields": ["embedding"],
                            "params": {
                                "dimension": embed_dim,
                                "metric": "cosine",
                                "nLists": nLists,
                                "defaultNProbe": default_nprobe,
                            },
                        }
                    )
                    logger.info(
                        "Created vector index on cluster.embedding (nLists=%s, defaultNProbe=%s)",
                        nLists,
                        default_nprobe,
                    )
            except Exception as exc:
                logger.error("Failed to create cluster vector index: %s", exc)

    # Set up cluster_entity edge indexes
    if db.has_collection("cluster_entity"):
        cluster_entity = db.collection("cluster_entity")
        ce_mgr = IndexManager(cluster_entity, db)
        ce_mgr.ensure_hash(["role"])
        ce_mgr.ensure_persistent(["weight"])

    # Set up conversation_memory indexes
    if db.has_collection("conversation_memory"):
        conv_mem = db.collection("conversation_memory")
        cm_mgr = IndexManager(conv_mem, db)
        cm_mgr.ensure_hash(["conversation_id"])
        cm_mgr.ensure_ttl(
            "ttl", 0
        )  # TTL index with immediate expiry based on ttl field

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
                            "text": {
                                "analyzers": ["text_en"]
                            },  # UI language (Hungarian)
                            "text_system": {
                                "analyzers": ["text_en"]
                            },  # System language (English)
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
                        "fields": {"text": {"analyzers": ["text_en"]}},
                        "features": ["frequency", "norm", "position"],
                    }
                }
            },
        )

    meta_col.insert({"_key": "schema_version", "value": SCHEMA_LATEST}, overwrite=True)

    from .__main__ import ensure_arango_graph

    ensure_arango_graph()
    logger.info("bootstrap finished")
