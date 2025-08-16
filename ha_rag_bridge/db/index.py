from ha_rag_bridge.logging import get_logger


logger = get_logger(__name__)


class IndexManager:
    """Helper for creating ArangoDB indexes idempotently."""

    DEFAULT_N_LISTS: int = 100
    DEFAULT_N_PROBE: int = 4

    def __init__(self, collection, database=None):
        self.coll = collection
        self.db = database

    def ensure_hash(self, fields, *, unique: bool = False, sparse: bool = True):
        indexes = self.coll.indexes()
        if not any(
            i["type"] in ("hash", "persistent") and i["fields"] == fields
            for i in indexes
        ):
            self.coll.add_persistent_index(fields=fields, unique=unique, sparse=sparse)

    def ensure_ttl(self, field, expire_after):
        indexes = self.coll.indexes()
        if not any(i["type"] == "ttl" and i["fields"] == [field] for i in indexes):
            self.coll.add_ttl_index(fields=[field], expiry_time=expire_after)

    def ensure_vector(
        self,
        field,
        *,
        dimensions: int,
        metric: str = "cosine",
        n_lists: int | None = None,
        default_nprobe: int | None = None,
    ) -> bool:
        indexes = self.coll.indexes()
        if any(i["type"] == "vector" and i["fields"] == [field] for i in indexes):
            return False

        try:
            doc_cnt = int(getattr(self.coll, "count", lambda: 0)())
        except (AttributeError, TypeError):
            doc_cnt = 0

        if doc_cnt < 1:
            logger.info("Skip vector index – collection empty (%s)", self.coll.name)
            return False

        n_lists = n_lists or max(1, doc_cnt // 15, self.DEFAULT_N_LISTS)
        n_lists = min(n_lists, doc_cnt)

        default_nprobe = default_nprobe or self.DEFAULT_N_PROBE
        default_nprobe = min(default_nprobe, n_lists)

        self.coll.add_index(
            {
                "type": "vector",
                "fields": [field],
                "params": {
                    "metric": metric,
                    "dimension": dimensions,
                    "nLists": n_lists,
                    "defaultNProbe": default_nprobe,
                },
            }
        )
        return True

    # --- Persistent (skiplist) ---
    def ensure_persistent(self, fields, unique=False, sparse=True):
        indexes = self.coll.indexes()
        if not any(
            idx["type"] in ("hash", "persistent") and idx["fields"] == fields
            for idx in indexes
        ):
            self.coll.add_persistent_index(fields=fields, unique=unique, sparse=sparse)
