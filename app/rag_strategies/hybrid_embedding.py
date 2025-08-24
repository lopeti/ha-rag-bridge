"""Hybrid embedding strategy for conversation-aware RAG

This strategy combines multiple conversation messages into a single weighted 
embedding for efficient entity search while maintaining conversation context.
"""

import logging
from typing import List, Dict, Any
import os

from . import register_strategy, StrategyConfig
from ..conversation_utils import create_weighted_embedding, analyze_conversation_context

logger = logging.getLogger(__name__)


@register_strategy("hybrid")
async def hybrid_embedding_strategy(
    messages: List[Dict[str, str]], config: StrategyConfig
) -> List[Dict[str, Any]]:
    """
    Hybrid embedding strategy implementation

    Process:
    1. Analyze conversation context
    2. Create weighted embedding from all messages
    3. Perform single vector search
    4. Apply context-based boosting
    5. Return ranked entities

    This approach is efficient (single search) while being context-aware.
    """

    if not messages:
        logger.warning("No messages provided to hybrid strategy")
        return []

    # DEBUG: Log what messages we received
    logger.info(f"HYBRID STRATEGY DEBUG: Received {len(messages)} messages")
    for i, msg in enumerate(messages):
        content_preview = (
            msg.get("content", "")[:200] + "..."
            if len(msg.get("content", "")) > 200
            else msg.get("content", "")
        )
        logger.info(
            f"HYBRID STRATEGY DEBUG: Message {i+1}: {msg.get('role')} - {content_preview}"
        )

    # DEBUG: Check if this looks like a meta-task that needs extraction
    if len(messages) == 1 and messages[0].get("role") == "user":
        content = messages[0].get("content", "")
        if "### Task:" in content and "### Chat History:" in content:
            logger.warning(
                "HYBRID STRATEGY DEBUG: DETECTED UNEXTRACTED META-TASK! This should have been extracted!"
            )
        elif "Generate" in content and "tags" in content:
            logger.warning(
                "HYBRID STRATEGY DEBUG: POSSIBLE UNEXTRACTED META-TASK detected!"
            )

    try:
        # Step 1: Initialize database and embedding backend
        from arango import ArangoClient
        from app.services.integrations.embeddings import get_backend

        # Database connection
        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db_name = os.getenv("ARANGO_DB", "_system")
        db = arango.db(
            db_name,
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        # Embedding backend
        backend_name = os.getenv("EMBEDDING_BACKEND", "local").lower()
        embedding_backend = get_backend(backend_name)

        # Step 2: Analyze conversation context
        context_info = analyze_conversation_context(messages)
        logger.debug(f"Conversation context: {context_info}")

        # Step 3: Create weighted embedding from messages
        combined_embedding = create_weighted_embedding(
            messages, embedding_backend.embed, config
        )

        if not combined_embedding:
            logger.error("Failed to create embedding")
            return []

        # Step 4: Perform vector search
        entities = await _vector_search_with_hybrid_query(
            db,
            combined_embedding,
            messages,
            k=config.max_messages * 10,  # Get more candidates for better filtering
        )

        # Step 5: Apply conversation context boosting
        boosted_entities = _apply_conversation_boosting(
            entities, context_info, messages
        )

        # Step 6: Final ranking and filtering
        final_entities = _final_ranking_and_filtering(boosted_entities, config)

        logger.info(
            f"Hybrid strategy: {len(messages)} messages -> "
            f"{len(entities)} candidates -> {len(final_entities)} final entities"
        )

        return final_entities

    except Exception as e:
        logger.error(f"Hybrid embedding strategy failed: {e}", exc_info=True)
        return []


async def _vector_search_with_hybrid_query(
    db, query_vector: List[float], messages: List[Dict[str, str]], k: int = 30
) -> List[Dict[str, Any]]:
    """
    Perform vector search with hybrid text fallback

    This implements the improved hybrid search with proper text field usage.
    """

    # Combine recent messages for text search fallback
    recent_text = " ".join(
        [
            msg.get("content", "")
            for msg in messages[-3:]  # Last 3 messages
            if msg.get("content", "").strip()
        ]
    )

    # Hybrid search AQL with fixed text field (not text_system)
    aql = """
    LET knn = (
        FOR e IN entity 
        FILTER LENGTH(e.embedding) > 0 
        LET score = COSINE_SIMILARITY(e.embedding, @qv) 
        SORT score DESC 
        LIMIT @k 
        RETURN MERGE(e, {_score: score})
    ) 
    LET txt = (
        FOR e IN v_meta 
        SEARCH ANALYZER(PHRASE(e.text, @msg, 'text_en'), 'text_en') 
        SORT BM25(e) DESC 
        LIMIT @k 
        RETURN MERGE(e, {_score: BM25(e)})
    ) 
    FOR e IN UNIQUE(UNION(knn, txt)) 
    LIMIT @k 
    RETURN {
        entity_id: e.entity_id,
        area: e.area,
        area_name: e.area_name, 
        domain: e.domain,
        device_class: e.device_class,
        friendly_name: e.friendly_name,
        text: e.text,
        state: e.state,
        attributes: e.attributes,
        score: e._score
    }
    """

    cursor = db.aql.execute(
        aql, bind_vars={"qv": query_vector, "msg": recent_text, "k": k}
    )

    return list(cursor)


def _apply_conversation_boosting(
    entities: List[Dict[str, Any]],
    context_info: Dict[str, Any],
    messages: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """
    Apply context-based boosting to entities based on conversation analysis
    """

    boosted_entities = []

    for entity in entities:
        entity_copy = entity.copy()
        boost_factors = {}
        total_boost = 0

        # Area-based boosting
        entity_area = entity.get("area") or entity.get("area_name") or ""
        if entity_area and context_info.get("areas_mentioned"):
            for mentioned_area in context_info["areas_mentioned"]:
                if mentioned_area.lower() in entity_area.lower():
                    boost_factors["area_match"] = 0.3
                    total_boost += 0.3
                    break

        # Domain-based boosting
        entity_domain = entity.get("domain", "")
        if entity_domain in context_info.get("domains_mentioned", []):
            boost_factors["domain_match"] = 0.2
            total_boost += 0.2

        # Topic-based boosting
        topics = context_info.get("topics", [])
        entity_text = entity.get("text", "").lower()

        if "temperature" in topics:
            if any(term in entity_text for term in ["temperature", "hőmérséklet"]):
                boost_factors["temperature_topic"] = 0.4
                total_boost += 0.4

        if "control" in topics and entity_domain in [
            "light",
            "switch",
            "climate",
            "cover",
        ]:
            boost_factors["controllable_entity"] = 0.3
            total_boost += 0.3

        # Apply boosting to score
        original_score = entity.get("score", 0)
        boosted_score = original_score * (1.0 + total_boost)

        entity_copy["score"] = boosted_score
        entity_copy["_boost_factors"] = boost_factors
        entity_copy["_total_boost"] = total_boost

        boosted_entities.append(entity_copy)

    # Re-sort by boosted scores
    return sorted(boosted_entities, key=lambda x: x.get("score", 0), reverse=True)


def _final_ranking_and_filtering(
    entities: List[Dict[str, Any]], config: StrategyConfig
) -> List[Dict[str, Any]]:
    """
    Final ranking and filtering of entities
    """

    if not entities:
        return []

    # Apply minimum score threshold
    min_score = (
        0.1  # Lower threshold than single-query search due to message combination
    )
    filtered_entities = [
        entity for entity in entities if entity.get("score", 0) >= min_score
    ]

    # Limit to reasonable number
    max_entities = min(25, len(filtered_entities))  # Max 25 entities

    final_entities = filtered_entities[:max_entities]

    # Add strategy metadata
    for entity in final_entities:
        entity["_strategy"] = "hybrid"
        entity["_filtered_by_score"] = entity.get("score", 0) >= min_score

    return final_entities


# Fallback strategy for when hybrid fails
@register_strategy("legacy")
async def legacy_workflow_strategy(
    messages: List[Dict[str, str]], config: StrategyConfig
) -> List[Dict[str, Any]]:
    """
    Legacy strategy using the existing LangGraph workflow

    This takes only the first/last user message and processes it through
    the existing pipeline for backward compatibility.
    """

    if not messages:
        return []

    try:
        from app.langgraph_workflow.workflow import run_rag_workflow

        # Get the most recent user message
        user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user" and msg.get("content", "").strip():
                user_message = msg["content"]
                break

        if not user_message:
            logger.warning("No user message found for legacy strategy")
            return []

        # Run the existing workflow
        result = await run_rag_workflow(
            user_query=user_message,
            session_id=f"legacy_{hash(user_message) % 1000000}",
            conversation_history=[],  # Legacy doesn't use full conversation
        )

        # Extract entities from workflow result
        entities = result.get("retrieved_entities", [])

        # Add strategy metadata
        for entity in entities:
            entity["_strategy"] = "legacy"
            entity["_source"] = "langgraph_workflow"

        logger.info(f"Legacy strategy processed: {len(entities)} entities")
        return entities

    except Exception as e:
        logger.error(f"Legacy strategy failed: {e}", exc_info=True)
        return []
