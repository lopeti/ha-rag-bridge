def _idx(coll):
    res = coll.indexes()
    return res.get("indexes", res) if isinstance(res, dict) else res


class IndexManager:
    """Helper for creating ArangoDB indexes idempotently."""

    def __init__(self, collection, database=None):
        self.coll = collection
        self.db = database

    def ensure_hash(self, fields, *, unique=False, sparse=True):
        indexes = _idx(self.coll)
        if not any(i.type == "hash" and i.fields == fields for i in indexes):
            self.coll.add_hash_index(fields=fields, unique=unique, sparse=sparse)

    def ensure_ttl(self, field, expire_after):
        indexes = _idx(self.coll)
        if not any(i.type == "ttl" and i.fields == [field] for i in indexes):
            self.coll.add_ttl_index(field=field, expire_after=expire_after)

    def ensure_vector(self, field, *, dimensions: int, metric: str = "cosine"):
        indexes = _idx(self.coll)
        if not any(i.type == "vector" and i.fields == [field] for i in indexes):
            self.coll.add_hnsw_index(
                fields=[field], dimensions=dimensions, similarity=metric
            )

    # --- Persistent (skiplist) ---
    def ensure_persistent(self, fields, unique=False, sparse=True):
        indexes = _idx(self.coll)
        if not any(
            idx.type == "persistent" and idx.fields == fields for idx in indexes
        ):
            self.coll.add_persistent_index(
                fields=fields, unique=unique, sparse=sparse
            )
