"""Message parsing utilities for different chat interfaces"""

import re
import logging
from typing import List, Dict, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MessageParseResult:
    """Result of message parsing operation"""

    messages: List[Dict[str, str]]
    original_query: str
    is_meta_task: bool
    extraction_method: str
    success: bool
    error: Optional[str] = None


def parse_openwebui_query(raw_query: str) -> MessageParseResult:
    """
    Parse OpenWebUI query format, handling meta-tasks and direct queries

    OpenWebUI often sends meta-task prompts like:
    "### Task: Generate tags... ### Chat History: USER: actual question"

    We need to extract the actual conversation from this wrapper.
    """

    try:
        # Check if this is a meta-task prompt
        if "### Task:" in raw_query and "### Chat History:" in raw_query:
            return _parse_meta_task_format(raw_query)

        # Check for other chat history indicators
        elif "USER:" in raw_query or "ASSISTANT:" in raw_query:
            return _parse_simple_chat_format(raw_query)

        # Direct query without conversation structure
        else:
            return MessageParseResult(
                messages=[{"role": "user", "content": raw_query.strip()}],
                original_query=raw_query,
                is_meta_task=False,
                extraction_method="direct",
                success=True,
            )

    except Exception as e:
        logger.error(f"Failed to parse query: {e}", exc_info=True)

        # Fallback: treat as direct user message
        return MessageParseResult(
            messages=[{"role": "user", "content": raw_query.strip()}],
            original_query=raw_query,
            is_meta_task=False,
            extraction_method="fallback",
            success=False,
            error=str(e),
        )


def _parse_meta_task_format(raw_query: str) -> MessageParseResult:
    """Parse OpenWebUI meta-task format with embedded chat history"""

    # Extract the chat history section
    history_match = re.search(
        r"### Chat History:\s*<chat_history>(.*?)</chat_history>",
        raw_query,
        re.DOTALL | re.IGNORECASE,
    )

    if not history_match:
        # Try without XML tags
        history_parts = raw_query.split("### Chat History:")
        if len(history_parts) > 1:
            chat_content = history_parts[-1].strip()
        else:
            raise ValueError("No chat history found in meta-task format")
    else:
        chat_content = history_match.group(1).strip()

    # Parse the extracted chat content
    messages = _extract_chat_messages(chat_content)

    if not messages:
        raise ValueError("No valid messages found in chat history")

    return MessageParseResult(
        messages=messages,
        original_query=raw_query,
        is_meta_task=True,
        extraction_method="meta_task",
        success=True,
    )


def _parse_simple_chat_format(raw_query: str) -> MessageParseResult:
    """Parse simple chat format with USER:/ASSISTANT: prefixes"""

    messages = _extract_chat_messages(raw_query)

    if not messages:
        # Fallback to treating as single user message
        messages = [{"role": "user", "content": raw_query.strip()}]

    return MessageParseResult(
        messages=messages,
        original_query=raw_query,
        is_meta_task=False,
        extraction_method="simple_chat",
        success=True,
    )


def _extract_chat_messages(content: str) -> List[Dict[str, str]]:
    """Extract USER/ASSISTANT messages from chat content"""

    messages = []

    # Split by USER: or ASSISTANT: markers
    parts = re.split(r"(USER:|ASSISTANT:)", content, flags=re.IGNORECASE)

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

    return messages


def extract_messages(raw_input: Union[str, List[Dict]]) -> List[Dict[str, str]]:
    """
    High-level function to extract messages from various input formats

    Args:
        raw_input: Either a raw query string or already parsed message list

    Returns:
        Normalized list of messages
    """

    if isinstance(raw_input, list):
        # Already parsed messages
        return [normalize_message(msg) for msg in raw_input]

    elif isinstance(raw_input, str):
        # Parse the string
        result = parse_openwebui_query(raw_input)

        if not result.success:
            logger.warning(f"Message parsing failed: {result.error}")

        return result.messages

    else:
        logger.error(f"Unsupported input type: {type(raw_input)}")
        return []


def normalize_message(message: Dict) -> Dict[str, str]:
    """Normalize a message to standard format"""

    # Ensure required fields
    normalized = {
        "role": str(message.get("role", "user")).lower(),
        "content": str(message.get("content", "")).strip(),
    }

    # Validate role
    if normalized["role"] not in ["user", "assistant", "system"]:
        logger.warning(f"Unknown role: {normalized['role']}, defaulting to 'user'")
        normalized["role"] = "user"

    return normalized


def get_last_user_message(messages: List[Dict[str, str]]) -> Optional[str]:
    """Get the content of the last user message"""

    for msg in reversed(messages):
        if msg.get("role") == "user" and msg.get("content"):
            return msg["content"]

    return None


def count_messages_by_role(messages: List[Dict[str, str]]) -> Dict[str, int]:
    """Count messages by role"""

    counts = {"user": 0, "assistant": 0, "system": 0}

    for msg in messages:
        role = msg.get("role", "user")
        if role in counts:
            counts[role] += 1
        else:
            counts["user"] += 1  # Default unknown roles to user

    return counts


# Example usage and test cases
if __name__ == "__main__":

    # Test cases
    test_cases = [
        # Meta-task format
        """### Task: Generate 1-3 broad tags categorizing the main themes of the chat history, along with 1-3 more specific subtopic tags.
### Guidelines:
- Start with high-level domains
### Chat History:
<chat_history>
USER: Hány fok van a nappaliban?
ASSISTANT: A nappaliban 23 fok van.
USER: És kint?
</chat_history>""",
        # Simple chat format
        """USER: Hány fok van?
ASSISTANT: 23 fok van.
USER: Köszi""",
        # Direct query
        "Hány fok van a nappaliban?",
    ]

    for i, test in enumerate(test_cases):
        print(f"\n--- Test Case {i+1} ---")
        result = parse_openwebui_query(test)
        print(f"Success: {result.success}")
        print(f"Method: {result.extraction_method}")
        print(f"Is meta-task: {result.is_meta_task}")
        print(f"Messages: {len(result.messages)}")
        for msg in result.messages:
            print(f"  {msg['role']}: {msg['content'][:50]}...")
