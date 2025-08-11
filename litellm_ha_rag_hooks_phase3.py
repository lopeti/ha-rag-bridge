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
from typing import Any, Dict, Literal, List

import httpx
from litellm.integrations.custom_logger import CustomLogger
from litellm.types.utils import LLMResponseTypes

# Translation service removed - using multilingual embedding approach
HAS_TRANSLATION = False
get_translation_service = None

def extract_entity_ids_from_prompt(prompt_text: str) -> List[str]:
    """Extract entity IDs and entity data from prompt text for entity proof tracking."""
    import re
    
    # Look for explicit entity IDs in common patterns
    entity_id_patterns = [
        r'\b(sensor\.[a-zA-Z0-9_]+)',
        r'\b(light\.[a-zA-Z0-9_]+)',
        r'\b(switch\.[a-zA-Z0-9_]+)', 
        r'\b(climate\.[a-zA-Z0-9_]+)',
        r'\b(cover\.[a-zA-Z0-9_]+)',
        r'\b(binary_sensor\.[a-zA-Z0-9_]+)',
    ]
    
    entity_ids = set()
    for pattern in entity_id_patterns:
        matches = re.findall(pattern, prompt_text, re.IGNORECASE)
        entity_ids.update(matches)
    
    # Also look for entity data patterns from bridge context (like "Temperature: 23.7 °C")
    entity_data_patterns = [
        r'Temperature:\s*[\d.]+\s*°C',
        r'Power:\s*[\d.]+\s*W',
        r'Humidity:\s*[\d.]+\s*%',
        r'State:\s*\w+',
        r'\[P\]\s+\w+:\s*[\d.]+',  # Primary entity format: [P] Temperature: 23.7 °C
        r'\[R\]\s+[\w\s]+',        # Related entity format: [R] Entity Name
    ]
    
    entity_data_found = []
    for pattern in entity_data_patterns:
        matches = re.findall(pattern, prompt_text, re.IGNORECASE)
        entity_data_found.extend(matches)
    
    # Combine entity IDs and entity data indicators
    all_entities = list(entity_ids) + [f"data:{data}" for data in entity_data_found]
    
    return sorted(list(set(all_entities)))[:10]  # Return max 10 unique entities to avoid log spam

# Simple type hints without importing proxy server
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from litellm.proxy.proxy_server import DualCache, UserAPIKeyAuth
else:
    DualCache = UserAPIKeyAuth = object

# ──────────────────────────────────────────────────────────────────────────────
# Configuration constants ─ values are injected via environment variables
# ──────────────────────────────────────────────────────────────────────────────

HA_RAG_API_URL: str = os.getenv("HA_RAG_API_URL", "http://localhost:8000")
RAG_QUERY_ENDPOINT: str = f"{HA_RAG_API_URL}/process-request-workflow"  # Use Phase 3 workflow endpoint
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
        
        # Debug: list all methods to check what hooks are available
        hook_methods = [method for method in dir(self) if 'hook' in method.lower()]
        logger.info(f"🔧 Available hook methods in this class: {hook_methods}")
        
    async def async_logging_hook(self, kwargs, result, start_time, end_time):
        """Debug method to see if ANY async method is being called."""
        logger.info("🚨 DEBUG: async_logging_hook called - our hook class is active")
        return await super().async_logging_hook(kwargs, result, start_time, end_time) if hasattr(super(), 'async_logging_hook') else None

    # ────────────────────────────────
    # Pre‑call: inject entities using Phase 3 workflow
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
        """Inject formatted entity list using Phase 3 LangGraph workflow."""
        logger.info(
            "HA RAG Hook Phase 3 async_pre_call_hook called with call_type: %s",
            call_type,
        )

        messages: List[Dict[str, Any]] = data.get("messages", [])
        logger.info(f"RAG Hook Phase 3: Received {len(messages)} messages")

        # DEBUG: Log data keys to understand what OpenWebUI sends
        logger.debug(f"RAG Hook Phase 3: Data keys available: {list(data.keys())}")

        # Log all messages for debugging
        for i, msg in enumerate(messages):
            logger.info(
                f"RAG Hook Phase 3: Message {i}: role={msg.get('role')}, content_preview={str(msg.get('content', ''))[:100]}..."
            )

        # Extract LAST user question and conversation context
        user_question, conversation_context = _extract_user_question_and_context(
            messages
        )
        if not user_question:
            logger.info("RAG Hook Phase 3: No user question extracted - EXITING")
            return data
            
        # Using multilingual embeddings - no translation needed
        # The RAG system now handles Hungarian queries natively via hybrid embeddings

        # Find the last user message to inject context into
        user_idx = None
        for idx in reversed(range(len(messages))):
            if messages[idx].get("role") == "user":
                user_idx = idx
                break

        if user_idx is None:
            logger.info("RAG Hook Phase 3: No user message found - EXITING")
            return data

        logger.info(
            f"RAG Hook Phase 3: Extracted LAST user question: '{user_question[:100]}...'"
        )
        logger.info(
            f"RAG Hook Phase 3: Conversation has {len(conversation_context)} messages"
        )

        logger.debug("Querying HA‑RAG bridge Phase 3 workflow for relevant entities…")
        logger.debug("Using Phase 3 workflow endpoint: %s", RAG_QUERY_ENDPOINT)

        formatted_context: str
        try:
            # Generate stable session ID for conversation continuity
            stable_session_id = _extract_stable_session_id(data, messages)

            logger.debug(
                f"Using stable session ID for Phase 3 workflow: {stable_session_id}"
            )

            # Build conversation-aware payload for Phase 3 workflow endpoint
            bridge_payload = {
                "user_message": user_question,  # Hungarian/English - handled by multilingual embeddings
                "conversation_history": (
                    [
                        {"role": msg["role"], "content": msg["content"]}
                        for msg in conversation_context
                    ]
                    if conversation_context
                    else None
                ),
                "session_id": stable_session_id,
            }
            
            # Translation metadata removed - no longer needed with multilingual embeddings

            # Call RAG bridge via HTTP endpoint
            async with httpx.AsyncClient(
                timeout=30
            ) as client:  # Increased timeout for complex workflow
                logger.info("Calling RAG bridge endpoint...")

                resp = await client.post(
                    RAG_QUERY_ENDPOINT,  # This is now /process-request
                    json=bridge_payload,
                )
                resp.raise_for_status()
                logger.debug(
                    "Received response from RAG bridge endpoint: %s, %s",
                    resp.status_code,
                    resp.text[:500],  # Truncate long responses
                )
                rag_payload = resp.json()

            # Handle Phase 3 workflow response format
            messages_from_bridge = rag_payload.get("messages", [])
            system_message = None
            for msg in messages_from_bridge:
                if msg.get("role") == "system":
                    system_message = msg.get("content", "")
                    break

            # DEBUG: Log what we actually got from bridge
            logger.debug(f"🔍 BRIDGE SYSTEM MESSAGE: {system_message[:200] if system_message else 'None'}...")

            if system_message:
                formatted_context = system_message
            else:
                # Fallback: try old format for backward compatibility
                formatted_context = rag_payload.get("formatted_content")
                if not formatted_context:
                    entities = rag_payload.get("relevant_entities", [])
                    if entities:
                        rows = [
                            f"{e['entity_id']},{e.get('name', e['entity_id'])},{e.get('state', 'unknown')},{'/'.join(e.get('aliases', []))}"
                            for e in entities
                        ]
                        formatted_context = (
                            "Available Devices (from Phase 3 workflow):\n"  # header
                            "```csv\nentity_id,name,state,aliases\n"
                            + "\n".join(rows)
                            + "\n```"
                        )
                    else:
                        formatted_context = (
                            "No relevant entities found from Phase 3 workflow."
                        )

            # Log Phase 3 workflow metrics
            # In Phase 3 format, entities are embedded in the system message, not as a separate list
            # Extract entity count from metadata or estimate from content length
            metadata = rag_payload.get("metadata") or {}
            entities_count = metadata.get("entity_count", "unknown") if metadata else "unknown"
            if entities_count == "unknown" and system_message:
                # Estimate entity count from system message content length
                # Typical entity context is ~100-200 chars per entity
                estimated_count = max(1, len(system_message) // 150) if len(system_message) > 500 else 0
                entities_count = f"~{estimated_count}"
            logger.info(f"Phase 3 workflow completed: {entities_count} entities retrieved")
            if metadata:
                logger.debug(f"Phase 3 metadata: {metadata}")

        except Exception as exc:  # noqa: BLE001
            logger.exception("HA‑RAG Phase 3 workflow failed: %s", exc)
            logger.error(f"Phase 3 workflow error details: {type(exc).__name__}: {str(exc)}")
            logger.error(f"RAG_QUERY_ENDPOINT: {RAG_QUERY_ENDPOINT}")
            logger.error(f"bridge_payload: {bridge_payload}")
            
            # Fallback to basic RAG endpoint
            logger.info("Falling back to basic RAG endpoint")
            try:
                fallback_endpoint = f"{HA_RAG_API_URL}/process-request"
                basic_payload = {
                    "user_message": user_question,
                    "conversation_history": (
                        [{"role": msg["role"], "content": msg["content"]}
                         for msg in conversation_context]
                        if conversation_context
                        else None
                    ),
                    "conversation_id": stable_session_id,
                }
                
                async with httpx.AsyncClient(timeout=15) as client:
                    logger.info("Calling basic RAG fallback endpoint...")
                    resp = await client.post(fallback_endpoint, json=basic_payload)
                    resp.raise_for_status()
                    basic_rag_payload = resp.json()
                    
                    logger.info(f"Basic RAG fallback successful: {len(basic_rag_payload.get('messages', []))} messages")
                    
                    # Extract system message from basic RAG response
                    messages_from_basic = basic_rag_payload.get("messages", [])
                    for msg in messages_from_basic:
                        if msg.get("role") == "system":
                            formatted_context = msg.get("content", "")
                            logger.info("Using system message from basic RAG fallback")
                            break
                    else:
                        formatted_context = "Basic RAG fallback: No system message found"
                        
            except Exception as fallback_exc:
                logger.error(f"Basic RAG fallback also failed: {fallback_exc}")
                formatted_context = (
                    "Error retrieving Home Assistant entities from both Phase 3 workflow and basic RAG fallback."
                )

        # Cache-friendly approach: inject conversation-aware context into user message
        original_user_content = messages[user_idx]["content"]

        # Build enhanced context with Phase 3 workflow results
        context_parts = []

        # Add Phase 3 workflow context - preserve original bridge formatting
        if (
            formatted_context
            and formatted_context
            != "Error retrieving Home Assistant entities from Phase 3 workflow."
        ):
            # Use the bridge context directly without wrapping it in generic text
            # This preserves the specific entity data like "Temperature: 23.7 °C"
            context_parts.append(formatted_context)

        # Add conversation continuity note if multi-turn
        if len(conversation_context) > 1:
            context_parts.append(
                "Multi-turn conversation - Phase 3 system automatically considers previous context and entity memory."
            )

        # Combine all context parts
        if context_parts:
            combined_context = "\n\n".join(context_parts)
            updated_user_content = (
                f"{combined_context}\n\nUser question: {original_user_content}"
            )
        else:
            updated_user_content = original_user_content

        messages[user_idx]["content"] = updated_user_content
        data["messages"] = messages

        # Entity Proof System: Log what entities are in the final prompt  
        entities_in_prompt = extract_entity_ids_from_prompt(updated_user_content)
        
        logger.info(
            f"🔄 RAG Hook Phase 3: Context injected ({len(updated_user_content)} chars, {len(entities_in_prompt)} entities)"
        )
        
        # System prompt preview for debugging
        system_msg_preview = formatted_context[:400] if formatted_context else "No system message"
        logger.info(f"📋 SYSTEM PROMPT PREVIEW: {system_msg_preview}...")
        
        # Entity proof tracking
        if entities_in_prompt:
            logger.info(f"🎯 ENTITIES IN PROMPT: {entities_in_prompt}")
        else:
            logger.warning("⚠️ No entities detected in final prompt - potential entity loss!")
        
        # User message for reference
        logger.debug(f"👤 USER MESSAGE: {user_question[:100]}...")

        return data

    # ────────────────────────────────
    # Post‑call: execute HA tools (reuse from original hook)
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
        if hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                response_content = choice.message.content or ""
                logger.info(f"🤖 LLM RESPONSE PREVIEW: {response_content[:200]}...")
                
                # Check if response mentions temperature/entities we're looking for
                if "hőmérséklet" in response_content.lower() or "temperature" in response_content.lower():
                    logger.info("✅ Response contains temperature information")
                else:
                    logger.warning("⚠️ Response may be missing expected temperature data")
            
            # Log tool calls if any
            if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                tool_names = [tc.function.name for tc in choice.message.tool_calls if hasattr(tc, 'function')]
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

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        """Basic success logging fallback method."""
        logger.info("HA RAG Hook Phase 3 async_log_success_event called")


# Exported instance – reference this in litellm_config.yaml
ha_rag_hook_phase3_instance: HARagHookPhase3 = HARagHookPhase3()
logger.info(f"🔥 MODULE RELOAD TIMESTAMP: {__import__('time').time()} - Hook instance created")
logger.info(
    "HA RAG Hook Phase 3 instance created successfully: %s", ha_rag_hook_phase3_instance
)
