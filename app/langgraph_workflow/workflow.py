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

logger = get_logger(__name__)


def create_rag_workflow() -> StateGraph:
    """Create the RAG workflow graph for Phase 1 (simple linear flow)."""

    workflow = StateGraph(RAGState)

    # Add Phase 1 nodes
    workflow.add_node("conversation_analysis", conversation_analysis_node)
    workflow.add_node("scope_detection", llm_scope_detection_node)
    workflow.add_node("entity_retrieval", entity_retrieval_node)  # Mock implementation
    workflow.add_node(
        "context_formatting", context_formatting_node
    )  # Mock implementation

    # Define simple linear flow (no conditional routing yet)
    workflow.set_entry_point("conversation_analysis")
    workflow.add_edge("conversation_analysis", "scope_detection")
    workflow.add_edge("scope_detection", "entity_retrieval")
    workflow.add_edge("entity_retrieval", "context_formatting")
    workflow.add_edge("context_formatting", END)

    logger.info(
        "Created Phase 1 RAG workflow: conversation_analysis → scope_detection → entity_retrieval → context_formatting"
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
