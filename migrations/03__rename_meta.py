from ha_rag_bridge.bootstrap.naming import safe_rename


def run(db):
    col = db.get_col("_meta")
    if col:
        safe_rename(col, "meta")
    col = db.get_col("_bootstrap_log")
    if col:
        safe_rename(col, "bootstrap_log")
