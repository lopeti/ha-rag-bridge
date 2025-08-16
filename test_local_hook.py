#!/usr/bin/env python3
"""
Test script for local LiteLLM RAG hook integration
"""
import requests
import sys


def test_local_litellm_hook():
    """Test the local LiteLLM with RAG hook"""

    # LiteLLM endpoint
    url = "http://localhost:4000/chat/completions"

    # Test payload with HA RAG placeholder
    payload = {
        "model": "gemini-flash",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful home assistant AI. You can answer questions and control the home.\n\nUse the given context about home devices to provide accurate information.\n\n{{HA_RAG_ENTITIES}}\n\nIf there's a way to help using the available devices, suggest how to do it.",
            },
            {"role": "user", "content": "Mennyi a kertben a hőmérséklet?"},
        ],
    }

    headers = {"Content-Type": "application/json", "Authorization": "Bearer test"}

    try:
        print("🚀 Testing local LiteLLM RAG hook...")
        print(f"📡 Sending request to: {url}")
        print(f"🤖 Model: {payload['model']}")
        print(f"❓ Question: {payload['messages'][1]['content']}")

        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            print("✅ SUCCESS!")
            print(f"🏠 Assistant response: {content}")
            print(f"📊 Token usage: {result.get('usage', {})}")

            # Check if RAG entities were injected (should contain specific temperature)
            if any(
                keyword in content.lower()
                for keyword in ["°c", "celsius", "fok", "hőmérséklet"]
            ):
                print("🎯 RAG hook working - specific temperature data found!")
                return True
            else:
                print("⚠️  RAG hook might not be working - no specific temperature data")
                return False

        else:
            print(f"❌ ERROR: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to LiteLLM (is it running?)")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


if __name__ == "__main__":
    success = test_local_litellm_hook()
    sys.exit(0 if success else 1)
