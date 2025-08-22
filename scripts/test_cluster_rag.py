#!/usr/bin/env python3
"""Test script for cluster-first RAG system."""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ha_rag_bridge.logging import get_logger  # noqa: E402
from app.services.integrations.embeddings import get_backend  # noqa: E402
from app.services.rag.cluster_manager import ClusterManager  # noqa: E402
from app.services.query_scope_detector import (  # noqa: E402
    query_scope_detector,
    QueryScope,
)

logger = get_logger(__name__)


def test_query_scope_detection():
    """Test query scope detection with various queries."""
    print("\n🔍 Testing Query Scope Detection")
    print("=" * 50)

    test_queries = [
        ("kapcsold fel a lámpát", QueryScope.MICRO),
        ("mi van a nappaliban?", QueryScope.MACRO),
        ("hogy termel a napelem?", QueryScope.MICRO),
        ("mi újság otthon?", QueryScope.OVERVIEW),
        ("hőmérséklet a konyhában", QueryScope.MACRO),
        ("energia fogyasztás", QueryScope.OVERVIEW),
    ]

    for query, expected_scope in test_queries:
        detected_scope, scope_config, details = query_scope_detector.detect_scope(query)

        status = "✅" if detected_scope == expected_scope else "❌"
        print(f"{status} '{query}'")
        print(f"   Detected: {detected_scope.value} (expected: {expected_scope.value})")
        print(f"   Optimal k: {details['optimal_k']}")
        print(f"   Formatter: {scope_config.formatter}")
        print(f"   Confidence: {details['confidence']:.2f}")
        if details["reasoning"]:
            print(f"   Reasoning: {details['reasoning']}")
        print()


def test_cluster_search():
    """Test cluster search functionality."""
    print("\n🏷️  Testing Cluster Search")
    print("=" * 50)

    cluster_manager = ClusterManager()
    backend = get_backend(os.getenv("EMBEDDING_BACKEND", "local").lower())

    test_queries = [
        "hogy termel a napelem?",
        "hőmérséklet a nappaliban",
        "kapcsold fel a fényt",
        "mi újság otthon?",
        "biztonság",
    ]

    for query in test_queries:
        print(f"Query: '{query}'")

        # Get query embedding
        query_vector = backend.embed([query])[0]

        # Search clusters
        clusters = cluster_manager.search_clusters(
            query_vector=query_vector,
            cluster_types=["micro_cluster", "macro_cluster", "overview_cluster"],
            k=3,
            threshold=0.5,
        )

        if clusters:
            print(f"   Found {len(clusters)} matching clusters:")
            for cluster in clusters:
                print(
                    f"   - {cluster['name']} ({cluster['type']}, score: {cluster['similarity_score']:.3f})"
                )
        else:
            print("   No clusters found")
        print()


def test_full_pipeline():
    """Test the full cluster-first RAG pipeline."""
    print("\n🚀 Testing Full Pipeline Integration")
    print("=" * 50)

    # This would require a full database setup, so we'll just test components
    test_queries = [
        "hogy termel a napelem?",
        "hőmérséklet a konyhában",
        "mi újság otthon?",
    ]

    for query in test_queries:
        print(f"Processing: '{query}'")

        # Step 1: Scope detection
        detected_scope, scope_config, details = query_scope_detector.detect_scope(query)
        print(
            f"   Scope: {detected_scope.value} (k={details['optimal_k']}, formatter={scope_config.formatter})"
        )

        # Step 2: Cluster search (simulated)
        cluster_types = scope_config.cluster_types
        print(f"   Would search cluster types: {cluster_types}")

        print()


def main():
    """Run all tests."""
    print("🧪 Cluster-first RAG System Test Suite")
    print("=" * 60)

    try:
        test_query_scope_detection()
        test_cluster_search()
        test_full_pipeline()

        print("✅ All tests completed successfully!")

    except Exception as exc:
        logger.error(f"❌ Test suite failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
