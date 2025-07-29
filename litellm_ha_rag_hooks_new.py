"""
LiteLLM Hook a Home Assistant RAG Bridge integrációhoz

Ez a modul tartalmazza a LiteLLM hook függvényeket a Home Assistant RAG Bridge
integrációhoz, amelyek lehetővé teszik a releváns entitások promptba illesztését
és a tool hívások kezelését.
"""

import os
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

# Konfigurációs értékek
HA_RAG_API_URL = os.getenv("HA_RAG_API_URL", "http://localhost:8000/api")
RAG_PLACEHOLDER = os.getenv("HA_RAG_PLACEHOLDER", "{{HA_RAG_ENTITIES}}")
RAG_QUERY_ENDPOINT = f"{HA_RAG_API_URL}/query"
TOOL_EXECUTION_ENDPOINT = f"{HA_RAG_API_URL}/execute_tool"

# Tool végrehajtás konfigurációk
# "ha-rag-bridge": Ha-rag-bridge végzi a tool végrehajtást
# "caller": A hívó (pl. extended_openai_conversation) végzi a tool végrehajtást
# "both": Mindkettő kapja a tool hívásokat (a ha-rag-bridge végrehajtja, a hívó is megkapja)
# "disabled": Nincs tool végrehajtás
TOOL_EXECUTION_MODE = os.getenv("HA_RAG_TOOL_EXECUTION_MODE", "ha-rag-bridge")

# Logger beállítása
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("litellm_ha_rag_hook")


def litellm_pre_processor(
    messages: List[Dict[str, Any]], model: Optional[str] = None, **kwargs
) -> List[Dict[str, Any]]:
    """
    LiteLLM pre-processor hook a Home Assistant RAG entitások injektálásához.

    Ez a függvény:
    1. Megkeresi a RAG_PLACEHOLDER-t a rendszerüzenetekben
    2. Kivonja a felhasználói kérdést
    3. Meghívja a HA-RAG Bridge API-t a releváns entitások lekéréséhez
    4. Beilleszti a formázott entitásokat a prompt helyére

    Args:
        messages: Az LLM-nek küldendő üzenetek listája
        model: Az LLM modell neve
        kwargs: További paraméterek

    Returns:
        A módosított üzenetek listája
    """
    start_time = datetime.now()
    logger.info(f"HA-RAG Hook indítása: {start_time.isoformat()}")

    # Ellenőrizzük, hogy van-e placeholder a promptban
    has_placeholder = False
    system_message_idx = None

    for i, message in enumerate(messages):
        if (
            message.get("role") == "system"
            and isinstance(message.get("content"), str)
            and RAG_PLACEHOLDER in message["content"]
        ):
            has_placeholder = True
            system_message_idx = i
            break

    # Ha nincs placeholder, nincs teendőnk
    if not has_placeholder or system_message_idx is None:
        logger.info(
            "Nincs RAG placeholder a promptban, az eredeti üzenetek visszaadása"
        )
        return messages

    # Keressünk felhasználói kérdést
    user_question = None
    for message in messages:
        if message.get("role") == "user":
            user_question = message.get("content")
            if user_question:
                break

    # Ha nincs felhasználói kérdés, nincs teendőnk
    if not user_question:
        logger.warning(
            "Nem találtunk felhasználói kérdést, az eredeti üzenetek visszaadása"
        )
        return messages

    # Hívjuk meg a RAG API-t
    try:
        logger.info(f"HA-RAG API hívása: {RAG_QUERY_ENDPOINT}")
        response = requests.post(
            RAG_QUERY_ENDPOINT, json={"question": user_question, "top_k": 5}, timeout=10
        )
        response.raise_for_status()
        rag_data = response.json()

        # Ellenőrizzük, hogy megérkezett-e a formázott tartalom
        formatted_content = rag_data.get("formatted_content")
        if not formatted_content:
            # Próbáljuk meg a relevant_entities-t használni
            relevant_entities = rag_data.get("relevant_entities", [])
            if relevant_entities:
                # Formázzuk a szöveget
                formatted_content = "Available Devices (relevant to your query):\n```csv\nentity_id,name,state,aliases\n"
                for entity in relevant_entities:
                    aliases = "/".join(entity.get("aliases", []))
                    formatted_content += f"{entity['entity_id']},{entity.get('name', entity['entity_id'])},{entity.get('state', 'unknown')},{aliases}\n"
                formatted_content += "```"
            else:
                formatted_content = "No relevant entities found for your query."

        # Cseréljük ki a placeholder-t a formázott tartalomra
        system_message = messages[system_message_idx]
        system_message["content"] = system_message["content"].replace(
            RAG_PLACEHOLDER, formatted_content
        )
        messages[system_message_idx] = system_message

        # Loggoljuk a sikert
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"HA-RAG entitások sikeresen beillesztve, időtartam: {duration:.2f} másodperc"
        )

    except Exception as e:
        # Hiba esetén, hagyjuk az eredeti promptot
        logger.error(f"Hiba a HA-RAG API hívásakor: {str(e)}")
        # Cseréljük ki a placeholder-t egy hibaüzenetre
        system_message = messages[system_message_idx]
        system_message["content"] = system_message["content"].replace(
            RAG_PLACEHOLDER, "Error retrieving Home Assistant entities."
        )
        messages[system_message_idx] = system_message

    return messages


def litellm_post_processor(
    response: Dict[str, Any], model: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    """
    LiteLLM post-processor hook a Home Assistant tool hívások kezeléséhez.

    Ez a függvény:
    1. Ellenőrzi, hogy a válasz tartalmaz-e tool hívásokat
    2. Azonosítja a Home Assistant műveleteket (pl. light.turn_on)
    3. A beállított végrehajtási mód alapján kezeli a tool hívásokat:
       - ha-rag-bridge: Továbbítja a műveleteket a HA-RAG Bridge API-nak végrehajtásra
       - caller: A tool hívásokat változatlanul hagyja, hogy a hívó fél hajtsa végre
       - both: Végrehajtja a műveleteket és a hívó fél is megkapja azokat
       - disabled: Nincs tool végrehajtás
    4. Hozzáadja a végrehajtási eredményeket a válaszhoz, ha szükséges

    Args:
        response: Az LLM válasz
        model: Az LLM modell neve
        kwargs: További paraméterek, amelyek megadhatják a végrehajtási módot

    Returns:
        A módosított válasz
    """
    # Kérés specifikus végrehajtási mód ellenőrzése (a kwargs-ból vagy headerből)
    execution_mode = kwargs.get("tool_execution_mode", TOOL_EXECUTION_MODE)

    # Loggoljuk a használt végrehajtási módot
    logger.info(f"Home Assistant tool végrehajtási mód: {execution_mode}")

    # Ha ki van kapcsolva a tool végrehajtás, visszaadjuk az eredeti választ
    if execution_mode == "disabled":
        logger.info(
            "Home Assistant tool végrehajtás nincs engedélyezve, kihagyjuk a végrehajtást"
        )
        return response

    # Ellenőrizzük, hogy a válasz tartalmaz-e tool hívásokat
    if not response.get("choices"):
        return response

    choice = response["choices"][0]
    if not choice.get("message") or not choice["message"].get("tool_calls"):
        return response

    tool_calls = choice["message"]["tool_calls"]
    ha_tool_calls = []

    # Azonosítsuk a Home Assistant műveleteket
    for tool_call in tool_calls:
        if not tool_call.get("function"):
            continue

        function = tool_call["function"]
        name = function.get("name", "")

        # Home Assistant művelet azonosítása
        if (
            name.startswith("homeassistant.")
            or "." in name
            and name.split(".", 1)[0]
            in [
                "light",
                "switch",
                "climate",
                "sensor",
                "media_player",
                "scene",
                "script",
                "automation",
                "cover",
                "fan",
                "input_boolean",
                "notify",
            ]
        ):
            ha_tool_calls.append(tool_call)

    # Ha nincsenek Home Assistant műveletek, visszaadjuk az eredeti választ
    if not ha_tool_calls:
        return response

    # Ha a caller mód van beállítva, csak a caller hajtja végre a tool hívásokat
    if execution_mode == "caller":
        logger.info("Tool végrehajtás a hívó félnek átadva")
        return response

    try:
        # Ha ha-rag-bridge vagy both mód van beállítva, a ha-rag-bridge végrehajtja a tool hívásokat
        if execution_mode in ["ha-rag-bridge", "both"]:
            logger.info(f"Tool végrehajtás kérése: {len(ha_tool_calls)} tool")
            execute_response = requests.post(
                TOOL_EXECUTION_ENDPOINT, json={"tool_calls": ha_tool_calls}, timeout=15
            )
            execute_response.raise_for_status()
            execute_result = execute_response.json()

            # Tool execution eredmények hozzáadása a válaszhoz
            if "tool_execution_results" in execute_result:
                # Itt kibővítjük a választ a végrehajtás eredményeivel
                logger.info(
                    f"Tool végrehajtási eredmények hozzáadása: {len(execute_result['tool_execution_results'])} eredmény"
                )
                if "execution_results" not in response:
                    response["execution_results"] = []
                response["execution_results"].extend(
                    execute_result["tool_execution_results"]
                )
    except Exception as e:
        logger.error(f"Hiba a Home Assistant tool-ok végrehajtásakor: {str(e)}")

    return response
