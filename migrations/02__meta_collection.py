from ha_rag_bridge.bootstrap.naming import safe_create_collection


def run(db):
    if not db.has_collection("_meta"):
        safe_create_collection(db, "_meta")
