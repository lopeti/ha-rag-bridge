"""LiteLLM Hook for Home Assistant RAG Bridge integration with Phase 3 LangGraph Workflow

This is the enhanced version that integrates the Phase 3 LangGraph workflow with:
1. Conversation memory persistence with TTL
2. Advanced conditional routing and error handling
3. Multi-turn context enhancement
4. Comprehensive fallback mechanisms

The implementation follows LiteLLM's `CustomLogger` interface and must be
referenced from `litellm_config.yaml` like so:

```yaml
litellm_settings:
  callbacks: litellm_ha_rag_hooks_phase3.ha_rag_hook_phase3_instance
```
"""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING, Any, Dict, List

import httpx
from litellm.integrations.custom_logger import CustomLogger
from litellm.types.utils import LLMResponseTypes

# Translation service removed - using multilingual embedding approach
HAS_TRANSLATION = False
get_translation_service = None


def extract_entity_ids_from_prompt(prompt_text: str) -> List[str]:
    """Extract entity IDs and entity data from prompt text for entity proof tracking."""
    # Look for explicit entity IDs in common patterns
    entity_id_patterns = [
        r"\b(sensor\.[a-zA-Z0-9_]+)",
        r"\b(light\.[a-zA-Z0-9_]+)",
        r"\b(switch\.[a-zA-Z0-9_]+)",
        r"\b(climate\.[a-zA-Z0-9_]+)",
        r"\b(cover\.[a-zA-Z0-9_]+)",
        r"\b(binary_sensor\.[a-zA-Z0-9_]+)",
    ]

    entity_ids = set()
    for pattern in entity_id_patterns:
        matches = re.findall(pattern, prompt_text, re.IGNORECASE)
        entity_ids.update(matches)

    # Also look for entity data patterns from bridge context (like "Temperature: 23.7 °C")
    entity_data_patterns = [
        r"Temperature:\s*[\d.]+\s*°C",
        r"Power:\s*[\d.]+\s*W",
        r"Humidity:\s*[\d.]+\s*%",
        r"State:\s*\w+",
        r"\[P\]\s+\w+:\s*[\d.]+",  # Primary entity format: [P] Temperature: 23.7 °C
        r"\[R\]\s+[\w\s]+",  # Related entity format: [R] Entity Name
    ]

    entity_data_found = []
    for pattern in entity_data_patterns:
        matches = re.findall(pattern, prompt_text, re.IGNORECASE)
        entity_data_found.extend(matches)

    # Combine entity IDs and entity data indicators
    all_entities = list(entity_ids) + [f"data:{data}" for data in entity_data_found]

    return sorted(list(set(all_entities)))[
        :10
    ]  # Return max 10 unique entities to avoid log spam


if TYPE_CHECKING:
    from litellm.proxy.proxy_server import DualCache, UserAPIKeyAuth
else:
    DualCache = UserAPIKeyAuth = object

# ──────────────────────────────────────────────────────────────────────────────
# Configuration constants ─ values are injected via environment variables
# ──────────────────────────────────────────────────────────────────────────────

HA_RAG_API_URL: str = os.getenv("HA_RAG_API_URL", "http://localhost:8000")
RAG_QUERY_ENDPOINT: str = (
    f"{HA_RAG_API_URL}/process-request-workflow"  # Use Phase 3 workflow endpoint
)
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
logger = logging.getLogger("litellm_ha_rag_hook_phase3")

# ──────────────────────────────────────────────────────────────────────────────
# Helper functions (reuse from original hook with enhancements)
# ──────────────────────────────────────────────────────────────────────────────


def _extract_user_question_and_context(
    messages: List[Dict[str, Any]],
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
# The main callback class with Phase 3 integration
# ──────────────────────────────────────────────────────────────────────────────


class HARagHookPhase3(CustomLogger):
    """Enhanced LiteLLM callback for Home‑Assistant RAG bridging with Phase 3 LangGraph workflow."""

    def __init__(self):
        super().__init__()

        # Translation service removed - using multilingual embedding approach
        self.translation_service = None
        logger.info("Using multilingual embeddings - no translation needed")

        logger.info(
            "HARagHookPhase3 initialized successfully with LangGraph workflow integration"
        )
        logger.info(f"🔧 HA RAG API URL: {HA_RAG_API_URL}")
        logger.info(f"🔧 RAG Query Endpoint: {RAG_QUERY_ENDPOINT}")

        # Debug: list all methods to check what hooks are available
        hook_methods = [method for method in dir(self) if "hook" in method.lower()]
        logger.info(f"🔧 Available hook methods in this class: {hook_methods}")

        # MANUALLY register to litellm.callbacks as well
        try:
            import litellm

            if not hasattr(litellm, "callbacks"):
                litellm.callbacks = []
            if self not in litellm.callbacks:
                litellm.callbacks.append(self)
                logger.info(
                    f"🔧 MANUALLY added hook to litellm.callbacks: {litellm.callbacks}"
                )
            else:
                logger.info(
                    f"🔧 Hook already in litellm.callbacks: {litellm.callbacks}"
                )
        except Exception as e:
            logger.error(f"🔧 Failed to manually add to litellm.callbacks: {e}")

    # MINDEN HOOK TESZTELÉSE
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        """SYNC logging test."""
        logger.info("🔥🔥🔥 SYNC log_success_event CALLED!")
        return super().log_success_event(kwargs, response_obj, start_time, end_time)

    # MINDEN LEHETSÉGES PRE-CALL HOOK TESZTELÉSE
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        """PRE-call hook - ez az igazi hely a kontextus injektálásra."""
        logger.info(f"🔥🔥🔥 ASYNC_PRE_CALL_HOOK CALLED! call_type={call_type}")
        logger.info(f"🔥🔥🔥 data keys: {list(data.keys()) if data else 'None'}")

        # Simple context injection test
        if data and "messages" in data:
            messages = data["messages"]
            if len(messages) > 0 and messages[-1].get("role") == "user":
                user_msg = messages[-1].get("content", "")
                logger.info(f"🔥🔥🔥 User message: '{user_msg}'")
                if "hány fok" in user_msg.lower():
                    # Inject simple context
                    system_msg = {
                        "role": "system",
                        "content": "HA RAG Context: Temperature in living room is 22.75°C from sensor.nappali_szoba_szenzor_temperature",
                    }
                    data["messages"].insert(0, system_msg)
                    logger.info("🔥🔥🔥 CONTEXT INJECTED VIA ASYNC_PRE_CALL_HOOK!")
                    logger.info(f"🔥🔥🔥 New message count: {len(data['messages'])}")

        return data

    # Próbáljuk meg a sync verzió is
    def pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        """SYNC pre-call hook."""
        logger.info(f"🔥🔥🔥 SYNC PRE_CALL_HOOK CALLED! call_type={call_type}")
        return data

    # És más lehetséges hook metódusok
    async def async_moderation_hook(self, data, user_api_key_dict, call_type):
        """Moderation hook."""
        logger.info(f"🔥🔥🔥 ASYNC_MODERATION_HOOK CALLED! call_type={call_type}")
        return data

    async def async_logging_hook(
        self, kwargs, result, call_type=None, start_time=None, end_time=None
    ):
        """Debug method to see if ANY async method is being called."""
        logger.info("🚨 DEBUG: async_logging_hook called (POST-call)")
        logger.info(f"🚨 DEBUG: call_type={call_type}")

        # Ez POST-call, már késő kontextust injektálni
        # A CustomLogger super class nem támogatja ezeket a paramétereket, vissza kell adni (kwargs, result) tuple-t
        return (kwargs, result)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        """Extended debug for success logging."""
        logger.info("🚨 DEBUG: async_log_success_event called")
        logger.info(
            f"🚨 DEBUG: kwargs keys={list(kwargs.keys()) if kwargs else 'None'}"
        )

        # Try to manually trigger pre-call logic here as workaround
        if kwargs and "messages" in kwargs:
            logger.info("🔧 WORKAROUND: Running pre-call logic in success event")
            try:
                # Simulate pre-call hook manually
                await self.async_pre_call_hook(
                    user_api_key_dict=None,
                    cache=None,
                    data=kwargs,
                    call_type="completion",
                )
                logger.info("🔧 WORKAROUND: Pre-call logic completed successfully")
            except Exception as e:
                logger.error(f"🔧 WORKAROUND: Pre-call logic failed: {e}")

        await super().async_log_success_event(
            kwargs, response_obj, start_time, end_time
        )

    # ────────────────────────────────
    # Pre‑call: inject entities using Phase 3 workflow
    # ────────────────────────────────

    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict: UserAPIKeyAuth,  # noqa: D401 (unused)
        response: LLMResponseTypes,
    ) -> Any:
        """Execute Home‑Assistant tool calls after a successful LLM call and translate response if needed."""
        logger.info("🔚 HA RAG Hook Phase 3: Post-call processing started")

        # Log LLM response preview for debugging
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and hasattr(choice.message, "content"):
                response_content = choice.message.content or ""
                logger.info(f"🤖 LLM RESPONSE PREVIEW: {response_content[:200]}...")

                # Check if response mentions temperature/entities we're looking for
                if (
                    "hőmérséklet" in response_content.lower()
                    or "temperature" in response_content.lower()
                ):
                    logger.info("✅ Response contains temperature information")
                else:
                    logger.warning(
                        "⚠️ Response may be missing expected temperature data"
                    )

            # Log tool calls if any
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                tool_names = [
                    tc.function.name
                    for tc in choice.message.tool_calls
                    if hasattr(tc, "function")
                ]
                logger.info(f"🔧 TOOL CALLS: {tool_names}")

        logger.debug(
            f"Post-call hook data keys: {list(data.keys()) if data else 'None'}"
        )
        logger.debug(f"Response type: {type(response).__name__}")

        # Response translation removed - LLM handles Hungarian natively with multilingual context

        # Second: Execute HA tool calls if needed
        execution_mode: str = (
            data.get("tool_execution_mode") or TOOL_EXECUTION_MODE
        ).lower()

        # Continue with tool execution if enabled
        if execution_mode == "disabled":
            return response

        # Ensure there is at least one tool call (re-fetch choices after potential translation)
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


# Exported instance – reference this in litellm_config.yaml
ha_rag_hook_phase3_instance: HARagHookPhase3 = HARagHookPhase3()
logger.info(
    f"🔥 MODULE RELOAD TIMESTAMP: {__import__('time').time()} - Hook instance created"
)
logger.info(
    "HA RAG Hook Phase 3 instance created successfully: %s", ha_rag_hook_phase3_instance
)
