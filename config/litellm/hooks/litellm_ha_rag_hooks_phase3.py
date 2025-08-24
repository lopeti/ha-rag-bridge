"""LiteLLM Hook for Home Assistant RAG Bridge integration - CLEAN VERSION

This is a simplified, single-responsibility hook that:
1. Detects OpenWebUI meta-tasks and extracts user queries
2. Always calls the bridge (no keyword filtering)
3. Uses only ONE hook method to avoid duplication
4. Has clear, debuggable flow
"""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

import httpx
from litellm.integrations.custom_logger import CustomLogger

if TYPE_CHECKING:
    from litellm.proxy.proxy_server import DualCache, UserAPIKeyAuth
else:
    DualCache = UserAPIKeyAuth = object

# Configuration
HA_RAG_API_URL: str = os.getenv("HA_RAG_API_URL", "http://bridge:8000")

# Logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("litellm_ha_rag_hook_clean")


def extract_user_query_from_meta_task(user_msg: str) -> str | None:
    """Extract the actual user query from OpenWebUI meta-task format.

    Args:
        user_msg: The full meta-task message from OpenWebUI

    Returns:
        The extracted user query, or None if extraction fails
    """
    # Look for chat history section
    chat_history_match = re.search(
        r"<chat_history>(.*?)</chat_history>", user_msg, re.DOTALL
    )
    if not chat_history_match:
        logger.warning("No chat_history section found in meta-task")
        return None

    chat_content = chat_history_match.group(1).strip()
    logger.debug(f"Found chat history content: {chat_content[:200]}...")

    # Extract the LAST user question (most recent)
    user_questions = re.findall(
        r"USER:\s*(.*?)(?=\nASSISTANT:|$)", chat_content, re.DOTALL
    )

    if user_questions:
        last_question = user_questions[-1].strip()
        logger.info(f"✅ Extracted user query: '{last_question}'")
        return last_question
    else:
        logger.warning("No USER questions found in chat history")
        return None


def is_meta_task(user_msg: str) -> bool:
    """Check if this is an OpenWebUI meta-task (title/tag generation)."""
    return "### Task:" in user_msg and (
        "Generate" in user_msg or "categoriz" in user_msg
    )


class HARagHookClean(CustomLogger):
    """Clean, single-responsibility HA RAG hook."""

    def __init__(self):
        super().__init__()
        logger.info("🚀 HA RAG Hook (Clean Version) initialized")

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        """The ONLY pre-call hook method. Handles both meta-tasks and direct queries."""
        logger.info(f"🎯 Hook activated for call_type={call_type}")

        if not data or "messages" not in data:
            return data

        messages = data.get("messages", [])
        if not messages or not messages[-1].get("role") == "user":
            return data

        user_msg = messages[-1].get("content", "")
        logger.info(f"📨 Processing message: '{user_msg[:50]}...'")

        # Determine what query to send to the bridge
        query_to_process = user_msg

        if is_meta_task(user_msg):
            logger.info("🔍 Meta-task detected - extracting user query")
            extracted_query = extract_user_query_from_meta_task(user_msg)

            if extracted_query:
                query_to_process = extracted_query
                logger.info(f"✅ Using extracted query: '{query_to_process}'")
            else:
                logger.warning(
                    "❌ Failed to extract query from meta-task - using full message"
                )
                # Continue with full message as fallback
        else:
            logger.info("💬 Direct user query - processing as-is")

        # Check if we already have HA context (prevent double injection)
        has_ha_context = any(
            msg.get("role") == "system"
            and (
                "Primary:" in str(msg.get("content", ""))
                or "Home Assistant" in str(msg.get("content", ""))
            )
            for msg in messages
        )

        if has_ha_context:
            logger.info("✋ HA context already injected - skipping")
            return data

        # ALWAYS call the bridge - let it decide if HA context is needed
        try:
            logger.info(f"🌉 Calling bridge with query: '{query_to_process[:100]}...'")

            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{HA_RAG_API_URL}/process-conversation",
                    json={
                        "user_message": query_to_process,
                        "conversation_history": [],
                        "session_id": f"hook_{hash(query_to_process) % 1000000}",
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    formatted_context = result.get("formatted_content", "")

                    if formatted_context and formatted_context.strip():
                        # Inject HA context as system message
                        system_msg = {"role": "system", "content": formatted_context}
                        messages.insert(0, system_msg)

                        entities_count = len(result.get("entities", []))
                        logger.info(
                            f"✅ HA context injected: {len(formatted_context)} chars, {entities_count} entities"
                        )
                    else:
                        logger.info(
                            "ℹ️ Bridge returned empty context - no HA entities relevant"
                        )
                else:
                    logger.error(f"❌ Bridge call failed: {response.status_code}")

        except Exception as e:
            logger.error(f"❌ Hook error: {e}")
            # Don't fail the request on hook errors

        return data


# Global instance for LiteLLM
ha_rag_hook_clean_instance = HARagHookClean()
