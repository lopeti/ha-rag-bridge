"""Fallback and retry nodes for LangGraph workflow Phase 3."""

from typing import Dict, Any
from ha_rag_bridge.logging import get_logger
from app.services.conversation.conversation_memory import ConversationMemoryService

from .state import RAGState, QueryScope

logger = get_logger(__name__)


async def fallback_analysis_node(state: RAGState) -> Dict[str, Any]:
    """Fallback conversation analysis with minimal processing."""
    logger.warning("Using fallback conversation analysis")

    try:
        query_lower = state["user_query"].lower()

        # Simple pattern-based analysis
        simple_areas = []
        simple_domains = []

        # Basic area detection
        area_patterns = {
            "nappali": ["nappali", "living", "living room"],
            "konyha": ["konyha", "kitchen"],
            "hálószoba": ["hálószoba", "bedroom", "bedroom"],
            "fürdőszoba": ["fürdőszoba", "bathroom"],
            "kert": ["kert", "garden", "outside", "kültér"],
        }

        for area, patterns in area_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                simple_areas.append(area)

        # Basic domain detection
        domain_patterns = {
            "light": ["lámpa", "light", "világítás", "fény"],
            "sensor": ["hőmérséklet", "temperature", "páratartalom", "humidity", "fok"],
            "switch": ["kapcsoló", "switch", "kapcsol"],
            "climate": ["klíma", "climate", "fűtés", "heating"],
        }

        for domain, patterns in domain_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                simple_domains.append(domain)

        # Determine intent
        intent = "read"  # Safe default
        if any(
            word in query_lower for word in ["kapcsold", "turn", "állítsd", "indítsd"]
        ):
            intent = "control"

        return {
            "conversation_context": {
                "areas_mentioned": simple_areas,
                "domains_mentioned": simple_domains,
                "is_follow_up": False,  # Cannot detect follow-ups in fallback
                "intent": intent,
                "confidence": 0.4,  # Low confidence for fallback
            }
        }

    except Exception as e:
        logger.error(f"Fallback analysis failed: {e}")
        return {
            "conversation_context": {
                "areas_mentioned": [],
                "domains_mentioned": [],
                "is_follow_up": False,
                "intent": "read",
                "confidence": 0.1,
            },
            "errors": state.get("errors", []) + [f"Fallback analysis failed: {str(e)}"],
        }


async def retry_scope_detection_node(state: RAGState) -> Dict[str, Any]:
    """Retry scope detection with adjusted parameters."""
    logger.info(f"Retrying scope detection (attempt {state.get('retry_count', 0) + 1})")

    try:
        # Import the original scope detection function
        from .nodes import llm_scope_detection_node

        # Increment retry counter
        updated_state = state.copy()
        updated_state["retry_count"] = state.get("retry_count", 0) + 1

        # Clear previous scope detection errors
        errors = [
            e for e in state.get("errors", []) if "scope detection" not in e.lower()
        ]
        updated_state["errors"] = errors

        # Retry with the updated state
        result = await llm_scope_detection_node(updated_state)

        # Add retry information
        result["retry_count"] = updated_state["retry_count"]
        result["retried"] = True

        return result

    except Exception as e:
        logger.error(f"Scope detection retry failed: {e}")
        return await fallback_scope_detection_node(state)


async def fallback_scope_detection_node(state: RAGState) -> Dict[str, Any]:
    """Fallback scope detection using simple heuristics."""
    logger.warning("Using fallback scope detection")

    try:
        query_lower = state["user_query"].lower().strip()
        context = state.get("conversation_context", {})
        areas_mentioned = context.get("areas_mentioned", []) if context else []

        # Handle problematic queries
        if len(query_lower) == 0:
            scope = QueryScope.OVERVIEW
            optimal_k = 10
            confidence = 0.3
            reasoning = "Empty query - showing overview"
        elif (
            len(query_lower) < 3
            or query_lower.isdigit()
            or not any(c.isalpha() for c in query_lower)
        ):
            scope = QueryScope.MACRO
            optimal_k = 12
            confidence = 0.2
            reasoning = "Invalid/short query - conservative scope"
        elif any(
            word in query_lower
            for word in ["qwerty", "xyz", "12345", "test123", "asdf"]
        ):
            scope = QueryScope.MACRO
            optimal_k = 10
            confidence = 0.1
            reasoning = "Garbage query - minimal scope"
        # Normal query heuristics
        elif any(
            word in query_lower
            for word in ["kapcsold", "turn on", "turn off", "állítsd"]
        ):
            if any(word in query_lower for word in ["összes", "minden", "all"]):
                scope = QueryScope.MACRO
                optimal_k = 25
                confidence = 0.7
                reasoning = "Control action with quantity modifier"
            else:
                scope = QueryScope.MICRO
                optimal_k = 8
                confidence = 0.6
                reasoning = "Simple control action"
        elif len(areas_mentioned) > 1:
            scope = QueryScope.MACRO
            optimal_k = 20
            confidence = 0.6
            reasoning = "Multiple areas mentioned"
        elif any(
            word in query_lower
            for word in ["otthon", "house", "minden", "all", "összesítés"]
        ):
            scope = QueryScope.OVERVIEW
            optimal_k = 35
            confidence = 0.7
            reasoning = "House-wide query detected"
        elif areas_mentioned:
            scope = QueryScope.MACRO
            optimal_k = 18
            confidence = 0.6
            reasoning = "Single area mentioned"
        else:
            # Conservative fallback
            scope = QueryScope.MACRO
            optimal_k = 15
            confidence = 0.5
            reasoning = "Conservative fallback scope"

        logger.info(
            f"Fallback scope detection: {scope.value}, k={optimal_k}, confidence={confidence}"
        )

        return {
            "detected_scope": scope,
            "scope_confidence": confidence,
            "optimal_k": optimal_k,
            "scope_reasoning": f"Fallback: {reasoning}",
            "fallback_used": True,
        }

    except Exception as e:
        logger.error(f"Fallback scope detection failed: {e}")
        return {
            "detected_scope": QueryScope.MACRO,
            "scope_confidence": 0.3,
            "optimal_k": 15,
            "scope_reasoning": f"Error fallback: {str(e)}",
            "fallback_used": True,
            "errors": state.get("errors", [])
            + [f"Fallback scope detection failed: {str(e)}"],
        }


async def retry_entity_retrieval_node(state: RAGState) -> Dict[str, Any]:
    """Retry entity retrieval with different parameters."""
    retry_count = state.get("retry_count", 0) + 1
    logger.info(f"Retrying entity retrieval (attempt {retry_count})")

    try:
        # Import routing logic to get retry strategy
        from .routing import determine_retry_strategy
        from .nodes import entity_retrieval_node

        strategy = determine_retry_strategy(state)

        # Update state based on retry strategy
        updated_state = state.copy()
        updated_state["retry_count"] = retry_count

        if strategy["modify_k"] and strategy["new_k"]:
            updated_state["optimal_k"] = strategy["new_k"]
            logger.info(f"Retry with modified k={strategy['new_k']}")

        if strategy["modify_scope"] and strategy["new_scope"]:
            updated_state["detected_scope"] = strategy["new_scope"]
            logger.info(f"Retry with modified scope={strategy['new_scope'].value}")

        if strategy["use_fallback"]:
            return await fallback_entity_retrieval_node(updated_state)

        # Clear previous retrieval errors
        errors = [e for e in state.get("errors", []) if "retrieval" not in e.lower()]
        updated_state["errors"] = errors

        # Retry entity retrieval
        result = await entity_retrieval_node(updated_state)
        result["retry_count"] = retry_count
        result["retried"] = True

        return result

    except Exception as e:
        logger.error(f"Entity retrieval retry failed: {e}")
        return await fallback_entity_retrieval_node(state)


async def fallback_entity_retrieval_node(state: RAGState) -> Dict[str, Any]:
    """Fallback entity retrieval using basic vector search."""
    logger.warning("Using fallback entity retrieval")

    try:
        from arango import ArangoClient
        from app.services.integrations.embeddings import get_backend
        import os

        # Initialize basic database connection
        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db_name = os.getenv("ARANGO_DB", "_system")
        db = arango.db(
            db_name,
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        # Get embedding backend
        backend_name = os.getenv("EMBEDDING_BACKEND", "local").lower()
        embedding_backend = get_backend(backend_name)

        # Generate query embedding
        query_vector = embedding_backend.embed([state["user_query"]])[0]

        # Simple vector search without clustering
        query = """
        FOR entity IN v_meta
            SEARCH ANALYZER(PHRASE(entity.display_entity_id, @query_text) OR 
                          PHRASE(entity.area_name, @query_text) OR
                          PHRASE(entity.domain, @query_text), "text_en")
            OR COSINE_SIMILARITY(entity.embedding, @query_vector) > @threshold
            
            LET similarity = COSINE_SIMILARITY(entity.embedding, @query_vector)
            FILTER similarity > @threshold
            
            SORT similarity DESC
            LIMIT @k
            
            RETURN MERGE(entity, {
                similarity: similarity,
                _score: similarity,
                _fallback_retrieval: true
            })
        """

        # Conservative parameters for fallback
        k = min(20, state.get("optimal_k", 15) or 15)
        threshold = 0.5  # Lower threshold for broader coverage

        cursor = db.aql.execute(
            query,
            bind_vars={
                "query_text": state["user_query"],
                "query_vector": query_vector,
                "threshold": threshold,
                "k": k,
            },
        )

        retrieved_entities = list(cursor)

        logger.info(f"Fallback retrieval found {len(retrieved_entities)} entities")

        return {
            "retrieved_entities": retrieved_entities,
            "cluster_entities": [],  # No clusters in fallback
            "memory_entities": [],  # No memory integration in fallback
            "fallback_used": True,
        }

    except Exception as e:
        logger.error(f"Fallback entity retrieval failed: {e}")
        # Ultimate fallback: return empty results
        return {
            "retrieved_entities": [],
            "cluster_entities": [],
            "memory_entities": [],
            "fallback_used": True,
            "errors": state.get("errors", [])
            + [f"All entity retrieval failed: {str(e)}"],
        }


async def retry_formatting_node(state: RAGState) -> Dict[str, Any]:
    """Retry context formatting with different formatter."""
    retry_count = state.get("retry_count", 0) + 1
    logger.info(f"Retrying context formatting (attempt {retry_count})")

    try:
        from .routing import select_fallback_formatter
        from .nodes import context_formatting_node

        # Update state with retry information
        updated_state = state.copy()
        updated_state["retry_count"] = retry_count

        # Force a different formatter
        fallback_formatter = select_fallback_formatter(state)
        updated_state["_force_formatter"] = fallback_formatter

        logger.info(f"Retry formatting with forced formatter: {fallback_formatter}")

        result = await context_formatting_node(updated_state)
        result["retry_count"] = retry_count
        result["retried"] = True

        return result

    except Exception as e:
        logger.error(f"Context formatting retry failed: {e}")
        return await emergency_formatting_node(state)


async def emergency_formatting_node(state: RAGState) -> Dict[str, Any]:
    """Emergency context formatting with minimal processing."""
    logger.warning("Using emergency context formatting")

    try:
        retrieved_entities = state.get("retrieved_entities", [])

        if not retrieved_entities:
            return {
                "formatted_context": "You are a Home Assistant agent.\n\nNo relevant entities found for this query.",
                "formatter_type": "emergency_empty",
            }

        # Very simple formatting
        entity_list = []
        for i, entity in enumerate(retrieved_entities[:10]):  # Limit to 10 entities
            entity_id = entity.get("entity_id", f"unknown_{i}")
            state_value = entity.get("state", "unknown")
            domain = entity.get("domain", "unknown")

            entity_list.append(f"- {entity_id} ({domain}): {state_value}")

        formatted_context = f"""You are a Home Assistant agent.

Available entities:
{chr(10).join(entity_list)}

Please help the user with their request."""

        return {
            "formatted_context": formatted_context,
            "formatter_type": "emergency_simple",
        }

    except Exception as e:
        logger.error(f"Emergency formatting failed: {e}")
        return {
            "formatted_context": "You are a Home Assistant agent.\n\nSystem error: Unable to format context.",
            "formatter_type": "emergency_error",
            "errors": state.get("errors", [])
            + [f"Emergency formatting failed: {str(e)}"],
        }


async def cleanup_memory_node(state: RAGState) -> Dict[str, Any]:
    """Clean up expired conversation memories."""
    logger.info("Running conversation memory cleanup")

    try:
        memory_service = ConversationMemoryService()
        cleaned_count = await memory_service.cleanup_all_expired()

        logger.info(
            f"Memory cleanup completed: {cleaned_count} expired memories removed"
        )

        return {"cleanup_performed": True, "cleaned_memories": cleaned_count}

    except Exception as e:
        logger.error(f"Memory cleanup failed: {e}")
        return {
            "cleanup_performed": False,
            "cleanup_error": str(e),
            "errors": state.get("errors", []) + [f"Memory cleanup failed: {str(e)}"],
        }


async def continue_without_memory_node(state: RAGState) -> Dict[str, Any]:
    """Continue workflow without conversation memory when memory service fails."""
    logger.warning("Continuing without conversation memory due to service failure")

    # Remove memory-related errors and continue
    errors = [e for e in state.get("errors", []) if "memory" not in e.lower()]

    return {"memory_disabled": True, "memory_entities": [], "errors": errors}


async def workflow_diagnostics_node(state: RAGState) -> Dict[str, Any]:
    """Diagnostic node to assess workflow performance and log metrics."""
    logger.info("Running workflow diagnostics")

    try:
        from .routing import assess_workflow_quality

        # Assess overall workflow quality
        quality_metrics = assess_workflow_quality(state)

        # Log diagnostic information
        logger.info("Workflow quality assessment:")
        logger.info(f"  - Overall quality: {quality_metrics['overall_quality']:.2f}")
        logger.info(
            f"  - Conversation analysis: {quality_metrics['conversation_analysis_quality']:.2f}"
        )
        logger.info(
            f"  - Scope detection: {quality_metrics['scope_detection_quality']:.2f}"
        )
        logger.info(
            f"  - Entity retrieval: {quality_metrics['entity_retrieval_quality']:.2f}"
        )
        logger.info(
            f"  - Context formatting: {quality_metrics['context_formatting_quality']:.2f}"
        )

        if quality_metrics["recommendations"]:
            logger.info(
                f"  - Recommendations: {', '.join(quality_metrics['recommendations'])}"
            )

        # Add diagnostic info to state
        return {"diagnostics": quality_metrics, "workflow_completed": True}

    except Exception as e:
        logger.error(f"Workflow diagnostics failed: {e}")
        return {"diagnostics": {"error": str(e)}, "workflow_completed": True}
