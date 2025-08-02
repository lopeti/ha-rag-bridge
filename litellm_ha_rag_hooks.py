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
from litellm.proxy.proxy_server import DualCache, UserAPIKeyAuth

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
    level=logging.INFO,
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
    """Return first user message content, else None."""
    for msg in messages:
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            return msg["content"]
    return None


# ──────────────────────────────────────────────────────────────────────────────
# The main callback class
# ──────────────────────────────────────────────────────────────────────────────


class HARagHook(CustomLogger):
    """Async LiteLLM callback for Home‑Assistant RAG bridging."""

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
        ],
    ) -> Dict[str, Any]:
        """Inject formatted entity list into the system prompt before the LLM call."""

        messages: List[Dict[str, Any]] = data.get("messages", [])
        sys_idx = _find_system_placeholder(messages)
        if sys_idx is None:
            return data  # nothing to do

        user_question = _extract_user_question(messages)
        if not user_question:
            return data

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
        messages[sys_idx]["content"] = messages[sys_idx]["content"].replace(
            RAG_PLACEHOLDER, formatted_content
        )
        data["messages"] = messages
        return data

    # ────────────────────────────────
    # Post‑call: execute HA tools
    # ────────────────────────────────

    async def async_post_call_success_hook(
        self,
        data: Dict[str, Any],
        user_api_key_dict: UserAPIKeyAuth,  # noqa: D401 (unused)
        response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Optionally execute Home‑Assistant tool calls after a successful LLM call."""

        execution_mode: str = (
            data.get("tool_execution_mode") or TOOL_EXECUTION_MODE
        ).lower()
        if execution_mode == "disabled":
            return response

        # Ensure there is at least one tool call
        choices = response.get("choices", [])
        if not choices:
            return response

        tool_calls = choices[0].get("message", {}).get("tool_calls", [])
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
            response.setdefault("execution_results", []).extend(
                exec_payload["tool_execution_results"]
            )
        return response


# Exported instance – reference this in litellm_config.yaml
ha_rag_hook_instance: HARagHook = HARagHook()
