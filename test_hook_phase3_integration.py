#!/usr/bin/env python3
"""Test script for Phase 3 hook integration with LangGraph workflow."""

import asyncio
import sys
from unittest.mock import MagicMock

# Test data structures for hook testing
test_messages = [{"role": "user", "content": "mi van a nappaliban?"}]

test_conversation_messages = [
    {"role": "user", "content": "kapcsold fel a nappali lámpákat"},
    {"role": "assistant", "content": "Felkapcsoltam a nappali lámpákat."},
    {"role": "user", "content": "és a hőmérséklet?"},
]

test_openwebui_metadata = [
    {
        "role": "user",
        "content": """### Task:
Generate a concise, 3-5 word title for the following chat history.

<chat_history>
USER: mi van a nappaliban?

ASSISTANT: A nappaliban minden rendben, 22°C, lámpák kikapcsolva.

USER: kapcsold fel őket
</chat_history>

### Output:
JSON format: {"title": "..."}""",
    }
]


async def test_process_request_workflow_endpoint():
    """Test the new /process-request-workflow endpoint directly."""
    print("🧪 Testing /process-request-workflow endpoint")
    print("=" * 50)

    try:
        import httpx
        import os

        # Ensure environment variables are set
        os.environ.setdefault("ARANGO_URL", "http://localhost:8529")
        os.environ.setdefault("ARANGO_USER", "root")
        os.environ.setdefault("ARANGO_PASS", "root")
        os.environ.setdefault("ARANGO_DB", "_system")
        os.environ.setdefault("EMBEDDING_BACKEND", "local")
        os.environ.setdefault("AUTO_BOOTSTRAP", "false")  # Skip bootstrap for tests

        # Test payload
        test_payload = {
            "user_message": "mi van a nappaliban?",
            "conversation_history": [
                {"role": "user", "content": "kapcsold fel a lámpákat"},
                {"role": "assistant", "content": "Felkapcsoltam a lámpákat"},
            ],
            "session_id": "test_hook_integration",
            "conversation_id": "test_hook_integration",
        }

        print(f"1. Testing with payload: {test_payload['user_message']}")
        print(f"   Session ID: {test_payload['session_id']}")
        print(
            f"   Conversation history: {len(test_payload['conversation_history'])} messages"
        )

        # Call the endpoint
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "http://localhost:8000/process-request-workflow", json=test_payload
            )

            print(f"   Status code: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print("   ✅ SUCCESS: Got response")
                print(f"   Entities count: {len(result.get('relevant_entities', []))}")
                print(f"   Context length: {len(result.get('formatted_content', ''))}")
                print(f"   Intent: {result.get('intent', 'unknown')}")

                # Check for Phase 3 metadata
                metadata = result.get("metadata", {})
                if metadata:
                    print(
                        f"   Phase 3 Quality: {metadata.get('workflow_quality', 0.0):.2f}"
                    )
                    print(
                        f"   Memory entities: {metadata.get('memory_entities_count', 0)}"
                    )
                    print(
                        f"   Memory boosted: {metadata.get('memory_boosted_count', 0)}"
                    )
                    print(f"   Phase: {metadata.get('phase', 'unknown')}")
                else:
                    print("   ⚠️ No Phase 3 metadata found")

                # Show some entities
                entities = result.get("relevant_entities", [])
                if entities:
                    print("   Sample entities:")
                    for entity in entities[:3]:
                        entity_id = entity.get("entity_id", "unknown")[:30]
                        state = entity.get("state", "unknown")
                        is_primary = entity.get("is_primary", False)
                        similarity = entity.get("similarity", 0.0)
                        print(
                            f"     - {entity_id}: {state} (primary={is_primary}, sim={similarity:.2f})"
                        )

                return True
            else:
                print(f"   ❌ FAILED: {response.status_code}")
                print(f"   Error: {response.text}")
                return False

    except Exception as e:
        print(f"   ❌ EXCEPTION: {e}")
        return False


async def test_hook_pre_call_integration():
    """Test the hook's pre_call functionality with Phase 3."""
    print("\n🧪 Testing Hook Pre-Call Integration")
    print("=" * 50)

    try:
        from litellm_ha_rag_hooks_phase3 import ha_rag_hook_phase3_instance

        # Mock user API key dict and cache
        mock_user_api_key_dict = MagicMock()
        mock_cache = MagicMock()

        # Test cases
        test_cases = [
            {
                "name": "Simple user query",
                "data": {
                    "messages": test_messages,
                    "headers": {"x-openwebui-chat-id": "test_simple_query"},
                },
                "call_type": "completion",
                "expect_enhancement": True,
            },
            {
                "name": "Multi-turn conversation",
                "data": {
                    "messages": test_conversation_messages,
                    "headers": {"x-openwebui-chat-id": "test_multiturn"},
                },
                "call_type": "completion",
                "expect_enhancement": True,
            },
            {
                "name": "OpenWebUI metadata task",
                "data": {
                    "messages": test_openwebui_metadata,
                    "headers": {"x-openwebui-chat-id": "test_metadata"},
                },
                "call_type": "completion",
                "expect_enhancement": True,
            },
        ]

        results = []

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}. {test_case['name']}")

            try:
                # Call the hook's pre_call method
                enhanced_data = await ha_rag_hook_phase3_instance.async_pre_call_hook(
                    user_api_key_dict=mock_user_api_key_dict,
                    cache=mock_cache,
                    data=test_case["data"].copy(),
                    call_type=test_case["call_type"],
                )

                # Check if data was enhanced
                original_messages = test_case["data"]["messages"]
                enhanced_messages = enhanced_data.get("messages", [])

                if len(enhanced_messages) != len(original_messages):
                    print(
                        f"   ❌ Message count changed: {len(original_messages)} -> {len(enhanced_messages)}"
                    )
                    results.append(False)
                    continue

                # Check for context enhancement in user message
                last_user_msg_original = None
                last_user_msg_enhanced = None

                for msg in reversed(original_messages):
                    if msg.get("role") == "user":
                        last_user_msg_original = msg.get("content", "")
                        break

                for msg in reversed(enhanced_messages):
                    if msg.get("role") == "user":
                        last_user_msg_enhanced = msg.get("content", "")
                        break

                if not last_user_msg_original or not last_user_msg_enhanced:
                    print("   ❌ Could not find user messages")
                    results.append(False)
                    continue

                enhancement_detected = len(last_user_msg_enhanced) > len(
                    last_user_msg_original
                )

                print(f"   Original length: {len(last_user_msg_original)}")
                print(f"   Enhanced length: {len(last_user_msg_enhanced)}")
                print(f"   Enhancement detected: {enhancement_detected}")

                # Check for Phase 3 indicators
                phase3_indicators = [
                    "Phase 3",
                    "workflow",
                    "Smart Home Context",
                    "conversation memory",
                    "LangGraph",
                ]

                phase3_found = any(
                    indicator.lower() in last_user_msg_enhanced.lower()
                    for indicator in phase3_indicators
                )

                print(f"   Phase 3 indicators found: {phase3_found}")

                success = enhancement_detected and (
                    phase3_found or not test_case["expect_enhancement"]
                )
                print(f"   Status: {'✅ PASS' if success else '❌ FAIL'}")

                if enhancement_detected:
                    print(
                        f"   Enhanced context preview: {last_user_msg_enhanced[:200]}..."
                    )

                results.append(success)

            except Exception as e:
                print(f"   ❌ EXCEPTION: {e}")
                results.append(False)

        success_rate = sum(results) / len(results)
        print("\n📊 Hook Pre-Call Integration Results:")
        print(f"   Success rate: {success_rate:.1%}")
        print(f"   Passed: {sum(results)}/{len(results)}")

        return success_rate >= 0.8

    except Exception as e:
        print(f"❌ Hook integration test failed: {e}")
        return False


async def test_full_hook_workflow_integration():
    """Test the complete hook workflow with Phase 3."""
    print("\n🧪 Testing Full Hook-Workflow Integration")
    print("=" * 50)

    # This is a comprehensive integration test
    test_scenarios = [
        {
            "name": "New conversation",
            "messages": [{"role": "user", "content": "mi van a nappaliban?"}],
            "session_id": "new_conversation_test",
            "expect_memory_entities": 0,  # First message, no memory
            "expect_formatted_context": True,
        },
        {
            "name": "Follow-up query with memory",
            "messages": [
                {"role": "user", "content": "kapcsold fel a lámpákat"},
                {"role": "assistant", "content": "Felkapcsoltam a lámpákat"},
                {"role": "user", "content": "és a hőmérséklet?"},
            ],
            "session_id": "followup_memory_test",
            "expect_memory_entities": 1,  # Should find previous entities
            "expect_formatted_context": True,
        },
    ]

    results = []

    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{i}. {scenario['name']}")

        try:
            from litellm_ha_rag_hooks_phase3 import ha_rag_hook_phase3_instance

            # Mock the hook environment
            mock_user_api_key_dict = MagicMock()
            mock_cache = MagicMock()

            # Prepare test data
            test_data = {
                "messages": scenario["messages"],
                "headers": {"x-openwebui-chat-id": scenario["session_id"]},
            }

            # Call hook pre-call
            enhanced_data = await ha_rag_hook_phase3_instance.async_pre_call_hook(
                user_api_key_dict=mock_user_api_key_dict,
                cache=mock_cache,
                data=test_data,
                call_type="completion",
            )

            # Analyze results
            enhanced_messages = enhanced_data.get("messages", [])
            last_user_message = None

            for msg in reversed(enhanced_messages):
                if msg.get("role") == "user":
                    last_user_message = msg.get("content", "")
                    break

            # Check expectations
            has_context = (
                last_user_message and "Smart Home Context" in last_user_message
            )
            has_phase3 = last_user_message and "Phase 3" in last_user_message

            print(f"   Enhanced message has context: {has_context}")
            print(f"   Phase 3 integration detected: {has_phase3}")

            success = has_context or has_phase3
            print(f"   Status: {'✅ PASS' if success else '❌ FAIL'}")

            if success and last_user_message:
                print(f"   Context length: {len(last_user_message)}")
                print(f"   Preview: {last_user_message[:150]}...")

            results.append(success)

        except Exception as e:
            print(f"   ❌ EXCEPTION: {e}")
            results.append(False)

    success_rate = sum(results) / len(results)
    print("\n📊 Full Hook-Workflow Integration Results:")
    print(f"   Success rate: {success_rate:.1%}")
    print(f"   Passed: {sum(results)}/{len(results)}")

    return success_rate >= 0.7


async def main():
    """Run all Phase 3 hook integration tests."""
    print("🚀 Phase 3 Hook Integration Testing")
    print("=" * 50)
    print("Testing LiteLLM hook integration with LangGraph Phase 3 workflow")

    test_results = []

    try:
        # Test 1: Direct endpoint testing
        endpoint_success = await test_process_request_workflow_endpoint()
        test_results.append(("Workflow Endpoint", endpoint_success))

        # Test 2: Hook pre-call integration
        hook_success = await test_hook_pre_call_integration()
        test_results.append(("Hook Pre-Call", hook_success))

        # Test 3: Full integration testing
        full_success = await test_full_hook_workflow_integration()
        test_results.append(("Full Integration", full_success))

        # Overall assessment
        print("\n🏁 Phase 3 Hook Integration Testing Complete!")
        print("=" * 55)

        overall_success = sum(result[1] for result in test_results) / len(test_results)

        print("📊 Test Results:")
        for test_name, success in test_results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"   {test_name}: {status}")

        print(f"\n   Overall success rate: {overall_success:.1%}")

        if overall_success >= 0.8:
            print("🎉 EXCELLENT: Phase 3 hook integration working perfectly!")
        elif overall_success >= 0.6:
            print("✅ GOOD: Phase 3 hook integration mostly working")
        else:
            print("❌ NEEDS WORK: Phase 3 hook integration requires fixes")

        return overall_success >= 0.6

    except Exception as e:
        print(f"\n❌ Hook integration testing failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
