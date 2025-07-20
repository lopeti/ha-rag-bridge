def run(db):
    if not db.has_collection("_meta"):
        db.create_collection("_meta")
