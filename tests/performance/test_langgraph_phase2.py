#!/usr/bin/env python3
"""Test script for LangGraph Phase 2 - Full entity retrieval and context formatting."""

import asyncio
import sys
from app.langgraph_workflow.workflow import run_rag_workflow
from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)


async def test_full_workflow_integration():
    """Test the complete Phase 2 workflow with real entity retrieval and formatting."""

    test_cases = [
        {
            "query": "kapcsold fel a lámpát",
            "description": "Micro scope - Simple control action",
            "expected_scope": "micro",
            "expected_k_range": (5, 10),
            "expected_formatter": "compact",
        },
        {
            "query": "és hány fok van a kertben?",
            "description": "Micro scope - Specific temperature query",
            "expected_scope": "micro",
            "expected_k_range": (5, 10),
            "expected_formatter": "compact",
        },
        {
            "query": "mi van a nappaliban?",
            "description": "Macro scope - Area status query",
            "expected_scope": "macro",
            "expected_k_range": (15, 30),
            "expected_formatter": "grouped_by_area",
        },
        {
            "query": "mi a helyzet otthon?",
            "description": "Overview scope - House-wide status",
            "expected_scope": "overview",
            "expected_k_range": (30, 50),
            "expected_formatter": "tldr",
        },
    ]

    print("🧪 Testing LangGraph Phase 2 - Full Workflow Integration")
    print("=" * 70)

    session_id = "test_phase2_integration"
    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print(f"   Query: '{test_case['query']}'")

        try:
            result = await run_rag_workflow(
                user_query=test_case["query"],
                session_id=session_id,
                conversation_history=[],
            )

            # Analyze results
            detected_scope = result.get("detected_scope")
            scope_str = (
                detected_scope.value
                if hasattr(detected_scope, "value")
                else str(detected_scope)
            )
            optimal_k = result.get("optimal_k", 0)
            retrieved_entities = result.get("retrieved_entities", [])
            cluster_entities = result.get("cluster_entities", [])
            formatted_context = result.get("formatted_context", "")
            formatter_type = result.get("formatter_type", "unknown")
            errors = result.get("errors", [])

            print(f"   Detected scope: {scope_str} (k={optimal_k})")
            print(
                f"   Retrieved entities: {len(retrieved_entities)} total, {len(cluster_entities)} from clusters"
            )
            print(f"   Formatter: {formatter_type}")
            print(f"   Context length: {len(formatted_context)} chars")

            if errors:
                print(f"   ⚠️ Errors: {len(errors)} error(s)")
                for error in errors[-3:]:  # Show last 3 errors
                    print(f"      - {error}")

            # Validate expectations
            scope_correct = scope_str == test_case["expected_scope"]
            k_in_range = (
                test_case["expected_k_range"][0]
                <= optimal_k
                <= test_case["expected_k_range"][1]
            )
            has_entities = len(retrieved_entities) > 0
            has_context = len(formatted_context) > 50

            status_items = []
            if scope_correct:
                status_items.append("✅ Scope")
            else:
                status_items.append("❌ Scope")

            if k_in_range:
                status_items.append("✅ K-value")
            else:
                status_items.append("❌ K-value")

            if has_entities:
                status_items.append("✅ Entities")
            else:
                status_items.append("❌ Entities")

            if has_context:
                status_items.append("✅ Context")
            else:
                status_items.append("❌ Context")

            overall_success = (
                scope_correct
                and k_in_range
                and has_entities
                and has_context
                and not errors
            )
            status = "✅ PASS" if overall_success else "❌ FAIL"

            print(f"   Status: {' | '.join(status_items)} → {status}")

            results.append(
                {
                    "query": test_case["query"],
                    "expected_scope": test_case["expected_scope"],
                    "actual_scope": scope_str,
                    "expected_formatter": test_case["expected_formatter"],
                    "actual_formatter": formatter_type,
                    "optimal_k": optimal_k,
                    "entity_count": len(retrieved_entities),
                    "cluster_entity_count": len(cluster_entities),
                    "context_length": len(formatted_context),
                    "errors": len(errors),
                    "success": overall_success,
                }
            )

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            logger.error(
                f"Test failed for query '{test_case['query']}': {e}", exc_info=True
            )
            results.append(
                {
                    "query": test_case["query"],
                    "success": False,
                    "error": str(e),
                }
            )

    # Summary
    print("\n" + "=" * 70)
    print("📊 PHASE 2 INTEGRATION TEST SUMMARY")
    print("=" * 70)

    successful_count = sum(1 for r in results if r.get("success", False))
    total_count = len(results)
    success_rate = (successful_count / total_count) * 100 if total_count > 0 else 0

    print(f"Success rate: {successful_count}/{total_count} ({success_rate:.1f}%)")
    print("Target: 100% (Phase 2 should handle all core cases)")

    if success_rate >= 100:
        print("🎉 EXCELLENT: Phase 2 integration fully working!")
    elif success_rate >= 75:
        print("✅ GOOD: Phase 2 mostly working, minor issues to fix")
    else:
        print("❌ NEEDS WORK: Phase 2 has significant integration issues")

    # Detailed analysis
    print("\nDetailed Results:")
    for r in results:
        if r.get("success", False):
            entities_info = (
                f"({r['cluster_entity_count']}/{r['entity_count']} from clusters)"
            )
            print(
                f"✅ {r['query'][:40]:<40} → {r['actual_scope']:<8} | {r['actual_formatter']:<15} | {r['entity_count']} entities {entities_info}"
            )
        else:
            error_info = r.get("error", "Multiple issues")[:30]
            print(f"❌ {r['query'][:40]:<40} → ERROR: {error_info}")

    return results


async def test_conversation_flow():
    """Test multi-turn conversation flow with entity context persistence."""

    print("\n🧪 Testing Conversation Flow")
    print("=" * 40)

    session_id = "test_conversation_flow"

    # First query: area-specific
    print("\n1. Initial query about specific area:")
    result1 = await run_rag_workflow(
        user_query="mi van a nappaliban?",
        session_id=session_id,
        conversation_history=[],
    )

    print(f"   Scope: {result1.get('detected_scope')}")
    print(f"   Entities: {len(result1.get('retrieved_entities', []))}")
    print(
        f"   Areas: {result1.get('conversation_context', {}).get('areas_mentioned', [])}"
    )

    # Second query: follow-up
    print("\n2. Follow-up query:")
    conversation_history = [
        {"role": "user", "content": "mi van a nappaliban?"},
        {
            "role": "assistant",
            "content": "A nappaliban 22°C van, a lámpák ki vannak kapcsolva.",
        },
    ]

    result2 = await run_rag_workflow(
        user_query="és a konyhában?",
        session_id=session_id,
        conversation_history=conversation_history,
    )

    print(f"   Scope: {result2.get('detected_scope')}")
    print(f"   Entities: {len(result2.get('retrieved_entities', []))}")
    print(
        f"   Areas: {result2.get('conversation_context', {}).get('areas_mentioned', [])}"
    )
    print(
        f"   Is follow-up: {result2.get('conversation_context', {}).get('is_follow_up', False)}"
    )

    return [result1, result2]


async def test_cluster_effectiveness():
    """Test cluster-based entity retrieval effectiveness."""

    print("\n🧪 Testing Cluster Effectiveness")
    print("=" * 40)

    cluster_test_queries = [
        "hogy termel a napelem?",  # Should use solar cluster
        "milyen a levegő minősége?",  # Should use air quality cluster
        "be van zárva minden ajtó?",  # Should use security cluster
        "mennyire világos a ház?",  # Should use lighting cluster
    ]

    for query in cluster_test_queries:
        print(f"\nQuery: '{query}'")
        result = await run_rag_workflow(
            user_query=query,
            session_id="test_cluster_effectiveness",
            conversation_history=[],
        )

        retrieved_entities = result.get("retrieved_entities", [])
        cluster_entities = result.get("cluster_entities", [])
        cluster_ratio = (
            len(cluster_entities) / len(retrieved_entities) if retrieved_entities else 0
        )

        print(f"   Total entities: {len(retrieved_entities)}")
        print(f"   From clusters: {len(cluster_entities)} ({cluster_ratio:.1%})")
        print(f"   Scope: {result.get('detected_scope')}")

        # Show cluster contexts
        cluster_contexts = set()
        for entity in cluster_entities:
            cluster_context = entity.get("_cluster_context", {})
            if cluster_context:
                cluster_contexts.add(cluster_context.get("cluster_key", "unknown"))

        if cluster_contexts:
            print(f"   Clusters used: {', '.join(cluster_contexts)}")


async def main():
    """Run all Phase 2 integration tests."""

    print("🚀 LangGraph Phase 2 Integration Testing")
    print("======================================")

    try:
        # Test 1: Full workflow integration
        await test_full_workflow_integration()

        # Test 2: Conversation flow
        await test_conversation_flow()

        # Test 3: Cluster effectiveness
        await test_cluster_effectiveness()

        print("\n🏁 Phase 2 Integration Testing Complete!")
        print("\nNext steps:")
        print("- Review any failed test cases")
        print("- Optimize cluster-entity relationships")
        print("- Performance validation and memory optimization")
        print("- Consider Phase 3: Conditional routing and advanced features")

        return True

    except Exception as e:
        logger.error(f"Phase 2 integration testing failed: {e}", exc_info=True)
        print(f"\n❌ Integration testing failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
