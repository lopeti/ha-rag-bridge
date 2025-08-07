"""LangGraph workflow definition for HA RAG system."""

from typing import List, Optional
from langgraph.graph import StateGraph, END
from ha_rag_bridge.logging import get_logger

from .state import RAGState
from .nodes import (
    conversation_analysis_node,
    llm_scope_detection_node,
    entity_retrieval_node,
    context_formatting_node,
)
from .fallback_nodes import (
    fallback_analysis_node,
    retry_scope_detection_node,
    fallback_scope_detection_node,
    retry_entity_retrieval_node,
    fallback_entity_retrieval_node,
    retry_formatting_node,
    cleanup_memory_node,
    workflow_diagnostics_node,
)
from .routing import (
    route_after_conversation_analysis,
    route_after_scope_detection,
    route_after_entity_retrieval,
    route_after_context_formatting,
    should_cleanup_memory,
)

logger = get_logger(__name__)


def create_rag_workflow() -> StateGraph:
    """Create the advanced RAG workflow graph for Phase 3 with conditional routing and error handling."""

    workflow = StateGraph(RAGState)

    # Add main workflow nodes
    workflow.add_node("conversation_analysis", conversation_analysis_node)
    workflow.add_node("scope_detection", llm_scope_detection_node)
    workflow.add_node("entity_retrieval", entity_retrieval_node)
    workflow.add_node("context_formatting", context_formatting_node)

    # Add fallback and retry nodes
    workflow.add_node("fallback_analysis", fallback_analysis_node)
    workflow.add_node("retry_scope_detection", retry_scope_detection_node)
    workflow.add_node("fallback_scope_detection", fallback_scope_detection_node)
    workflow.add_node("retry_entity_retrieval", retry_entity_retrieval_node)
    workflow.add_node("fallback_entity_retrieval", fallback_entity_retrieval_node)
    workflow.add_node("retry_formatting", retry_formatting_node)
    workflow.add_node("cleanup_memory", cleanup_memory_node)
    workflow.add_node("workflow_diagnostics", workflow_diagnostics_node)

    # Set entry point
    workflow.set_entry_point("conversation_analysis")

    # Conditional routing after conversation analysis
    workflow.add_conditional_edges(
        "conversation_analysis",
        route_after_conversation_analysis,
        {
            "scope_detection": "scope_detection",
            "fallback_analysis": "fallback_analysis",
        },
    )

    # Fallback analysis connects to scope detection
    workflow.add_edge("fallback_analysis", "scope_detection")

    # Conditional routing after scope detection
    workflow.add_conditional_edges(
        "scope_detection",
        route_after_scope_detection,
        {
            "entity_retrieval": "entity_retrieval",
            "retry_scope_detection": "retry_scope_detection",
            "fallback_scope_detection": "fallback_scope_detection",
        },
    )

    # Retry and fallback scope detection routes back to entity retrieval
    workflow.add_edge("retry_scope_detection", "entity_retrieval")
    workflow.add_edge("fallback_scope_detection", "entity_retrieval")

    # Conditional routing after entity retrieval
    workflow.add_conditional_edges(
        "entity_retrieval",
        route_after_entity_retrieval,
        {
            "context_formatting": "context_formatting",
            "retry_entity_retrieval": "retry_entity_retrieval",
            "fallback_entity_retrieval": "fallback_entity_retrieval",
        },
    )

    # Retry and fallback entity retrieval routes to context formatting
    workflow.add_edge("retry_entity_retrieval", "context_formatting")
    workflow.add_edge("fallback_entity_retrieval", "context_formatting")

    # Conditional routing after context formatting
    workflow.add_conditional_edges(
        "context_formatting",
        route_after_context_formatting,
        {
            "llm_interaction": "workflow_diagnostics",  # Skip LLM for now, go to diagnostics
            "retry_formatting": "retry_formatting",
        },
    )

    # Retry formatting routes to diagnostics
    workflow.add_edge("retry_formatting", "workflow_diagnostics")

    # Final cleanup and end routing
    workflow.add_conditional_edges(
        "workflow_diagnostics",
        should_cleanup_memory,
        {
            "cleanup_memory": "cleanup_memory",
            "end": END,
        },
    )

    # Cleanup memory ends the workflow
    workflow.add_edge("cleanup_memory", END)

    logger.info(
        "Created Phase 3 RAG workflow with conditional routing: "
        "conversation_analysis → scope_detection → entity_retrieval → "
        "context_formatting → workflow_diagnostics [→ cleanup_memory]"
    )

    return workflow.compile()


async def run_rag_workflow(
    user_query: str, session_id: str, conversation_history: Optional[List] = None
) -> dict:
    """Run the RAG workflow with given inputs."""

    if conversation_history is None:
        conversation_history = []

    # Initialize workflow state
    initial_state = RAGState(
        user_query=user_query,
        session_id=session_id,
        conversation_history=conversation_history,
        conversation_context=None,
        detected_scope=None,
        scope_confidence=0.0,
        optimal_k=None,
        retrieved_entities=[],
        cluster_entities=[],
        memory_entities=[],
        reranked_entities=[],
        formatted_context="",
        formatter_type="",
        llm_messages=[],
        llm_response=None,
        tool_calls=[],
        ha_results=[],
        final_response=None,
        errors=[],
        retry_count=0,
        fallback_used=False,
    )

    # Create and run workflow
    workflow = create_rag_workflow()

    logger.info(f"Running RAG workflow for query: {user_query[:50]}...")

    try:
        final_state = await workflow.ainvoke(initial_state)
        logger.info("RAG workflow completed successfully")

        if final_state.get("errors"):
            logger.warning(f"Workflow completed with errors: {final_state['errors']}")

        return final_state

    except Exception as e:
        logger.error(f"RAG workflow failed: {e}")
        return {
            **initial_state,
            "errors": [f"Workflow execution failed: {str(e)}"],
            "final_response": "Error: Workflow execution failed",
        }
