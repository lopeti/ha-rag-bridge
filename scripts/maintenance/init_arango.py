"""Initialize collections and indexes for local development."""

from __future__ import annotations

import os
from arango import ArangoClient

from ha_rag_bridge.db import BridgeDB
from ha_rag_bridge.db.index import IndexManager
from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)


def main() -> None:
    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db = arango.db(
        os.getenv("ARANGO_DB", "_system"),
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )
    db.__class__ = BridgeDB

    events = db.ensure_col("events")
    manager = IndexManager(events)
    manager.ensure_persistent(["time"])
    manager.ensure_ttl("ts", 30 * 24 * 3600)
    logger.info("init completed")


if __name__ == "__main__":
    main()
