"""
Teszteljük a Home Assistant RAG Bridge integrációt LiteLLM proxy-n keresztül.

Ez a szkript bemutatja, hogyan lehet direktben tesztelni a HA-RAG Bridge és LiteLLM
integrációt, a Home Assistant közbeiktatása nélkül.
"""

import requests
import time
import argparse


def test_ha_rag_api(question):
    """
    Teszteli a HA-RAG Bridge API-t közvetlenül
    """
    print("\n=== HA-RAG Bridge API teszt ===")
    url = "http://localhost:8000/api/query"
    payload = {"question": question, "top_k": 5}

    start_time = time.time()
    response = requests.post(url, json=payload)
    end_time = time.time()

    if response.status_code == 200:
        data = response.json()
        print(f"Sikeres API hívás ({end_time - start_time:.2f} másodperc)")
        print(f"Releváns entitások száma: {len(data.get('relevant_entities', []))}")

        if "formatted_content" in data:
            print("\nFormázott tartalom:")
            print(data["formatted_content"])
        else:
            print("\nReleváns entitások:")
            for entity in data.get("relevant_entities", []):
                print(
                    f"- {entity.get('name', entity['entity_id'])} ({entity['entity_id']}): {entity.get('state', 'unknown')}"
                )
    else:
        print(f"Hiba: {response.status_code} - {response.text}")


def test_litellm_integration(question):
    """
    Teszteli a LiteLLM proxy-t a HA-RAG hook-kal
    """
    print("\n=== LiteLLM + HA-RAG Hook teszt ===")
    url = "http://localhost:4000/v1/chat/completions"
    headers = {"Content-Type": "application/json"}

    # Az alábbi promptban a {{HA_RAG_ENTITIES}} helyére kerülnek a releváns entitások
    payload = {
        "model": "gpt-3.5-turbo",  # Ezt a LiteLLM átirányítja
        "messages": [
            {
                "role": "system",
                "content": (
                    "Te egy hasznos Home Assistant asszisztens vagy. "
                    "Segíthetsz a felhasználónak a kérdéseivel és az okosotthon vezérlésével.\n\n"
                    "Az alábbi kontextus tartalmazza az otthoni eszközök információit:\n\n"
                    "{{HA_RAG_ENTITIES}}\n\n"
                    "Használd ezt az információt a pontos válaszokhoz."
                ),
            },
            {"role": "user", "content": question},
        ],
        "temperature": 0.7,
        "max_tokens": 500,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "light.turn_on",
                    "description": "Bekapcsolja a megadott lámpát",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {
                                "type": "string",
                                "description": "A bekapcsolandó lámpa entity_id-ja",
                            }
                        },
                        "required": ["entity_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "light.turn_off",
                    "description": "Kikapcsolja a megadott lámpát",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {
                                "type": "string",
                                "description": "A kikapcsolandó lámpa entity_id-ja",
                            }
                        },
                        "required": ["entity_id"],
                    },
                },
            },
        ],
    }

    start_time = time.time()
    response = requests.post(url, headers=headers, json=payload)
    end_time = time.time()

    if response.status_code == 200:
        data = response.json()
        print(f"Sikeres API hívás ({end_time - start_time:.2f} másodperc)")

        # Válasz tartalmának kinyerése
        content = data["choices"][0]["message"]["content"]
        print("\nAI válasz:")
        print(content)

        # Tool hívások ellenőrzése
        if "tool_calls" in data["choices"][0]["message"]:
            tool_calls = data["choices"][0]["message"]["tool_calls"]
            print("\nTool hívások:")
            for tool_call in tool_calls:
                function = tool_call["function"]
                print(f"- {function['name']}({function['arguments']})")
    else:
        print(f"Hiba: {response.status_code} - {response.text}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="HA-RAG Bridge és LiteLLM integráció tesztelése"
    )
    parser.add_argument(
        "--question",
        type=str,
        default="Kapcsold be a nappali lámpát",
        help="A tesztelendő kérdés",
    )
    parser.add_argument(
        "--test-type",
        type=str,
        choices=["rag", "litellm", "both"],
        default="both",
        help="A futtatandó teszt típusa",
    )

    args = parser.parse_args()

    if args.test_type in ["rag", "both"]:
        test_ha_rag_api(args.question)

    if args.test_type in ["litellm", "both"]:
        test_litellm_integration(args.question)
