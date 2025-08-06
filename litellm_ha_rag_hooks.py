"""LiteLLM Hook for Home Assistant RAG Bridge integration

This module provides LiteLLM callback hooks that
1. Inject relevant Home‑Assistant entities into the system prompt (pre‑call)
2. Optionally execute Home‑Assistant tool calls and attach their results (post‑call)

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


def _extract_user_question(messages: List[Dict[str, Any]]) -> str | None:
    """Extract the actual user question, ignoring OpenWebUI metadata tasks."""
    import re
    
    logger.debug(f"Extracting user question from {len(messages)} messages")
    
    # OpenWebUI metadata task patterns (exact matches from their templates)
    metadata_patterns = [
        r"### Task:",
        r"Generate a concise, 3-5 word title",
        r"Generate 1-3 broad tags categorizing",
        r"main themes of the chat history",
        r"### Guidelines:",
        r"### Output:",
        r"JSON format:",
    ]
    
    for i, msg in enumerate(messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            content = msg["content"]
            logger.debug(f"Processing message {i} (user): '{content[:100]}...'")
            
            # Check if this is an OpenWebUI metadata generation task
            is_metadata_task = any(re.search(pattern, content, re.IGNORECASE) for pattern in metadata_patterns)
            
            if is_metadata_task:
                logger.debug("Detected OpenWebUI metadata task")
                # Extract the actual user question from chat history
                chat_history_match = re.search(r'<chat_history>(.*?)</chat_history>', content, re.DOTALL)
                if chat_history_match:
                    chat_content = chat_history_match.group(1)
                    logger.debug(f"Found chat history: '{chat_content[:200]}...'")
                    # Find the last USER question (most recent)
                    user_questions = re.findall(r'USER:\s*(.+?)(?=\nASSISTANT:|$)', chat_content, re.DOTALL | re.MULTILINE)
                    if user_questions:
                        # Clean up the extracted question
                        question = user_questions[-1].strip()
                        logger.info(f"Extracted user question from metadata task: '{question}'")
                        return question
                
                # If no chat history found, skip this metadata task
                logger.debug("Skipping OpenWebUI metadata generation task - no chat history")
                continue
            
            # This is likely a direct user question
            logger.debug(f"Using direct user question: '{content[:50]}...'")
            return content
    
    logger.debug("No user question found in any message")
    return None


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
            "mcp_call"
        ],
    ) -> Dict[str, Any]:
        """Inject formatted entity list into the system prompt before the LLM call."""
        logger.info("HA RAG Hook async_pre_call_hook called with call_type: %s", call_type)

        messages: List[Dict[str, Any]] = data.get("messages", [])
        logger.info(f"RAG Hook: Received {len(messages)} messages")
        
        # Log all messages for debugging
        for i, msg in enumerate(messages):
            logger.info(f"RAG Hook: Message {i}: role={msg.get('role')}, content_preview={str(msg.get('content', ''))[:100]}...")
        
        sys_idx = _find_system_placeholder(messages)
        if sys_idx is None:
            logger.info("RAG Hook: No system message with placeholder found - EXITING")
            return data  # nothing to do

        logger.info(f"RAG Hook: Found system placeholder at index {sys_idx}")
        user_question = _extract_user_question(messages)
        if not user_question:
            logger.info("RAG Hook: No user question extracted - EXITING")
            return data
            
        logger.info(f"RAG Hook: Extracted user question: '{user_question}'")

        logger.debug("Querying HA‑RAG bridge for relevant entities…")
        logger.debug("Using RAG_QUERY_ENDPOINT: %s", RAG_QUERY_ENDPOINT)
        formatted_content: str
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                logger.debug(
                    "Sending request to RAG_QUERY_ENDPOINT with payload: %s",
                    {"user_message": user_question},
                )
                resp = await client.post(
                    RAG_QUERY_ENDPOINT,
                    json={"user_message": user_question},
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
            system_message = None
            for msg in messages_from_bridge:
                if msg.get("role") == "system":
                    system_message = msg.get("content", "")
                    break
            
            if system_message:
                formatted_content = system_message
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

        # Replace the placeholder in‑place
        original_content = messages[sys_idx]["content"]
        updated_content = original_content.replace(RAG_PLACEHOLDER, formatted_content)
        messages[sys_idx]["content"] = updated_content
        data["messages"] = messages
        
        logger.info(f"RAG Hook: Successfully injected entities. Content length: {len(formatted_content)}")
        logger.debug(f"RAG Hook: Formatted content: {formatted_content[:200]}...")
        logger.info(f"RAG Hook: Updated system message length: {len(updated_content)}")
        
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
        """Optionally execute Home‑Assistant tool calls after a successful LLM call."""
        logger.info("HA RAG Hook async_post_call_success_hook called")
        logger.debug(f"Post-call hook data keys: {list(data.keys()) if data else 'None'}")
        logger.debug(f"Response type: {type(response).__name__}")

        execution_mode: str = (
            data.get("tool_execution_mode") or TOOL_EXECUTION_MODE
        ).lower()
        if execution_mode == "disabled":
            return response

        # Ensure there is at least one tool call  
        choices = getattr(response, "choices", [])
        if not choices:
            return response

        tool_calls = getattr(getattr(choices[0], "message", {}), "tool_calls", []) if choices else []
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
                response.execution_results.extend(exec_payload["tool_execution_results"])
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
