#!/usr/bin/env python3
"""Bootstrap initial semantic clusters for the RAG system."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ha_rag_bridge.logging import get_logger  # noqa: E402
from app.services.cluster_manager import ClusterManager  # noqa: E402

logger = get_logger(__name__)


def main():
    """Bootstrap initial semantic clusters."""
    try:
        logger.info("Starting cluster bootstrap process...")

        # Initialize cluster manager
        cluster_manager = ClusterManager()

        # Bootstrap initial clusters
        cluster_manager.bootstrap_initial_clusters()

        logger.info("✅ Cluster bootstrap completed successfully!")

    except Exception as exc:
        logger.error(f"❌ Cluster bootstrap failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
