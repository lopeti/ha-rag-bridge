"""LangGraph workflow nodes for HA RAG system."""

from typing import Dict, Any
from app.schemas import ChatMessage
from ha_rag_bridge.logging import get_logger
from app.services.conversation_analyzer import ConversationAnalyzer

from .state import RAGState, QueryScope

logger = get_logger(__name__)


async def conversation_analysis_node(state: RAGState) -> Dict[str, Any]:
    """Analyze conversation context and extract metadata."""
    logger.info(
        f"ConversationAnalysisNode: Processing query: {state['user_query'][:50]}..."
    )

    try:
        analyzer = ConversationAnalyzer()
        # Convert dict messages to ChatMessage objects
        chat_messages = [
            ChatMessage(role=msg["role"], content=msg["content"])
            for msg in state["conversation_history"]
        ]
        context = analyzer.analyze_conversation(state["user_query"], chat_messages)

        logger.debug(f"Conversation analysis result: {context}")

        return {
            "conversation_context": {
                "areas_mentioned": list(context.areas_mentioned),
                "domains_mentioned": list(context.domains_mentioned),
                "is_follow_up": context.is_follow_up,
                "intent": context.intent,
                "confidence": context.confidence,
            }
        }

    except Exception as e:
        logger.error(f"Error in conversation analysis: {e}")
        return {
            "conversation_context": {
                "areas_mentioned": [],
                "domains_mentioned": [],
                "is_follow_up": False,
                "intent": "read",
                "confidence": 0.0,
            },
            "errors": state.get("errors", [])
            + [f"Conversation analysis failed: {str(e)}"],
        }


async def llm_scope_detection_node(state: RAGState) -> Dict[str, Any]:
    """LLM-based scope detection replacing regex patterns."""
    logger.info("LLM Scope Detection: Classifying query scope...")

    try:
        # Enhanced classification logic with area + scope interaction
        # This is a temporary implementation for Phase 1 PoC
        context = state.get("conversation_context", {})
        query_lower = state["user_query"].lower()
        areas = context.get("areas_mentioned", []) if context else []

        # Priority 1: Check for area-scoped control actions (should be MACRO, not MICRO)
        has_control_action = any(
            word in query_lower
            for word in ["kapcsold", "indítsd", "állítsd", "turn", "switch"]
        )
        has_quantity_modifier = any(
            word in query_lower for word in ["összes", "minden", "all"]
        )
        has_area = len(areas) > 0

        if has_control_action and has_quantity_modifier:
            # "kapcsold fel az összes lámpát a konyhában" → MACRO (quantity modifier takes priority)
            scope = QueryScope.MACRO
            optimal_k = 25
            confidence = 0.85
            reasoning = "Control action with quantity modifier (összes/minden/all)"
        elif has_control_action and has_area and not has_quantity_modifier:
            # "turn on the kitchen light" → MICRO (single device in area, no quantity)
            scope = QueryScope.MICRO
            optimal_k = 8
            confidence = 0.75
            reasoning = "Single device control action in specific area"
        elif has_control_action and not has_area and not has_quantity_modifier:
            # "kapcsold fel a lámpát" → MICRO
            scope = QueryScope.MICRO
            optimal_k = 7
            confidence = 0.8
            reasoning = "Simple control action without area scope"
        elif (
            any(word in query_lower for word in ["mennyi", "hány fok"])
            and not has_quantity_modifier
        ):
            # "hány fok van a kertben?" → MICRO (specific value query)
            scope = QueryScope.MICRO
            optimal_k = 7
            confidence = 0.8
            reasoning = "Specific value query"
        elif len(areas) == 1 and not any(
            word in query_lower for word in ["otthon", "house", "home"]
        ):
            # Single area mentioned → MACRO
            scope = QueryScope.MACRO
            optimal_k = 22
            confidence = 0.7
            reasoning = "Single area-specific query"
        elif (
            any(word in query_lower for word in ["otthon", "house", "home"])
            or len(areas) > 1
        ):
            # House-wide or multiple areas → OVERVIEW
            scope = QueryScope.OVERVIEW
            optimal_k = 45
            confidence = 0.75
            reasoning = "House-wide or multi-area query"
        elif any(word in query_lower for word in ["minden", "all", "összes"]):
            # Global quantifiers → OVERVIEW
            scope = QueryScope.OVERVIEW
            optimal_k = 45
            confidence = 0.8
            reasoning = "Global quantifier detected"
        else:
            # Default fallback based on query length
            if len(query_lower.split()) <= 3:
                scope = QueryScope.MICRO
                optimal_k = 8
                confidence = 0.5
                reasoning = "Short query fallback"
            elif len(query_lower.split()) >= 8:
                scope = QueryScope.OVERVIEW
                optimal_k = 35
                confidence = 0.5
                reasoning = "Long query fallback"
            else:
                scope = QueryScope.MACRO
                optimal_k = 18
                confidence = 0.5
                reasoning = "Medium length query fallback"

        logger.info(
            f"Scope detected: {scope.value} (k={optimal_k}, confidence={confidence:.2f})"
        )
        logger.debug(f"Reasoning: {reasoning}")

        return {
            "detected_scope": scope,
            "scope_confidence": confidence,
            "optimal_k": optimal_k,
            "scope_reasoning": reasoning,
        }

    except Exception as e:
        logger.error(f"Error in scope detection: {e}")
        return {
            "detected_scope": QueryScope.MACRO,  # Safe fallback
            "scope_confidence": 0.3,
            "optimal_k": 20,
            "scope_reasoning": f"Error fallback: {str(e)}",
            "errors": state.get("errors", []) + [f"Scope detection failed: {str(e)}"],
        }


# TODO: Implement remaining nodes in subsequent phases
async def entity_retrieval_node(state: RAGState) -> Dict[str, Any]:
    """Placeholder for entity retrieval with clustering."""
    logger.info("EntityRetrieval: Not implemented yet - using mock data")

    return {
        "retrieved_entities": [],
        "cluster_entities": [],
        "errors": state.get("errors", [])
        + ["Entity retrieval not implemented in Phase 1"],
    }


async def context_formatting_node(state: RAGState) -> Dict[str, Any]:
    """Placeholder for context formatting."""
    logger.info("ContextFormatting: Not implemented yet")

    return {
        "formatted_context": "Mock formatted context for Phase 1 PoC",
        "formatter_type": "mock",
        "errors": state.get("errors", [])
        + ["Context formatting not implemented in Phase 1"],
    }
