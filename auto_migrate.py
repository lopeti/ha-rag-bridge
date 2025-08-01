"""Minimal migration helper for older installations."""

from __future__ import annotations

import os
from arango import ArangoClient

from ha_rag_bridge.db import BridgeDB


def main() -> None:
    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db = arango.db(
        os.getenv("ARANGO_DB", "_system"),
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )
    db.__class__ = BridgeDB

    coll = db.collection("events")
    if not any(
        i["type"] == "persistent" and i["fields"] == ["time"] for i in coll.indexes()
    ):
        coll.indexes.create.persistent(fields=["time"])


if __name__ == "__main__":
    main()
