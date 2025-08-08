"""LiteLLM Hook for Home Assistant RAG Bridge integration

This module provides LiteLLM callback hooks that:
1. Extract the LAST user question from conversations (including OpenWebUI metadata tasks)
2. Inject conversation-aware context into user messages for cache optimization
3. Optionally execute Home‑Assistant tool calls and attach their results (post‑call)

Cache-friendly approach: Entities are injected into user messages instead of system 
messages to maximize LLM KV-cache reuse and improve response times.

The implementation follows LiteLLM's `CustomLogger` interface and must be
referenced from `litellm_config.yaml` like so:

```yaml
litellm_settings:
  callbacks: litellm_ha_rag_hooks.ha_rag_hook_instance
```
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Literal, List

import httpx
from litellm.integrations.custom_logger import CustomLogger
from litellm.types.utils import LLMResponseTypes

# Simple type hints without importing proxy server
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from litellm.proxy.proxy_server import DualCache, UserAPIKeyAuth
else:
    DualCache = UserAPIKeyAuth = object

# ──────────────────────────────────────────────────────────────────────────────
# Configuration constants ─ values are injected via environment variables
# ──────────────────────────────────────────────────────────────────────────────

HA_RAG_API_URL: str = os.getenv("HA_RAG_API_URL", "http://ha-rag-bridge:8000")
RAG_PLACEHOLDER: str = os.getenv("HA_RAG_PLACEHOLDER", "{{HA_RAG_ENTITIES}}")
RAG_QUERY_ENDPOINT: str = f"{HA_RAG_API_URL}/process-request"
TOOL_EXECUTION_ENDPOINT: str = f"{HA_RAG_API_URL}/execute_tool"

# Tool‑execution behaviour: "ha-rag-bridge"|"caller"|"both"|"disabled"
TOOL_EXECUTION_MODE: str = os.getenv("HA_RAG_TOOL_EXECUTION_MODE", "ha-rag-bridge")

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("litellm_ha_rag_hook")

# ──────────────────────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────────────────────


def _find_system_placeholder(messages: List[Dict[str, Any]]) -> int | None:
    """Return index of first system message containing the placeholder, else None."""
    for idx, msg in enumerate(messages):
        if (
            msg.get("role") == "system"
            and isinstance(msg.get("content"), str)
            and RAG_PLACEHOLDER in msg["content"]
        ):
            return idx
    return None


def _extract_user_question_and_context(
    messages: List[Dict[str, Any]]
) -> tuple[str | None, List[Dict[str, Any]]]:
    """Extract the LAST user question and full conversation context."""
    import re

    logger.debug(f"Extracting user question and context from {len(messages)} messages")

    # OpenWebUI metadata task patterns
    metadata_patterns = [
        r"### Task:",
        r"Generate a concise, 3-5 word title",
        r"Generate 1-3 broad tags categorizing",
        r"main themes of the chat history",
        r"### Guidelines:",
        r"### Output:",
        r"JSON format:",
    ]

    # Check if the last message is a metadata task
    if messages:
        last_msg = messages[-1]
        if (
            last_msg.get("role") == "user"
            and isinstance(last_msg.get("content"), str)
            and any(
                re.search(pattern, last_msg["content"], re.IGNORECASE)
                for pattern in metadata_patterns
            )
        ):

            logger.debug("Last message is OpenWebUI metadata task")
            # Extract the actual conversation from chat history
            chat_history_match = re.search(
                r"<chat_history>(.*?)</chat_history>", last_msg["content"], re.DOTALL
            )
            if chat_history_match:
                chat_content = chat_history_match.group(1)
                logger.debug(f"Found chat history: '{chat_content[:200]}...'")
                # Find the last USER question (most recent)
                user_questions = re.findall(
                    r"USER:\s*(.+?)(?=\nASSISTANT:|$)",
                    chat_content,
                    re.DOTALL | re.MULTILINE,
                )
                if user_questions:
                    question = user_questions[-1].strip()
                    logger.info(
                        f"Extracted LAST user question from metadata: '{question}'"
                    )
                    # Build conversation context from chat history
                    conversation_context = _parse_chat_history(chat_content)
                    return question, conversation_context

            logger.debug("No valid chat history in metadata task")
            return None, []

    # For regular conversations, find the LAST user message
    last_user_question = None
    conversation_context = []

    # Build full conversation context and find last user message
    for msg in messages:
        if msg.get("role") in ["user", "assistant", "system"]:
            conversation_context.append(
                {"role": msg.get("role"), "content": str(msg.get("content", ""))}
            )

            # Track the last user message
            if msg.get("role") == "user":
                last_user_question = str(msg.get("content", "")).strip()

    if last_user_question:
        logger.info(f"Using LAST user question: '{last_user_question[:100]}...'")
        return last_user_question, conversation_context

    logger.debug("No user question found in conversation")
    return None, []


def _parse_chat_history(chat_content: str) -> List[Dict[str, Any]]:
    """Parse OpenWebUI chat history format into conversation context."""
    import re

    conversation = []

    # Split by USER/ASSISTANT markers
    parts = re.split(r"\n(USER:|ASSISTANT:)", chat_content)

    current_role = None
    current_content = ""

    for i, part in enumerate(parts):
        part = part.strip()
        if part == "USER:":
            if current_role and current_content:
                conversation.append(
                    {"role": current_role, "content": current_content.strip()}
                )
            current_role = "user"
            current_content = ""
        elif part == "ASSISTANT:":
            if current_role and current_content:
                conversation.append(
                    {"role": current_role, "content": current_content.strip()}
                )
            current_role = "assistant"
            current_content = ""
        else:
            if current_role:
                current_content += part

    # Add the last message
    if current_role and current_content:
        conversation.append({"role": current_role, "content": current_content.strip()})

    return conversation


def _extract_conversation_insights(
    conversation_context: List[Dict[str, Any]]
) -> str | None:
    """Extract insights and previously mentioned entities from conversation."""
    import re

    # Collect entity mentions, areas, and key topics from conversation
    insights = []
    mentioned_entities = set()
    mentioned_areas = set()

    # Common Hungarian area names
    area_patterns = [
        r"\b(nappali|nappaliban|nappaliba)\b",
        r"\b(konyha|konyhában|konyhába)\b",
        r"\b(hálószoba|hálószobában|hálószobába)\b",
        r"\b(fürdő|fürdőben|fürdőbe|fürdőszoba)\b",
        r"\b(iroda|irodában|irodába)\b",
        r"\b(gyerekszoba|gyerekszobában|gyerekszobába)\b",
        r"\b(kamra|kamrában|kamrába)\b",
        r"\b(pince|pincében|pincébe)\b",
        r"\b(padlás|padláson|padlásra)\b",
    ]

    # Entity-like patterns
    entity_patterns = [
        r"\b(hőmérséklet|fok|°C)\b",
        r"\b(lámpa|világítás|fény)\b",
        r"\b(fűtés|klíma|légkondi)\b",
        r"\b(ajtó|ablak|redőny)\b",
        r"\b(napelem|battery|akkumulátor)\b",
        r"\b(szenzor|érzékelő|detector)\b",
    ]

    for msg in conversation_context[:-1]:  # Exclude the current message
        if msg.get("role") in ["user", "assistant"]:
            content = msg.get("content", "").lower()

            # Extract area mentions
            for pattern in area_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    area = match.split("|")[0]  # Take first variant
                    mentioned_areas.add(area)

            # Extract entity type mentions
            for pattern in entity_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    entity_type = match.split("|")[0]  # Take first variant
                    mentioned_entities.add(entity_type)

    # Build insights summary
    if mentioned_areas:
        insights.append(f"Említett helyiségek: {', '.join(mentioned_areas)}")

    if mentioned_entities:
        insights.append(f"Tárgyalt eszköz típusok: {', '.join(mentioned_entities)}")

    # Add context about conversation flow
    if len(conversation_context) > 3:
        insights.append("Folyamatos beszélgetés - korábbi kontextus figyelembevétele")

    return " | ".join(insights) if insights else None


def _extract_stable_session_id(data: dict, messages: List[Dict[str, Any]]) -> str:
    """Extract stable session ID from OpenWebUI standard headers or generate fallback."""
    from datetime import datetime

    # Priority 1: OpenWebUI Standard Headers (ENABLE_FORWARD_USER_INFO_HEADERS=true)
    headers = data.get("headers", {})
    if isinstance(headers, dict):
        # Check for OpenWebUI standard chat ID header (newest standard)
        chat_id = headers.get("x-openwebui-chat-id") or headers.get(
            "X-OpenWebUI-Chat-Id"
        )
        if chat_id and isinstance(chat_id, str) and len(chat_id) > 0:
            logger.debug(f"Using OpenWebUI standard chat ID: {chat_id}")
            return chat_id

        # Check for other OpenWebUI headers as fallback
        user_id = headers.get("x-openwebui-user-id") or headers.get(
            "X-OpenWebUI-User-Id"
        )
        if user_id and isinstance(user_id, str) and len(user_id) > 0:
            # If no chat_id but have user_id, create session-like ID
            # This is NOT ideal for multi-chat per user, but better than nothing
            logger.debug(f"Using OpenWebUI user ID as session fallback: {user_id}")
            return f"user_{user_id}_session"

    # Priority 2: Look for explicit session fields in data
    explicit_session_fields = ["session_id", "conversation_id", "chat_id"]
    for field in explicit_session_fields:
        session_value = data.get(field)
        if session_value and isinstance(session_value, str) and len(session_value) > 0:
            logger.debug(f"Using explicit session ID from {field}: {session_value}")
            return session_value

    # Priority 3: Generate unique session ID for new conversations
    # Each new conversation gets a unique ID - no cross-conversation contamination!
    unique_timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )  # microsecond precision
    session_id = f"generated_{unique_timestamp}"

    logger.debug(f"Generated unique session ID: {session_id}")
    logger.info(
        "No OpenWebUI chat_id found - recommend enabling ENABLE_FORWARD_USER_INFO_HEADERS=true"
    )
    return session_id


# ──────────────────────────────────────────────────────────────────────────────
# The main callback class
# ──────────────────────────────────────────────────────────────────────────────


class HARagHook(CustomLogger):
    """Async LiteLLM callback for Home‑Assistant RAG bridging."""

    def __init__(self):
        super().__init__()
        logger.info("HARagHook initialized successfully")

    # ────────────────────────────────
    # Pre‑call: inject entities
    # ────────────────────────────────

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,  # noqa: D401  (unused but required)
        cache: DualCache,  # noqa: D401  (unused but required)
        data: Dict[str, Any],
        call_type: Literal[
            "completion",
            "text_completion",
            "embeddings",
            "image_generation",
            "moderation",
            "audio_transcription",
            "pass_through_endpoint",
            "rerank",
            "mcp_call",
        ],
    ) -> Dict[str, Any]:
        """Inject formatted entity list into the system prompt before the LLM call."""
        logger.info(
            "HA RAG Hook async_pre_call_hook called with call_type: %s", call_type
        )

        messages: List[Dict[str, Any]] = data.get("messages", [])
        logger.info(f"RAG Hook: Received {len(messages)} messages")

        # DEBUG: Log data keys to understand what OpenWebUI sends
        logger.debug(f"RAG Hook: Data keys available: {list(data.keys())}")

        # DEBUG: Log potential session-related fields
        potential_session_fields = [
            "session_id",
            "conversation_id",
            "chat_id",
            "user_id",
            "headers",
            "metadata",
            "request_id",
            "openwebui_session",
        ]
        for field in potential_session_fields:
            if field in data:
                logger.debug(f"RAG Hook: Found {field}: {data[field]}")

        # Log all messages for debugging
        for i, msg in enumerate(messages):
            logger.info(
                f"RAG Hook: Message {i}: role={msg.get('role')}, content_preview={str(msg.get('content', ''))[:100]}..."
            )

        # Cache-friendly approach: extract LAST user question and conversation context
        user_question, conversation_context = _extract_user_question_and_context(
            messages
        )
        if not user_question:
            logger.info("RAG Hook: No user question extracted - EXITING")
            return data

        # Find the last user message to inject context into
        user_idx = None
        for idx in reversed(range(len(messages))):
            if messages[idx].get("role") == "user":
                user_idx = idx
                break

        if user_idx is None:
            logger.info("RAG Hook: No user message found - EXITING")
            return data

        logger.info(
            f"RAG Hook: Extracted LAST user question: '{user_question[:100]}...'"
        )
        logger.info(f"RAG Hook: Conversation has {len(conversation_context)} messages")

        logger.debug("Querying HA‑RAG bridge for relevant entities…")
        logger.debug("Using RAG_QUERY_ENDPOINT: %s", RAG_QUERY_ENDPOINT)
        formatted_content: str
        try:
            # Build conversation-aware payload for bridge
            bridge_payload = {
                "user_message": user_question,
                "conversation_history": (
                    conversation_context if conversation_context else None
                ),
            }

            # Generate stable session ID for conversation continuity
            stable_session_id = _extract_stable_session_id(data, messages)
            bridge_payload["session_id"] = stable_session_id

            # Keep conversation_id for backward compatibility (but now it's stable)
            bridge_payload["conversation_id"] = stable_session_id

            logger.debug(f"Using stable session/conversation ID: {stable_session_id}")

            async with httpx.AsyncClient(timeout=10) as client:
                logger.debug(
                    "Sending request to RAG_QUERY_ENDPOINT with payload: %s",
                    {
                        **bridge_payload,
                        "conversation_history": (
                            f"[{len(conversation_context)} messages]"
                            if conversation_context
                            else None
                        ),
                    },
                )
                resp = await client.post(
                    RAG_QUERY_ENDPOINT,
                    json=bridge_payload,
                )
                resp.raise_for_status()
                logger.debug(
                    "Received response from RAG_QUERY_ENDPOINT: %s, %s",
                    resp.status_code,
                    resp.text,
                )
                rag_payload = resp.json()

            # Handle new bridge response format with messages array
            messages_from_bridge = rag_payload.get("messages", [])
            user_context = None
            
            # Look for user message with home context from Bridge
            for msg in messages_from_bridge:
                if msg.get("role") == "user" and "Current home context:" in msg.get("content", ""):
                    user_context = msg.get("content", "")
                    break
            
            if user_context:
                formatted_content = user_context
            else:
                # Fallback: try old format for backward compatibility
                formatted_content = rag_payload.get("formatted_content")
                if not formatted_content:
                    entities = rag_payload.get("relevant_entities", [])
                    if entities:
                        rows = [
                            f"{e['entity_id']},{e.get('name', e['entity_id'])},{e.get('state', 'unknown')},{'/'.join(e.get('aliases', []))}"
                            for e in entities
                        ]
                        formatted_content = (
                            "Available Devices (relevant to your query):\n"  # header
                            "```csv\nentity_id,name,state,aliases\n"
                            + "\n".join(rows)
                            + "\n```"
                        )
                    else:
                        formatted_content = "No relevant entities found for your query."
        except Exception as exc:  # noqa: BLE001
            logger.exception("HA‑RAG query failed: %s", exc)
            formatted_content = "Error retrieving Home Assistant entities."

        # Cache-friendly approach: inject conversation-aware context into user message
        original_user_content = messages[user_idx]["content"]

        # Build enhanced context with conversation awareness
        context_parts = []

        # Add current relevant entities (always with fresh values)
        if (
            formatted_content
            and formatted_content != "Error retrieving Home Assistant entities."
        ):
            context_parts.append(f"Aktuálisan releváns eszközök:\n{formatted_content}")

        # Add conversation context if available
        if len(conversation_context) > 1:  # More than just current message
            # Extract previously mentioned entities or areas
            prev_context = _extract_conversation_insights(conversation_context)
            if prev_context:
                context_parts.append(
                    f"A beszélgetés során korábban relevánsnak talált információk:\n{prev_context}"
                )

        # Combine all context parts
        if context_parts:
            combined_context = "\n\n".join(context_parts)
            updated_user_content = (
                f"{combined_context}\n\nFelhasználói kérdés: {original_user_content}"
            )
        else:
            updated_user_content = original_user_content

        messages[user_idx]["content"] = updated_user_content
        data["messages"] = messages

        logger.info(
            f"RAG Hook: Successfully injected conversation-aware context. Total length: {len(updated_user_content)}"
        )
        logger.debug(
            f"RAG Hook: Enhanced context preview: {updated_user_content[:300]}..."
        )
        logger.info(
            f"RAG Hook: Updated user message length: {len(updated_user_content)}"
        )

        return data

    # ────────────────────────────────
    # Post‑call: execute HA tools
    # ────────────────────────────────

    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict: UserAPIKeyAuth,  # noqa: D401 (unused)
        response: LLMResponseTypes,
    ) -> Any:
        """Execute Home‑Assistant tool calls after a successful LLM call."""
        logger.info("HA RAG Hook async_post_call_success_hook called")
        logger.debug(
            f"Post-call hook data keys: {list(data.keys()) if data else 'None'}"
        )
        logger.debug(f"Response type: {type(response).__name__}")

        # First: Execute HA tool calls if needed
        execution_mode: str = (
            data.get("tool_execution_mode") or TOOL_EXECUTION_MODE
        ).lower()

        # Continue with tool execution if enabled
        if execution_mode == "disabled":
            return response

        # Ensure there is at least one tool call
        choices = getattr(response, "choices", [])
        if not choices:
            return response

        tool_calls = (
            getattr(getattr(choices[0], "message", {}), "tool_calls", [])
            if choices
            else []
        )
        if not tool_calls:
            return response

        # Filter Home‑Assistant calls
        ha_calls: List[Dict[str, Any]] = []
        for call in tool_calls:
            func = call.get("function", {})
            name: str = func.get("name", "")
            if name.startswith("homeassistant.") or (
                "." in name
                and name.split(".", 1)[0]
                in {
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
                }
            ):
                ha_calls.append(call)

        if not ha_calls:
            return response  # nothing to execute

        if execution_mode == "caller":
            return response  # let the caller handle execution

        # ha‑rag‑bridge or both → execute via bridge
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                exec_resp = await client.post(
                    TOOL_EXECUTION_ENDPOINT,
                    json={"tool_calls": ha_calls},
                )
                exec_resp.raise_for_status()
                exec_payload = exec_resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool execution via HA‑RAG bridge failed: %s", exc)
            return response

        if execution_mode in {"ha-rag-bridge", "both"} and exec_payload.get(
            "tool_execution_results"
        ):
            # Add execution results to response (if response is mutable)
            if hasattr(response, "__dict__"):
                if not hasattr(response, "execution_results"):
                    response.execution_results = []
                response.execution_results.extend(
                    exec_payload["tool_execution_results"]
                )
        return response

    # ────────────────────────────────
    # Fallback: basic success logging
    # ────────────────────────────────

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        """Basic success logging fallback method."""
        logger.info("HA RAG Hook async_log_success_event called")


# Exported instance – reference this in litellm_config.yaml
ha_rag_hook_instance: HARagHook = HARagHook()
logger.info("HA RAG Hook instance created successfully: %s", ha_rag_hook_instance)
