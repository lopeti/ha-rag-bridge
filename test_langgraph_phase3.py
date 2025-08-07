#!/usr/bin/env python3
"""Test script for LangGraph Phase 3 - Advanced workflow with conversation memory and conditional routing."""

import asyncio
import sys
from app.langgraph_workflow.workflow import run_rag_workflow
from app.services.conversation_memory import ConversationMemoryService
from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)


async def test_conversation_memory_persistence():
    """Test conversation memory storage and retrieval across multiple queries."""

    print("🧪 Testing Conversation Memory Persistence")
    print("=" * 50)

    memory_service = ConversationMemoryService()
    session_id = "test_memory_persistence"

    # Clear any existing memory for clean test
    await memory_service._cleanup_expired_memory(session_id)

    test_queries = [
        "mi van a nappaliban?",
        "és a hőmérséklet?",
        "kapcsold fel a lámpákat",
        "mennyi ideje égnek?",
    ]

    conversation_history = []
    results = []

    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Query: '{query}'")

        # Run workflow
        result = await run_rag_workflow(
            user_query=query,
            session_id=session_id,
            conversation_history=conversation_history.copy(),
        )

        # Check memory integration
        memory_entities = result.get("memory_entities", [])
        retrieved_entities = result.get("retrieved_entities", [])
        memory_boosted = [e for e in retrieved_entities if e.get("_memory_boosted")]

        print(f"   Memory entities: {len(memory_entities)}")
        print(f"   Retrieved entities: {len(retrieved_entities)}")
        print(f"   Memory boosted: {len(memory_boosted)}")

        # Debug: Show more details about memory service
        if i == 1:  # First query - should have no memory
            print("   DEBUG: First query, no memory expected")
        else:
            print("   DEBUG: Follow-up query, memory service result:")
            if memory_entities:
                for mem in memory_entities[:2]:
                    print(
                        f"     - {mem.get('entity_id', 'unknown')[:30]}: relevance={mem.get('memory_relevance', 0):.2f}"
                    )
            else:
                print(
                    f"     - No memory entities found (check conversation_id={session_id})"
                )

        # Show memory boost details
        if memory_boosted:
            for entity in memory_boosted[:3]:
                entity_id = entity.get("entity_id", "unknown")[:30]
                boost = entity.get("_memory_boost", 1.0)
                relevance = entity.get("_memory_relevance", 0)
                print(
                    f"     - {entity_id}: boost={boost:.2f}, relevance={relevance:.2f}"
                )

        # Add to conversation history for next query
        conversation_history.extend(
            [
                {"role": "user", "content": query},
                {"role": "assistant", "content": f"Processed query {i}"},
            ]
        )

        results.append(
            {
                "query": query,
                "memory_entities": len(memory_entities),
                "memory_boosted": len(memory_boosted),
                "total_entities": len(retrieved_entities),
            }
        )

    # Test memory stats
    print("\n📊 Memory Statistics:")
    memory_stats = await memory_service.get_conversation_stats(session_id)
    if memory_stats:
        print(f"   Entity count: {memory_stats['entity_count']}")
        print(f"   Query count: {memory_stats['query_count']}")
        print(f"   Areas: {memory_stats['top_areas']}")
        print(f"   TTL remaining: {memory_stats['minutes_remaining']:.1f} minutes")

    # Summary
    print("\n✅ Conversation Memory Test Results:")
    for i, result in enumerate(results, 1):
        memory_ratio = result["memory_boosted"] / max(1, result["total_entities"])
        print(
            f"   Query {i}: {result['memory_boosted']}/{result['total_entities']} boosted ({memory_ratio:.1%})"
        )

    return results


async def test_conditional_routing_and_error_handling():
    """Test conditional routing logic and error recovery mechanisms."""

    print("\n🧪 Testing Conditional Routing & Error Handling")
    print("=" * 55)

    test_cases = [
        {
            "query": "kapcsold fel a lámpát",
            "description": "Normal micro query - should use main flow",
            "expect_retries": False,
            "expect_fallbacks": False,
        },
        {
            "query": "qwerty xyz invalid query 12345",
            "description": "Invalid query - should trigger fallbacks",
            "expect_retries": True,
            "expect_fallbacks": True,
        },
        {
            "query": "mi van otthon mindenhol?",
            "description": "Complex overview query - may need retries",
            "expect_retries": False,
            "expect_fallbacks": False,
        },
        {
            "query": "",
            "description": "Empty query - should handle gracefully",
            "expect_retries": True,
            "expect_fallbacks": True,
        },
    ]

    session_id = "test_routing_errors"
    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print(f"   Query: '{test_case['query']}'")

        try:
            result = await run_rag_workflow(
                user_query=test_case["query"],
                session_id=f"{session_id}_{i}",
                conversation_history=[],
            )

            # Analyze routing and error handling
            errors = result.get("errors", [])
            retry_count = result.get("retry_count", 0)
            fallback_used = result.get("fallback_used", False)
            diagnostics = result.get("diagnostics", {})

            print(f"   Errors: {len(errors)}")
            print(f"   Retries: {retry_count}")
            print(f"   Fallback used: {fallback_used}")

            if errors:
                print(f"   Error types: {[e[:50] for e in errors[:2]]}")

            if diagnostics:
                overall_quality = diagnostics.get("overall_quality", 0.0)
                print(f"   Quality score: {overall_quality:.2f}")

            # Validation
            routing_correct = True
            if test_case["expect_retries"] and retry_count == 0:
                routing_correct = False
                print("   ❌ Expected retries but none occurred")
            elif not test_case["expect_retries"] and retry_count > 0:
                print(f"   ⚠️ Unexpected retries: {retry_count}")

            if test_case["expect_fallbacks"] and not fallback_used:
                routing_correct = False
                print("   ❌ Expected fallbacks but none used")
            elif not test_case["expect_fallbacks"] and fallback_used:
                print("   ⚠️ Unexpected fallback usage")

            status = "✅ PASS" if routing_correct and len(errors) <= 2 else "❌ FAIL"
            print(f"   Status: {status}")

            results.append(
                {
                    "query": test_case["query"],
                    "errors": len(errors),
                    "retries": retry_count,
                    "fallback_used": fallback_used,
                    "quality": overall_quality if diagnostics else 0.0,
                    "success": routing_correct,
                }
            )

        except Exception as e:
            print(f"   ❌ Exception: {e}")
            results.append(
                {"query": test_case["query"], "exception": str(e), "success": False}
            )

    return results


async def test_multi_turn_context_enhancement():
    """Test multi-turn conversation with context enhancement."""

    print("\n🧪 Testing Multi-turn Context Enhancement")
    print("=" * 45)

    session_id = "test_multiturn_context"
    conversation_flow = [
        ("mi van a nappaliban?", "Initial area query"),
        ("és a hőmérséklet?", "Follow-up temperature query"),
        ("kapcsold fel a lámpákat", "Action based on area context"),
        ("mi van a konyhában?", "Switch to different area"),
        ("ott is fel kell kapcsolni őket?", "Context-dependent follow-up"),
    ]

    conversation_history = []
    results = []

    for i, (query, description) in enumerate(conversation_flow, 1):
        print(f"\n{i}. {description}")
        print(f"   Query: '{query}'")

        result = await run_rag_workflow(
            user_query=query,
            session_id=session_id,
            conversation_history=conversation_history.copy(),
        )

        # Analyze context enhancement
        context = result.get("conversation_context", {})
        memory_entities = result.get("memory_entities", [])
        is_follow_up = context.get("is_follow_up", False)
        areas_mentioned = context.get("areas_mentioned", [])

        print(f"   Follow-up detected: {is_follow_up}")
        print(f"   Areas in context: {areas_mentioned}")
        print(f"   Memory entities: {len(memory_entities)}")

        # Check context enhancement quality
        context_quality = "Good"
        if i > 1 and not memory_entities:
            context_quality = "Missing memory"
        elif i > 2 and not is_follow_up and "kapcsold" not in query:
            context_quality = "Missing follow-up detection"

        print(f"   Context quality: {context_quality}")

        # Add to conversation history
        conversation_history.extend(
            [
                {"role": "user", "content": query},
                {"role": "assistant", "content": f"Processed: {description}"},
            ]
        )

        results.append(
            {
                "turn": i,
                "query": query,
                "is_follow_up": is_follow_up,
                "areas": areas_mentioned,
                "memory_count": len(memory_entities),
                "context_quality": context_quality,
            }
        )

    # Summary
    print("\n📊 Multi-turn Context Analysis:")
    follow_up_accuracy = sum(1 for r in results[1:] if r["is_follow_up"]) / max(
        1, len(results) - 1
    )
    memory_effectiveness = sum(1 for r in results[1:] if r["memory_count"] > 0) / max(
        1, len(results) - 1
    )

    print(f"   Follow-up detection rate: {follow_up_accuracy:.1%}")
    print(f"   Memory utilization rate: {memory_effectiveness:.1%}")

    return results


async def test_workflow_diagnostics_and_quality():
    """Test workflow diagnostics and quality assessment."""

    print("\n🧪 Testing Workflow Diagnostics & Quality Assessment")
    print("=" * 55)

    test_queries = [
        ("kapcsold fel a nappali lámpákat", "High-quality specific query"),
        ("mi van", "Low-quality vague query"),
        ("hány fok van a konyhában most?", "Medium-quality specific query"),
        ("minden rendben otthon?", "Overview quality query"),
    ]

    session_id = "test_diagnostics"
    quality_scores = []

    for i, (query, description) in enumerate(test_queries, 1):
        print(f"\n{i}. {description}")
        print(f"   Query: '{query}'")

        result = await run_rag_workflow(
            user_query=query,
            session_id=f"{session_id}_{i}",
            conversation_history=[],
        )

        # Analyze diagnostics
        diagnostics = result.get("diagnostics", {})

        if diagnostics and "overall_quality" in diagnostics:
            quality = diagnostics["overall_quality"]
            conv_quality = diagnostics.get("conversation_analysis_quality", 0.0)
            scope_quality = diagnostics.get("scope_detection_quality", 0.0)
            entity_quality = diagnostics.get("entity_retrieval_quality", 0.0)
            format_quality = diagnostics.get("context_formatting_quality", 0.0)
            recommendations = diagnostics.get("recommendations", [])

            print(f"   Overall quality: {quality:.2f}")
            print(
                f"   Component scores: conv={conv_quality:.2f}, scope={scope_quality:.2f}, "
                f"entity={entity_quality:.2f}, format={format_quality:.2f}"
            )

            if recommendations:
                print(f"   Recommendations: {len(recommendations)} items")
                for rec in recommendations[:2]:
                    print(f"     - {rec}")

            quality_scores.append(
                {
                    "query": query,
                    "overall": quality,
                    "components": {
                        "conversation": conv_quality,
                        "scope": scope_quality,
                        "entity": entity_quality,
                        "formatting": format_quality,
                    },
                    "recommendations": len(recommendations),
                }
            )
        else:
            print("   ❌ No diagnostics available")
            quality_scores.append(
                {"query": query, "overall": 0.0, "error": "No diagnostics"}
            )

    # Quality analysis
    if quality_scores:
        avg_quality = sum(q.get("overall", 0.0) for q in quality_scores) / len(
            quality_scores
        )
        print("\n📊 Quality Analysis:")
        print(f"   Average quality score: {avg_quality:.2f}")
        print(
            f"   High quality queries (>0.7): {sum(1 for q in quality_scores if q.get('overall', 0) > 0.7)}"
        )
        print(
            f"   Low quality queries (<0.5): {sum(1 for q in quality_scores if q.get('overall', 0) < 0.5)}"
        )

    return quality_scores


async def main():
    """Run all Phase 3 integration tests."""

    print("🚀 LangGraph Phase 3 Integration Testing")
    print("=" * 45)
    print("Features: Conversation Memory + Conditional Routing + Error Handling")

    try:
        # Test 1: Conversation memory persistence
        memory_results = await test_conversation_memory_persistence()

        # Test 2: Conditional routing and error handling
        routing_results = await test_conditional_routing_and_error_handling()

        # Test 3: Multi-turn context enhancement
        context_results = await test_multi_turn_context_enhancement()

        # Test 4: Workflow diagnostics and quality
        quality_results = await test_workflow_diagnostics_and_quality()

        # Overall assessment
        print("\n🏁 Phase 3 Integration Testing Complete!")
        print("=" * 45)

        # Success metrics
        memory_success = sum(
            1 for r in memory_results if r["memory_boosted"] > 0
        ) / len(memory_results)
        routing_success = sum(
            1 for r in routing_results if r.get("success", False)
        ) / len(routing_results)
        context_success = sum(
            1 for r in context_results if r["context_quality"] == "Good"
        ) / len(context_results)
        quality_success = sum(
            1 for r in quality_results if r.get("overall", 0) > 0.6
        ) / len(quality_results)

        overall_success = (
            memory_success + routing_success + context_success + quality_success
        ) / 4

        print("📊 Success Metrics:")
        print(f"   Memory utilization: {memory_success:.1%}")
        print(f"   Routing reliability: {routing_success:.1%}")
        print(f"   Context enhancement: {context_success:.1%}")
        print(f"   Quality assessment: {quality_success:.1%}")
        print(f"   Overall Phase 3 success: {overall_success:.1%}")

        if overall_success >= 0.8:
            print("🎉 EXCELLENT: Phase 3 features working exceptionally well!")
        elif overall_success >= 0.6:
            print(
                "✅ GOOD: Phase 3 features mostly working, minor optimizations needed"
            )
        else:
            print("❌ NEEDS WORK: Phase 3 features require significant improvements")

        print("\n📋 Next Steps:")
        if overall_success >= 0.8:
            print("- Performance optimization and load testing")
            print("- Integration with LiteLLM hook for production")
            print("- Documentation and deployment preparation")
        else:
            print("- Fix failing test cases and error handling")
            print("- Optimize conversation memory algorithms")
            print("- Review routing logic and fallback mechanisms")

        return overall_success >= 0.6

    except Exception as e:
        logger.error(f"Phase 3 integration testing failed: {e}", exc_info=True)
        print(f"\n❌ Integration testing failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
