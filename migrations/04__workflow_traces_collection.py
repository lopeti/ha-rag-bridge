#!/usr/bin/env python3
"""
ArangoDB Migration: Create workflow_traces collection
Adds collection for comprehensive workflow debugging and visualization.
"""

from arango import ArangoClient
import os
import sys


def create_workflow_traces_collection(db):
    """Create workflow_traces collection with indexes."""
    from ha_rag_bridge.logging import get_logger

    logger = get_logger(__name__)

    collection_name = "workflow_traces"

    # Create collection if it doesn't exist
    if not db.has_collection(collection_name):
        collection = db.create_collection(collection_name)
        logger.info(f"Created collection: {collection_name}")
    else:
        collection = db.collection(collection_name)
        logger.info(f"Collection {collection_name} already exists")

    # Create indexes for efficient queries
    indexes_to_create = [
        {
            "type": "hash",
            "fields": ["session_id"],
            "name": "idx_session_id",
            "unique": False,
        },
        {
            "type": "skiplist",
            "fields": ["start_time"],
            "name": "idx_start_time",
            "unique": False,
        },
        {"type": "hash", "fields": ["status"], "name": "idx_status", "unique": False},
        {
            "type": "skiplist",
            "fields": ["total_duration_ms"],
            "name": "idx_duration",
            "unique": False,
        },
        {
            "type": "fulltext",
            "fields": ["user_query"],
            "name": "idx_user_query",
            "min_length": 2,
        },
    ]

    # Get existing indexes
    existing_indexes = {idx["name"] for idx in collection.indexes()}

    # Create missing indexes
    for index_def in indexes_to_create:
        if index_def["name"] not in existing_indexes:
            try:
                collection.add_index(index_def)
                logger.info(
                    f"Created index: {index_def['name']} on {index_def['fields']}"
                )
            except Exception as e:
                logger.error(f"Failed to create index {index_def['name']}: {e}")
        else:
            logger.info(f"Index {index_def['name']} already exists")

    # Create TTL index for automatic cleanup (30 days)
    ttl_index_name = "idx_ttl_cleanup"
    if ttl_index_name not in existing_indexes:
        try:
            collection.add_index(
                {
                    "type": "ttl",
                    "fields": ["start_time"],
                    "name": ttl_index_name,
                    "expireAfter": 2592000,  # 30 days in seconds
                }
            )
            logger.info(f"Created TTL index: {ttl_index_name} (30 day cleanup)")
        except Exception as e:
            logger.error(f"Failed to create TTL index: {e}")
    else:
        logger.info(f"TTL index {ttl_index_name} already exists")


def run(db):
    """Bootstrap-compatible migration function."""
    from ha_rag_bridge.logging import get_logger

    logger = get_logger(__name__)

    try:
        # Create workflow_traces collection
        create_workflow_traces_collection(db)
        logger.info("Migration 04: workflow_traces collection setup completed")

    except Exception as e:
        logger.error(f"Migration 04 failed: {e}")
        raise


def main():
    """Main migration function."""

    try:
        # Connect to ArangoDB
        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db_name = os.getenv("ARANGO_DB", "_system")
        db = arango.db(
            db_name,
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        print(f"🔗 Connected to ArangoDB database: {db_name}")

        # Run the migration
        run(db)

        print("✅ Migration 04 completed successfully!")

    except KeyError as e:
        print(f"❌ Missing environment variable: {e}")
        print("Required: ARANGO_URL, ARANGO_USER, ARANGO_PASS")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
