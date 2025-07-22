class IndexManager:
    """Helper for creating ArangoDB indexes idempotently."""

    def __init__(self, collection, database=None):
        self.coll = collection
        self.db = database

    def ensure_hash(self, fields, *, unique: bool = False, sparse: bool = True):
        indexes = self.coll.indexes()
        if not any(
            i["type"] in ("hash", "persistent") and i["fields"] == fields
            for i in indexes
        ):
            self.coll.add_persistent_index(
                fields=fields, unique=unique, sparse=sparse
            )

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
        default_nprobe: int = 1,
    ) -> None:
        indexes = self.coll.indexes()
        if any(i["type"] == "vector" and i["fields"] == [field] for i in indexes):
            return

        if n_lists is None:
            try:
                count = int(getattr(self.coll, "count", lambda: 0)())
                n_lists = max(1, count // 15)
            except Exception:
                n_lists = 100

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

    # --- Persistent (skiplist) ---
    def ensure_persistent(self, fields, unique=False, sparse=True):
        indexes = self.coll.indexes()
        if not any(
            idx["type"] in ("hash", "persistent") and idx["fields"] == fields
            for idx in indexes
        ):
            self.coll.add_persistent_index(
                fields=fields, unique=unique, sparse=sparse
            )
