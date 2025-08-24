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

        # Step 2.5: Integrate conversation memory for entity boosting
        memory_entities = []
        session_id = None
        
        # Try to get session_id from various sources (will be set by the hook)
        # This is a bit of a hack but necessary until we refactor the strategy signature
        try:
            import inspect
            frame = inspect.currentframe()
            while frame:
                if 'session_id' in frame.f_locals:
                    session_id = frame.f_locals['session_id']
                    break
                frame = frame.f_back
        except:
            pass
            
        if not session_id:
            # Generate fallback session ID
            import hashlib
            message_content = " ".join([msg.get("content", "") for msg in messages[-3:]])
            session_id = f"hybrid_{hashlib.md5(message_content.encode()).hexdigest()[:8]}"
            
        logger.debug(f"HYBRID STRATEGY: Using session_id: {session_id}")
        
        # Initialize conversation memory service
        from app.services.conversation.conversation_memory import ConversationMemoryService
        memory_service = ConversationMemoryService(ttl_minutes=15)
        
        try:
            # Get existing conversation memory
            existing_memory = await memory_service.get_conversation_memory(session_id)
            
            if existing_memory:
                logger.info(f"HYBRID STRATEGY: Found existing memory with {len(existing_memory.entities)} entities")
                # Convert memory entities to boost candidates
                for mem_entity in existing_memory.entities:
                    memory_entities.append({
                        "entity_id": mem_entity.entity_id,
                        "boost_weight": mem_entity.boost_weight,
                        "context": mem_entity.context,
                        "relevance_score": mem_entity.relevance_score
                    })
            else:
                logger.debug(f"HYBRID STRATEGY: No existing memory found for session {session_id}")
                
        except Exception as e:
            logger.warning(f"HYBRID STRATEGY: Failed to load conversation memory: {e}")

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

        # Step 5: Apply conversation context boosting (including memory)
        boosted_entities = _apply_conversation_boosting(
            entities, context_info, messages, memory_entities
        )
        
        # Step 5.5: Update conversation memory with new entities
        try:
            # Store top entities in conversation memory for next turn
            await _update_conversation_memory(
                memory_service, session_id, boosted_entities[:10], messages, context_info
            )
        except Exception as e:
            logger.warning(f"HYBRID STRATEGY: Failed to update conversation memory: {e}")

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
    memory_entities: List[Dict[str, Any]] = None,
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

        # Memory-based boosting (conversation continuity)
        if memory_entities:
            entity_id = entity.get("entity_id", "")
            for mem_entity in memory_entities:
                if mem_entity["entity_id"] == entity_id:
                    memory_boost = mem_entity.get("boost_weight", 1.0) - 1.0
                    boost_factors["conversation_memory"] = memory_boost
                    total_boost += memory_boost
                    logger.debug(f"Applied memory boost {memory_boost:.2f} to {entity_id}")
                    break

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


async def _update_conversation_memory(
    memory_service,
    session_id: str,
    entities: List[Dict[str, Any]],
    messages: List[Dict[str, str]],
    context_info: Dict[str, Any]
) -> None:
    """Update conversation memory with entities from current turn."""
    from app.services.conversation.conversation_memory import ConversationEntity
    from datetime import datetime
    
    try:
        # Create conversation entities from the top results
        memory_entities = []
        current_time = datetime.utcnow()
        
        for i, entity in enumerate(entities[:10]):  # Store top 10 entities
            # Calculate boost weight based on position and score
            base_boost = 1.2 - (i * 0.02)  # Decreasing boost: 1.2, 1.18, 1.16, etc.
            score_boost = min(0.3, entity.get("score", 0) * 0.5)  # Up to 0.3 boost from score
            final_boost = base_boost + score_boost
            
            # Determine context type based on score and position
            if i < 3 and entity.get("score", 0) > 0.7:
                context_type = "primary"
            elif i < 7:
                context_type = "secondary"  
            else:
                context_type = "historical"
            
            memory_entity = ConversationEntity(
                entity_id=entity.get("entity_id", ""),
                relevance_score=entity.get("score", 0),
                mentioned_at=current_time,
                context=f"Retrieved in turn with {len(messages)} messages",
                area=entity.get("area") or entity.get("area_name"),
                domain=entity.get("domain"),
                boost_weight=final_boost,
                context_type=context_type
            )
            memory_entities.append(memory_entity)
        
        # Store in conversation memory
        await memory_service.store_conversation_memory(
            conversation_id=session_id,
            entities=memory_entities,
            areas_mentioned=context_info.get("areas_mentioned", set()),
            domains_mentioned=context_info.get("domains", set()),
            ttl_minutes=15
        )
        
        logger.info(f"HYBRID STRATEGY: Updated memory for {session_id} with {len(memory_entities)} entities")
        
    except Exception as e:
        logger.error(f"HYBRID STRATEGY: Failed to update conversation memory: {e}", exc_info=True)


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
