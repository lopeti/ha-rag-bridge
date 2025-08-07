"""Conditional routing logic for LangGraph workflow Phase 3."""

from typing import Literal
from ha_rag_bridge.logging import get_logger
from .state import RAGState, QueryScope

logger = get_logger(__name__)


def route_after_conversation_analysis(
    state: RAGState,
) -> Literal["scope_detection", "fallback_analysis"]:
    """Route after conversation analysis based on confidence."""

    context = state.get("conversation_context", {})
    confidence = context.get("confidence", 0.0)

    if confidence >= 0.5:  # High confidence in conversation analysis
        logger.debug(
            "Routing to scope_detection after successful conversation analysis"
        )
        return "scope_detection"
    else:
        logger.warning("Low confidence in conversation analysis, using fallback")
        return "fallback_analysis"


def route_after_scope_detection(
    state: RAGState,
) -> Literal["entity_retrieval", "retry_scope_detection", "fallback_scope_detection"]:
    """Route based on scope detection confidence and error state."""

    scope_confidence = state.get("scope_confidence", 0.0)
    errors = state.get("errors", [])
    retry_count = state.get("retry_count", 0)
    user_query = state.get("user_query", "")

    # Check for critical errors first
    has_critical_errors = any(
        "scope detection failed" in error.lower() for error in errors
    )

    # Enhanced error detection for problematic queries
    is_problematic_query = (
        len(user_query.strip()) == 0  # Empty query
        or len(user_query.strip()) < 3  # Too short
        or user_query.strip().isdigit()  # Only numbers
        or not any(c.isalpha() for c in user_query)  # No letters
        or any(
            word in user_query.lower()
            for word in ["qwerty", "xyz", "12345", "test123", "asdf"]
        )  # Garbage input
    )

    if is_problematic_query:
        logger.warning(
            f"Problematic query detected: '{user_query}' - routing to fallback"
        )
        return "fallback_scope_detection"

    if has_critical_errors and retry_count < 2:
        logger.info(f"Scope detection errors detected, retry attempt {retry_count + 1}")
        return "retry_scope_detection"
    elif has_critical_errors:
        logger.warning("Max retries reached for scope detection, using fallback")
        return "fallback_scope_detection"
    elif scope_confidence < 0.5 and retry_count < 1:  # Lowered threshold
        logger.info(f"Low scope confidence ({scope_confidence:.2f}), attempting retry")
        return "retry_scope_detection"
    elif scope_confidence < 0.3:  # Lowered fallback threshold
        logger.warning(
            f"Very low scope confidence ({scope_confidence:.2f}), using fallback"
        )
        return "fallback_scope_detection"
    else:
        logger.debug(
            f"Scope detection successful (confidence: {scope_confidence:.2f}), proceeding to entity retrieval"
        )
        return "entity_retrieval"


def route_after_entity_retrieval(
    state: RAGState,
) -> Literal[
    "context_formatting", "retry_entity_retrieval", "fallback_entity_retrieval"
]:
    """Route after entity retrieval based on results quality."""

    retrieved_entities = state.get("retrieved_entities", [])
    cluster_entities = state.get("cluster_entities", [])
    memory_entities = state.get("memory_entities", [])
    errors = state.get("errors", [])
    retry_count = state.get("retry_count", 0)

    # Check for retrieval errors
    has_retrieval_errors = any(
        "entity retrieval failed" in error.lower() for error in errors
    )

    if has_retrieval_errors and retry_count < 2:
        logger.info(f"Entity retrieval errors, retry attempt {retry_count + 1}")
        return "retry_entity_retrieval"
    elif not retrieved_entities and retry_count < 1:
        logger.warning(
            "No entities retrieved, attempting retry with different parameters"
        )
        return "retry_entity_retrieval"
    elif not retrieved_entities:
        logger.error("No entities retrieved after retries, using fallback")
        return "fallback_entity_retrieval"
    else:
        entity_count = len(retrieved_entities)
        cluster_count = len(cluster_entities)
        memory_count = len(memory_entities)

        logger.info(
            f"Entity retrieval successful: {entity_count} total, "
            f"{cluster_count} from clusters, {memory_count} from memory"
        )
        return "context_formatting"


def route_after_context_formatting(
    state: RAGState,
) -> Literal["llm_interaction", "retry_formatting"]:
    """Route after context formatting based on output quality."""

    formatted_context = state.get("formatted_context", "")
    formatter_type = state.get("formatter_type", "")
    retry_count = state.get("retry_count", 0)

    # Basic quality checks
    has_sufficient_content = len(formatted_context) > 50  # Lowered threshold
    has_valid_formatter = formatter_type in [
        "compact",
        "detailed",
        "grouped_by_area",
        "tldr",
        "emergency_simple",
        "emergency_empty",
    ]

    if not has_sufficient_content and retry_count < 1:
        logger.warning("Insufficient context content, attempting retry")
        return "retry_formatting"
    elif not has_valid_formatter and retry_count < 1:
        logger.warning(f"Invalid formatter type: {formatter_type}, attempting retry")
        return "retry_formatting"
    else:
        logger.debug(
            f"Context formatting successful: {len(formatted_context)} chars, formatter: {formatter_type}"
        )
        return "llm_interaction"  # This gets remapped to workflow_diagnostics in workflow definition


def should_cleanup_memory(state: RAGState) -> Literal["cleanup_memory", "end"]:
    """Decide whether to run memory cleanup after workflow completion."""

    session_id = state.get("session_id", "")
    query_count = state.get("conversation_context", {}).get("query_count", 1)

    # Always run cleanup for test sessions to validate functionality
    should_cleanup = (
        query_count % 5 == 0  # Every 5th query (more frequent for testing)
        or session_id
        and "test" in session_id.lower()  # Test sessions
        or session_id.startswith("test_")  # Test session pattern
    )

    if should_cleanup:
        logger.info(f"Scheduling conversation memory cleanup for session: {session_id}")
        return "cleanup_memory"
    else:
        logger.debug(f"Skipping cleanup for session: {session_id}")
        return "end"


def determine_retry_strategy(state: RAGState) -> dict:
    """Determine retry strategy based on current state and error patterns."""

    errors = state.get("errors", [])
    retry_count = state.get("retry_count", 0)
    detected_scope = state.get("detected_scope")

    strategy = {
        "should_retry": False,
        "modify_k": False,
        "new_k": None,
        "modify_scope": False,
        "new_scope": None,
        "use_fallback": False,
    }

    if retry_count >= 3:
        strategy["use_fallback"] = True
        return strategy

    # Analyze error patterns
    scope_errors = [e for e in errors if "scope" in e.lower()]
    retrieval_errors = [e for e in errors if "retrieval" in e.lower()]

    if scope_errors and retry_count < 2:
        strategy["should_retry"] = True
        strategy["modify_scope"] = True
        # Fallback to MACRO scope for safer retrieval
        strategy["new_scope"] = QueryScope.MACRO
        logger.info("Retry strategy: Adjusting scope to MACRO for safer retrieval")

    elif retrieval_errors and retry_count < 2:
        strategy["should_retry"] = True
        strategy["modify_k"] = True
        # Increase k for better entity coverage
        current_k = state.get("optimal_k", 15)
        strategy["new_k"] = min(50, current_k * 2)
        logger.info(
            f"Retry strategy: Increasing k from {current_k} to {strategy['new_k']}"
        )

    elif not state.get("retrieved_entities") and retry_count < 1:
        strategy["should_retry"] = True
        strategy["modify_k"] = True
        strategy["modify_scope"] = True
        strategy["new_k"] = 30  # Broader search
        strategy["new_scope"] = QueryScope.OVERVIEW  # Broader scope
        logger.info("Retry strategy: Broadening search with k=30 and OVERVIEW scope")

    return strategy


def select_fallback_formatter(state: RAGState) -> str:
    """Select appropriate fallback formatter when primary formatting fails."""

    retrieved_entities = state.get("retrieved_entities", [])
    detected_scope = state.get("detected_scope")

    # Conservative fallback selection
    if not retrieved_entities:
        return "empty"
    elif len(retrieved_entities) <= 3:
        return "compact"
    elif len(retrieved_entities) <= 8:
        return "detailed"
    elif detected_scope == QueryScope.OVERVIEW:
        return "tldr"
    else:
        return "grouped_by_area"


def get_error_recovery_node(error_type: str) -> str:
    """Map error types to appropriate recovery nodes."""

    error_mapping = {
        "conversation_analysis": "fallback_analysis",
        "scope_detection": "fallback_scope_detection",
        "entity_retrieval": "fallback_entity_retrieval",
        "context_formatting": "retry_formatting",
        "memory_service": "continue_without_memory",
        "database": "fallback_entity_retrieval",
    }

    for error_key, recovery_node in error_mapping.items():
        if error_key in error_type.lower():
            logger.info(f"Error recovery: {error_type} -> {recovery_node}")
            return recovery_node

    # Default fallback
    logger.warning(
        f"No specific recovery for error type: {error_type}, using general fallback"
    )
    return "fallback_entity_retrieval"


def assess_workflow_quality(state: RAGState) -> dict:
    """Assess overall workflow quality and provide recommendations."""

    quality_metrics = {
        "conversation_analysis_quality": 0.0,
        "scope_detection_quality": 0.0,
        "entity_retrieval_quality": 0.0,
        "context_formatting_quality": 0.0,
        "overall_quality": 0.0,
        "recommendations": [],
    }

    # Conversation analysis quality
    context = state.get("conversation_context", {})
    if context:
        confidence = context.get("confidence", 0.0)
        has_areas = bool(context.get("areas_mentioned"))
        has_domains = bool(context.get("domains_mentioned"))

        quality_metrics["conversation_analysis_quality"] = (
            confidence * 0.6
            + (0.2 if has_areas else 0.0)
            + (0.2 if has_domains else 0.0)
        )

    # Scope detection quality
    scope_confidence = state.get("scope_confidence", 0.0)
    has_scope = state.get("detected_scope") is not None
    quality_metrics["scope_detection_quality"] = scope_confidence if has_scope else 0.0

    # Entity retrieval quality
    retrieved_entities = state.get("retrieved_entities", [])
    cluster_entities = state.get("cluster_entities", [])
    memory_entities = state.get("memory_entities", [])

    if retrieved_entities:
        cluster_ratio = len(cluster_entities) / len(retrieved_entities)
        memory_ratio = len(memory_entities) / max(1, len(retrieved_entities))
        avg_score = sum(e.get("_score", 0.0) for e in retrieved_entities) / len(
            retrieved_entities
        )

        quality_metrics["entity_retrieval_quality"] = min(
            1.0, avg_score * 0.4 + cluster_ratio * 0.3 + memory_ratio * 0.3
        )

    # Context formatting quality
    formatted_context = state.get("formatted_context", "")
    formatter_type = state.get("formatter_type", "")

    if formatted_context:
        length_score = min(
            1.0, len(formatted_context) / 1000
        )  # Normalize to 1000 chars
        has_valid_formatter = formatter_type in [
            "compact",
            "detailed",
            "grouped_by_area",
            "tldr",
        ]

        quality_metrics["context_formatting_quality"] = length_score * 0.7 + (
            0.3 if has_valid_formatter else 0.0
        )

    # Calculate overall quality
    quality_metrics["overall_quality"] = (
        quality_metrics["conversation_analysis_quality"] * 0.2
        + quality_metrics["scope_detection_quality"] * 0.25
        + quality_metrics["entity_retrieval_quality"] * 0.35
        + quality_metrics["context_formatting_quality"] * 0.2
    )

    # Generate recommendations
    if quality_metrics["overall_quality"] < 0.6:
        quality_metrics["recommendations"].append(
            "Consider tuning similarity thresholds"
        )

    if quality_metrics["entity_retrieval_quality"] < 0.5:
        quality_metrics["recommendations"].append(
            "Review cluster definitions and entity relationships"
        )

    if len(retrieved_entities) < 3:
        quality_metrics["recommendations"].append(
            "Consider lowering similarity thresholds or expanding k values"
        )

    if not cluster_entities and retrieved_entities:
        quality_metrics["recommendations"].append(
            "Check cluster-entity mappings for query domain"
        )

    return quality_metrics
