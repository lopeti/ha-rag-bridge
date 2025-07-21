from ha_rag_bridge.bootstrap.naming import safe_rename


def run(db):
    if db._collection("_meta"):
        safe_rename(db._collection("_meta"), "meta")
    if db._collection("_bootstrap_log"):
        safe_rename(db._collection("_bootstrap_log"), "bootstrap_log")
