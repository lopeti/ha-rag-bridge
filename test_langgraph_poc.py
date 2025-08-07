#!/usr/bin/env python3
"""Test script for LangGraph Phase 1 PoC."""

import asyncio
import sys
from app.langgraph_workflow.workflow import run_rag_workflow
from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)


async def test_scope_detection():
    """Test the LLM-based scope detection with various queries."""

    test_cases = [
        # Micro queries (should get k=5-10)
        {
            "query": "kapcsold fel a lámpát",
            "expected_scope": "micro",
            "description": "Simple control action",
        },
        {
            "query": "és hány fok van a kertben?",
            "expected_scope": "micro",
            "description": "Specific temperature query (was misclassified before)",
        },
        {
            "query": "turn on the kitchen light",
            "expected_scope": "micro",
            "description": "English control action",
        },
        # Macro queries (should get k=15-30)
        {
            "query": "mi van a nappaliban?",
            "expected_scope": "macro",
            "description": "Area-specific status query",
        },
        {
            "query": "kapcsold fel az összes lámpát a konyhában",
            "expected_scope": "macro",
            "description": "Area-scoped control action",
        },
        # Overview queries (should get k=30-50)
        {
            "query": "mi a helyzet otthon?",
            "expected_scope": "overview",
            "description": "House-wide status query",
        },
        {
            "query": "show me all sensors in the house",
            "expected_scope": "overview",
            "description": "Global overview request",
        },
    ]

    print("🧪 Testing LangGraph Phase 1 PoC - Scope Detection")
    print("=" * 60)

    session_id = "test_session_123"
    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print(f"   Query: '{test_case['query']}'")
        print(f"   Expected: {test_case['expected_scope']}")

        try:
            result = await run_rag_workflow(
                user_query=test_case["query"],
                session_id=session_id,
                conversation_history=[],
            )

            detected_scope = result.get("detected_scope")
            scope_confidence = result.get("scope_confidence", 0.0)
            optimal_k = result.get("optimal_k", 0)
            reasoning = result.get("scope_reasoning", "No reasoning provided")
            errors = result.get("errors", [])

            if detected_scope:
                scope_str = (
                    detected_scope.value
                    if hasattr(detected_scope, "value")
                    else str(detected_scope)
                )
            else:
                scope_str = "None"

            print(
                f"   Result: {scope_str} (k={optimal_k}, confidence={scope_confidence:.2f})"
            )
            print(f"   Reasoning: {reasoning}")

            if errors:
                print(f"   ⚠️ Errors: {errors}")

            # Check if result matches expectation
            is_correct = scope_str == test_case["expected_scope"]
            status = "✅ PASS" if is_correct else "❌ FAIL"
            print(f"   Status: {status}")

            results.append(
                {
                    "query": test_case["query"],
                    "expected": test_case["expected_scope"],
                    "actual": scope_str,
                    "correct": is_correct,
                    "confidence": scope_confidence,
                    "k_value": optimal_k,
                    "reasoning": reasoning,
                }
            )

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results.append(
                {
                    "query": test_case["query"],
                    "expected": test_case["expected_scope"],
                    "actual": "ERROR",
                    "correct": False,
                    "error": str(e),
                }
            )

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)

    correct_count = sum(1 for r in results if r.get("correct", False))
    total_count = len(results)
    accuracy = (correct_count / total_count) * 100 if total_count > 0 else 0

    print(f"Accuracy: {correct_count}/{total_count} ({accuracy:.1f}%)")
    print("Target accuracy: >90% (current regex-based: ~67%)")

    if accuracy >= 90:
        print("🎉 EXCELLENT: Target accuracy achieved!")
    elif accuracy >= 70:
        print("✅ GOOD: Accuracy improved, further tuning needed")
    else:
        print("❌ NEEDS WORK: Accuracy below acceptable threshold")

    print("\nDetailed Results:")
    for r in results:
        status = "✅" if r.get("correct") else "❌"
        print(
            f"{status} {r['query'][:30]:<30} → {r['actual']:<8} (expected: {r['expected']})"
        )

    return results


async def test_conversation_analysis():
    """Test conversation analysis with context."""

    print("\n🧪 Testing Conversation Analysis")
    print("=" * 40)

    # Test with conversation history
    conversation_history = [
        {"role": "user", "content": "mi van a nappaliban?"},
        {
            "role": "assistant",
            "content": "A nappaliban 22°C van, a lámpák ki vannak kapcsolva.",
        },
    ]

    result = await run_rag_workflow(
        user_query="és a konyhában?",
        session_id="test_conversation_123",
        conversation_history=conversation_history,
    )

    context = result.get("conversation_context", {})
    print("Query: 'és a konyhában?'")
    print(f"Areas mentioned: {context.get('areas_mentioned', [])}")
    print(f"Is follow-up: {context.get('is_follow_up', False)}")
    print(f"Intent: {context.get('intent', 'unknown')}")

    return result


async def main():
    """Run all PoC tests."""

    print("🚀 LangGraph Phase 1 PoC Verification")
    print("=====================================")

    try:
        # Test scope detection
        await test_scope_detection()

        # Test conversation analysis
        await test_conversation_analysis()

        print("\n🏁 Phase 1 PoC Testing Complete!")
        print("Next steps:")
        print("- Review accuracy results")
        print("- Implement actual LLM integration for scope detection")
        print("- Move to Phase 2: Full workflow nodes")

        return True

    except Exception as e:
        logger.error(f"PoC testing failed: {e}")
        print(f"\n❌ PoC testing failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
