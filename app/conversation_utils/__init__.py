"""Conversation utilities for RAG strategies

This module provides utilities for parsing and processing conversation data,
particularly from OpenWebUI and other chat interfaces.
"""

from .message_parser import (
    parse_openwebui_query,
    extract_messages,
    normalize_message,
    MessageParseResult,
)
from .embedding_utils import (
    create_weighted_embedding,
    calculate_message_weights,
    combine_messages_for_embedding,
    analyze_conversation_context,
)

__all__ = [
    "parse_openwebui_query",
    "extract_messages",
    "normalize_message",
    "MessageParseResult",
    "create_weighted_embedding",
    "calculate_message_weights",
    "combine_messages_for_embedding",
    "analyze_conversation_context",
]
