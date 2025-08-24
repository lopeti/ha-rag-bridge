"""Embedding utilities for conversation-aware RAG"""

import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.rag_strategies.base import StrategyConfig

logger = logging.getLogger(__name__)


def calculate_message_weights(
    messages: List[Dict[str, str]], config: Optional["StrategyConfig"] = None
) -> List[float]:
    """
    Calculate weights for messages based on role and recency

    Args:
        messages: List of conversation messages
        config: Strategy configuration with weight settings

    Returns:
        List of weights corresponding to each message
    """

    if not messages:
        return []

    # Default weights if no config provided
    user_weight = config.user_weight if config else 1.0
    assistant_weight = config.assistant_weight if config else 0.5
    recency_boost = config.recency_boost if config else 0.3

    weights = []

    for i, message in enumerate(messages):
        # Base weight by role
        if message.get("role") == "user":
            base_weight = user_weight
        elif message.get("role") == "assistant":
            base_weight = assistant_weight
        else:
            base_weight = 0.3  # System messages get low weight

        # Recency boost (more recent = higher weight)
        # Use position from the end, so last message gets highest boost
        recency_factor = 1.0 + (i * recency_boost)

        final_weight = base_weight * recency_factor
        weights.append(final_weight)

    return weights


def combine_messages_for_embedding(
    messages: List[Dict[str, str]],
    weights: Optional[List[float]] = None,
    separator: str = " [SEP] ",
) -> str:
    """
    Combine multiple messages into a single text for embedding

    Args:
        messages: List of conversation messages
        weights: Optional weights for each message (for repetition-based weighting)
        separator: Text separator between messages

    Returns:
        Combined text suitable for embedding
    """

    if not messages:
        return ""

    combined_parts = []

    for i, message in enumerate(messages):
        content = message.get("content", "").strip()

        if not content:
            continue

        # Apply weight by repeating content (simple but effective)
        if weights and i < len(weights):
            weight = weights[i]
            # Convert weight to repetition count (1.0 = 1 time, 2.0 = 2 times, etc.)
            repetitions = max(1, int(round(weight)))
            weighted_content = " ".join([content] * repetitions)
        else:
            weighted_content = content

        combined_parts.append(weighted_content)

    return separator.join(combined_parts)


def create_weighted_embedding(
    messages: List[Dict[str, str]],
    embedding_func,
    config: Optional["StrategyConfig"] = None,
) -> List[float]:
    """
    Create a single embedding from multiple weighted messages

    Args:
        messages: List of conversation messages
        embedding_func: Function to generate embeddings (e.g., backend.embed)
        config: Strategy configuration

    Returns:
        Single embedding vector representing the entire conversation
    """

    if not messages:
        logger.warning("No messages provided for embedding")
        return []

    try:
        # Limit number of messages to process
        max_messages = config.max_messages if config else 5
        recent_messages = messages[-max_messages:]

        # Calculate weights
        weights = calculate_message_weights(recent_messages, config)

        # Combine messages with weights
        combined_text = combine_messages_for_embedding(recent_messages, weights)

        if not combined_text.strip():
            logger.warning("Combined text is empty after processing")
            return []

        # Generate embedding
        embeddings = embedding_func([combined_text])

        if not embeddings or len(embeddings) == 0:
            logger.error("Embedding function returned empty result")
            return []

        return embeddings[0]

    except Exception as e:
        logger.error(f"Failed to create weighted embedding: {e}", exc_info=True)
        return []


def extract_key_phrases(text: str, max_length: int = 100) -> str:
    """
    Extract key phrases from assistant messages to reduce noise

    This is a simple heuristic approach. For production, consider
    using NLP libraries for proper keyword extraction.

    Args:
        text: Input text (typically assistant message)
        max_length: Maximum length of extracted phrases

    Returns:
        Extracted key phrases
    """

    if not text:
        return ""

    # Simple approach: look for entity mentions and temperature-related terms
    import re

    # Common Home Assistant entity patterns
    entity_patterns = [
        r"sensor\.\w+",
        r"climate\.\w+",
        r"light\.\w+",
        r"switch\.\w+",
    ]

    # Temperature/climate related terms
    climate_terms = [
        r"\d+\s*fok",
        r"\d+\s*°[CF]",
        r"hőmérséklet\w*",
        r"temperature",
        r"klíma\w*",
        r"climate",
        r"meleg",
        r"hideg",
        r"warm",
        r"cold",
    ]

    # Location/area terms
    location_terms = [
        r"nappali\w*",
        r"konyha\w*",
        r"hálószoba\w*",
        r"fürdő\w*",
        r"kert\w*",
        r"living\s*room",
        r"kitchen",
        r"bedroom",
        r"bathroom",
        r"garden",
    ]

    key_phrases = []
    text_lower = text.lower()

    # Extract matches for each pattern group
    all_patterns = entity_patterns + climate_terms + location_terms

    for pattern in all_patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        key_phrases.extend(matches)

    # Join and limit length
    result = " ".join(key_phrases)

    if len(result) > max_length:
        result = result[:max_length].rsplit(" ", 1)[0]  # Cut at word boundary

    return result if result else text[:max_length]


def analyze_conversation_context(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Analyze conversation for context clues

    Returns insights that might be useful for entity search:
    - Dominant topics
    - Mentioned areas/domains
    - Question patterns
    """

    if not messages:
        return {}

    context = {
        "message_count": len(messages),
        "user_messages": 0,
        "assistant_messages": 0,
        "topics": set(),
        "areas_mentioned": set(),
        "domains_mentioned": set(),
        "has_temperature_query": False,
        "has_control_request": False,
    }

    # Analyze each message
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "").lower()

        if role == "user":
            context["user_messages"] += 1
        elif role == "assistant":
            context["assistant_messages"] += 1

        # Look for temperature-related content
        if any(
            term in content
            for term in ["fok", "hőmérséklet", "temperature", "meleg", "hideg"]
        ):
            context["has_temperature_query"] = True
            context["topics"].add("temperature")

        # Look for control requests
        if any(
            term in content
            for term in ["kapcsold", "indítsd", "turn on", "turn off", "switch"]
        ):
            context["has_control_request"] = True
            context["topics"].add("control")

        # Extract area mentions (basic Hungarian/English)
        areas = [
            "nappali",
            "konyha",
            "hálószoba",
            "fürdő",
            "kert",
            "living room",
            "kitchen",
            "bedroom",
            "bathroom",
            "garden",
        ]
        for area in areas:
            if area in content:
                context["areas_mentioned"].add(area)

        # Extract domain mentions
        domains = ["sensor", "light", "climate", "switch", "cover"]
        for domain in domains:
            if domain in content:
                context["domains_mentioned"].add(domain)

    # Convert sets to lists for JSON serialization
    context["topics"] = list(context["topics"])
    context["areas_mentioned"] = list(context["areas_mentioned"])
    context["domains_mentioned"] = list(context["domains_mentioned"])

    return context
