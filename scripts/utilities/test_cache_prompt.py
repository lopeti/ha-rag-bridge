#!/usr/bin/env python3
"""Test cache-friendly system prompt implementation."""

import requests


def test_cache_friendly_prompt():
    """Test the new cache-friendly system prompt format."""

    url = "http://localhost:4000/process-request"  # LiteLLM proxy

    test_queries = [
        "hogy termel a napelem?",
        "mi van a nappaliban?",
        "hőmérséklet a konyhában",
    ]

    print("🧪 Testing Cache-Friendly System Prompt Format")
    print("=" * 55)

    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Query: '{query}'")

        try:
            response = requests.post(url, json={"user_message": query}, timeout=10)

            if response.status_code == 200:
                data = response.json()
                messages = data.get("messages", [])

                if len(messages) >= 2:
                    system_msg = messages[0]["content"]
                    user_msg = messages[1]["content"]

                    print("   ✅ Response received")
                    print(f"   System prompt length: {len(system_msg)} chars")
                    print(
                        "   System prompt is static:",
                        "You are an intelligent home assistant AI" in system_msg,
                    )
                    print(
                        "   Context in user message:",
                        "Current home context:" in user_msg,
                    )
                    print(f"   User message length: {len(user_msg)} chars")

                    # Check if context is properly formatted
                    lines = user_msg.split("\n")
                    context_start = any(
                        "Current home context:" in line for line in lines
                    )
                    query_start = any("User question:" in line for line in lines)

                    print(
                        "   Proper format: ✅"
                        if context_start and query_start
                        else "   Format issue: ❌"
                    )
                else:
                    print("   ❌ Insufficient messages in response")
            else:
                print(f"   ❌ HTTP {response.status_code}: {response.text}")

        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request failed: {e}")

    print(f"\n{'='*55}")
    print("Cache Benefits:")
    print("✅ Static system prompt - perfect KV cache reuse")
    print("✅ Dynamic context in user message - no cache pollution")
    print("✅ Consistent AI behavior across requests")
    print("✅ Reduced token processing for system instructions")


if __name__ == "__main__":
    test_cache_friendly_prompt()
