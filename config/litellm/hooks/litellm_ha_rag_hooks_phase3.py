"""LiteLLM Hook for Home Assistant RAG Bridge integration - Enhanced Multi-Turn Version

This hook provides comprehensive multi-turn conversation support:
1. Detects OpenWebUI meta-tasks, direct messages, and conversation arrays
2. Integrates conversation memory for persistent entity context across turns
3. Always calls the bridge with appropriate conversation format
4. Has enhanced debugging and logging for troubleshooting
5. Maintains session continuity for optimal RAG performance
"""

from __future__ import annotations

import logging
import os
import re
import hashlib
import json
from typing import TYPE_CHECKING, List, Dict, Optional
from datetime import datetime

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
logger = logging.getLogger("litellm_ha_rag_hook_enhanced")


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


def extract_full_conversation_from_meta_task(user_msg: str) -> list[dict[str, str]]:
    """Extract the full conversation history from OpenWebUI meta-task format.

    Args:
        user_msg: The full meta-task message from OpenWebUI

    Returns:
        List of messages in format [{"role": "user", "content": "..."}, ...]
    """
    # Look for chat history section
    chat_history_match = re.search(
        r"<chat_history>(.*?)</chat_history>", user_msg, re.DOTALL
    )
    if not chat_history_match:
        logger.warning("No chat_history section found in meta-task")
        return []

    chat_content = chat_history_match.group(1).strip()
    logger.debug(f"Extracting full conversation from: {chat_content[:200]}...")

    messages = []

    # Split by USER: or ASSISTANT: markers
    parts = re.split(r"(USER:|ASSISTANT:)", chat_content, flags=re.IGNORECASE)

    # Process parts in pairs (marker, content)
    current_role = None

    for part in parts:
        part = part.strip()

        if part.upper() == "USER:":
            current_role = "user"
        elif part.upper() == "ASSISTANT:":
            current_role = "assistant"
        elif current_role and part:
            # This is message content
            message_text = part.strip()

            # Clean up the message (remove extra whitespace, newlines)
            message_text = re.sub(r"\s+", " ", message_text).strip()

            if message_text:  # Only add non-empty messages
                messages.append({"role": current_role, "content": message_text})

    logger.info(f"✅ Extracted full conversation: {len(messages)} messages")
    for i, msg in enumerate(messages):
        logger.debug(f"  {i+1}. {msg['role']}: {msg['content'][:50]}...")

    return messages


def is_meta_task(user_msg: str) -> bool:
    """Check if this is an OpenWebUI meta-task (title/tag generation)."""
    return "### Task:" in user_msg and (
        "Generate" in user_msg or "categoriz" in user_msg
    )


def detect_message_format(
    messages: List[Dict], data: Dict
) -> tuple[str, List[Dict], Optional[str]]:
    """Detect the format of incoming messages from OpenWebUI.

    Returns:
        tuple of (format_type, processed_messages, session_id)
        - format_type: "meta_task", "direct_conversation", "single_message"
        - processed_messages: List of messages ready for bridge
        - session_id: Extracted or generated session ID
    """

    if not messages:
        return "empty", [], None

    last_message = messages[-1]
    user_content = last_message.get("content", "")

    # Enhanced debugging - log the raw structure
    logger.info(f"🔍 ENHANCED DEBUG: Received {len(messages)} messages from OpenWebUI")
    logger.info(f"🔍 ENHANCED DEBUG: Data keys: {list(data.keys())}")

    # Log each message with detailed structure
    for i, msg in enumerate(messages):
        content_preview = str(msg.get("content", ""))[:100].replace("\n", "\\n")
        logger.info(
            f"🔍 ENHANCED DEBUG: Message {i+1}: role={msg.get('role')}, content_len={len(str(msg.get('content', '')))}, preview='{content_preview}'"
        )

    # Try to extract session info from various sources
    session_id = None

    # Check for session in data
    if "session_id" in data:
        session_id = data["session_id"]
    elif "conversation_id" in data:
        session_id = data["conversation_id"]
    elif "user_id" in data:
        session_id = f"user_{data['user_id']}"

    # Check if this is a meta-task
    if is_meta_task(user_content):
        logger.info("📋 ENHANCED DEBUG: Detected META-TASK format")
        conversation_messages = extract_full_conversation_from_meta_task(user_content)

        if conversation_messages:
            # Generate session ID from conversation content if not provided
            if not session_id:
                content_hash = hashlib.md5(
                    str(conversation_messages).encode()
                ).hexdigest()[:8]
                session_id = f"meta_{content_hash}"

            logger.info(
                f"📋 ENHANCED DEBUG: Extracted {len(conversation_messages)} messages from meta-task"
            )
            return "meta_task", conversation_messages, session_id
        else:
            logger.warning(
                "📋 ENHANCED DEBUG: Meta-task extraction failed - treating as single message"
            )
            if not session_id:
                session_id = (
                    f"single_{hashlib.md5(user_content.encode()).hexdigest()[:8]}"
                )
            return (
                "single_message",
                [{"role": "user", "content": user_content}],
                session_id,
            )

    # Check if we have multiple messages (direct conversation array)
    elif len(messages) > 1:
        logger.info(
            f"💬 ENHANCED DEBUG: Detected DIRECT CONVERSATION format with {len(messages)} messages"
        )

        # Generate session ID from message sequence if not provided
        if not session_id:
            msg_sequence = "|".join(
                [f"{m.get('role')}:{m.get('content', '')[:50]}" for m in messages[-5:]]
            )
            content_hash = hashlib.md5(msg_sequence.encode()).hexdigest()[:8]
            session_id = f"direct_{content_hash}"

        # Filter out system messages that aren't HA context
        filtered_messages = []
        for msg in messages:
            if msg.get("role") == "system" and (
                "Primary:" in str(msg.get("content", ""))
                or "Home Assistant" in str(msg.get("content", ""))
            ):
                # Skip existing HA context - we'll regenerate
                continue
            filtered_messages.append(msg)

        return "direct_conversation", filtered_messages, session_id

    # Single user message
    else:
        logger.info("📝 ENHANCED DEBUG: Detected SINGLE MESSAGE format")
        if not session_id:
            session_id = f"single_{hashlib.md5(user_content.encode()).hexdigest()[:8]}"

        return "single_message", [{"role": "user", "content": user_content}], session_id


def generate_persistent_session_id(messages: List[Dict], format_type: str) -> str:
    """Generate a persistent session ID that remains consistent for the same conversation.

    This ensures conversation memory persists across multiple turns.
    """

    # For direct conversations, use a consistent hash based on user messages
    if format_type == "direct_conversation" and len(messages) > 1:
        user_messages = [
            msg["content"] for msg in messages if msg.get("role") == "user"
        ]
        if len(user_messages) >= 2:
            # Use first and last user messages to create stable ID
            stable_content = f"{user_messages[0][:100]}|{user_messages[-1][:100]}"
            return f"conv_{hashlib.md5(stable_content.encode()).hexdigest()[:12]}"

    # For single messages, just use content hash
    if messages:
        content = messages[-1].get("content", "")
        return f"{format_type}_{hashlib.md5(content.encode()).hexdigest()[:8]}"

    # Fallback
    return f"{format_type}_{datetime.now().strftime('%H%M%S')}"


class HARagHookEnhanced(CustomLogger):
    """Enhanced multi-turn HA RAG hook."""

    def __init__(self):
        super().__init__()
        logger.info("🚀 HA RAG Hook (Enhanced Multi-Turn Version) initialized")

    def log_pre_api_call(self, model, messages, kwargs):
        """Pre-API call log hook - alternative hook method."""
        logger.info(f"🎯 LOG_PRE_API_CALL Hook activated with {len(messages)} messages")
        for i, msg in enumerate(messages):
            logger.info(
                f"  {i+1}. {msg.get('role', 'unknown')}: {msg.get('content', '')[:50]}..."
            )
        return {"model": model, "messages": messages, "kwargs": kwargs}

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        """Success log hook - another alternative."""
        logger.info("🎯 ASYNC_LOG_SUCCESS Hook activated")
        data = kwargs.get("data", kwargs)
        messages = data.get("messages", [])
        if messages:
            logger.info(f"📨 Success hook found {len(messages)} messages")
        return kwargs

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        """Primary pre-call hook method. Handles both meta-tasks and direct queries."""
        logger.info(f"🎯 PRE_CALL Hook activated for call_type={call_type}")
        return await self._process_request(data)

    async def async_logging_hook(self, kwargs, response_obj, start_time, end_time):
        """Logging hook - processes requests for context injection."""
        logger.info("🎯 LOGGING Hook activated")

        # Extract the original request data
        data = kwargs.get("data") or kwargs
        logger.info(f"🔍 Kwargs keys: {list(kwargs.keys())}")
        logger.info(
            f"🔍 Data type: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'Not dict'}"
        )

        # Try to find messages in various locations
        messages = None
        if isinstance(data, dict) and "messages" in data:
            messages = data["messages"]
        elif hasattr(kwargs, "messages"):
            messages = kwargs.messages
        elif "messages" in kwargs:
            messages = kwargs["messages"]

        if messages:
            logger.info(f"📨 Found {len(messages)} messages in logging hook")
            for i, msg in enumerate(messages):
                logger.info(
                    f"  {i+1}. {msg.get('role', 'unknown')}: {msg.get('content', '')[:50]}..."
                )
        else:
            logger.warning("❌ No messages found in logging hook")

        return kwargs

    async def _process_request(self, data):
        """Enhanced request processing with multi-turn conversation support."""
        logger.info(
            f"🔧 ENHANCED: Processing request with data keys: {list(data.keys())}"
        )

        if not data or "messages" not in data:
            logger.warning("🔧 ENHANCED: No messages in request data")
            return data

        messages = data.get("messages", [])
        if not messages:
            logger.warning("🔧 ENHANCED: Empty messages array")
            return data

        # Detect message format and get processed conversation
        format_type, conversation_to_send, session_id = detect_message_format(
            messages, data
        )

        logger.info(
            f"🔧 ENHANCED: Detected format: {format_type}, messages: {len(conversation_to_send)}, session: {session_id}"
        )

        if not conversation_to_send:
            logger.warning(
                f"🔧 ENHANCED: No valid messages extracted from {format_type} format"
            )
            return data

        # Generate a persistent session ID for conversation memory
        persistent_session_id = generate_persistent_session_id(
            conversation_to_send, format_type
        )
        logger.info(
            f"🔧 ENHANCED: Using persistent session ID: {persistent_session_id}"
        )

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
            logger.info("✋ ENHANCED: HA context already injected - skipping")
            return data

        # Get the last user query for logging
        last_query = "unknown"
        for msg in reversed(conversation_to_send):
            if msg.get("role") == "user":
                last_query = msg.get("content", "")[:100]
                break

        # Call the bridge with enhanced conversation processing
        try:
            logger.info(
                f"🌉 ENHANCED: Calling bridge - format: {format_type}, messages: {len(conversation_to_send)}, query: '{last_query}...'"
            )

            async with httpx.AsyncClient(timeout=20.0) as client:
                bridge_payload = {
                    "messages": conversation_to_send,
                    "session_id": persistent_session_id,
                    "strategy": "hybrid",  # Force hybrid for conversation processing
                    "format_info": {
                        "detected_format": format_type,
                        "original_message_count": len(messages),
                        "processed_message_count": len(conversation_to_send),
                        "is_multi_turn": len(
                            [m for m in conversation_to_send if m.get("role") == "user"]
                        )
                        > 1,
                    },
                }

                logger.debug(
                    f"🌉 ENHANCED: Bridge payload: {json.dumps(bridge_payload, indent=2)[:500]}..."
                )

                response = await client.post(
                    f"{HA_RAG_API_URL}/process-conversation", json=bridge_payload
                )

                if response.status_code == 200:
                    result = response.json()
                    formatted_context = result.get("formatted_content", "")

                    if formatted_context and formatted_context.strip():
                        # Inject HA context as system message
                        system_msg = {"role": "system", "content": formatted_context}
                        messages.insert(0, system_msg)

                        entities_count = len(result.get("entities", []))
                        strategy_used = result.get("strategy_used", "unknown")
                        message_count = result.get(
                            "message_count", len(conversation_to_send)
                        )

                        logger.info(
                            f"✅ ENHANCED: HA context injected via {strategy_used}: "
                            f"{len(formatted_context)} chars, {entities_count} entities, "
                            f"{message_count} messages processed ({format_type})"
                        )

                        # Log conversation continuity info
                        if message_count > 1:
                            logger.info(
                                f"🔄 ENHANCED: Multi-turn conversation detected with session {persistent_session_id}"
                            )
                    else:
                        logger.info(
                            f"ℹ️ ENHANCED: Bridge returned empty context for {format_type} with {len(conversation_to_send)} messages"
                        )
                else:
                    logger.error(
                        f"❌ ENHANCED: Bridge call failed: {response.status_code} - {response.text[:200]}"
                    )

        except Exception as e:
            logger.error(f"❌ ENHANCED: Hook processing error: {e}", exc_info=True)
            # Don't fail the request on hook errors

        return data


# Global instance for LiteLLM
ha_rag_hook_enhanced_instance = HARagHookEnhanced()

# Auto-register the hook if in LiteLLM environment
try:
    import litellm

    if ha_rag_hook_enhanced_instance not in litellm.callbacks:
        litellm.callbacks.append(ha_rag_hook_enhanced_instance)
        logger.info("✅ Auto-registered Enhanced HA RAG hook with LiteLLM")
except ImportError:
    logger.debug("LiteLLM not available - hook registration deferred")
except Exception as e:
    logger.error(f"Failed to auto-register enhanced hook: {e}")
