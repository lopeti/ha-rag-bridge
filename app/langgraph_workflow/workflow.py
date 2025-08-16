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


def _extract_entity_pipeline(final_state: dict) -> List[dict]:
    """Extract entity pipeline data from final workflow state."""
    from app.services.workflow_tracer import EntityStageInfo

    pipeline_stages = []

    # Stage 1: Cluster Search (if cluster entities exist)
    if final_state.get("cluster_entities"):
        cluster_stage = EntityStageInfo(
            stage="cluster_search",
            entity_count=len(final_state["cluster_entities"]),
            entities=final_state["cluster_entities"],
            scores={},
            filters_applied=["cluster_based"],
            metadata={
                "detected_scope": str(final_state.get("detected_scope", "unknown")),
                "scope_confidence": final_state.get("scope_confidence", 0.0),
                "optimal_k": final_state.get("optimal_k", 0),
            },
        )
        pipeline_stages.append(cluster_stage)

    # Stage 2: Vector Search (retrieved entities)
    if final_state.get("retrieved_entities"):
        vector_stage = EntityStageInfo(
            stage=(
                "vector_fallback"
                if final_state.get("cluster_entities")
                else "vector_search"
            ),
            entity_count=len(final_state["retrieved_entities"]),
            entities=final_state["retrieved_entities"],
            scores={},
            filters_applied=["vector_similarity"],
            metadata={
                "optimal_k": final_state.get("optimal_k", 0),
                "fallback_used": final_state.get("fallback_used", False),
            },
        )
        pipeline_stages.append(vector_stage)

    # Stage 3: Memory Enhancement (if memory entities exist)
    if final_state.get("memory_entities"):
        memory_stage = EntityStageInfo(
            stage="memory_enhancement",
            entity_count=len(final_state["memory_entities"]),
            entities=final_state["memory_entities"],
            scores={},
            filters_applied=["conversation_memory"],
            metadata={
                "session_id": final_state.get("session_id", "unknown"),
                "memory_boost_applied": True,
            },
        )
        pipeline_stages.append(memory_stage)

    # Stage 4: Reranking (reranked entities)
    if final_state.get("reranked_entities"):
        rerank_stage = EntityStageInfo(
            stage="reranking",
            entity_count=len(final_state["reranked_entities"]),
            entities=final_state["reranked_entities"],
            scores={},
            filters_applied=["cross_encoder_reranking"],
            metadata={
                "formatter_type": final_state.get("formatter_type", "unknown"),
                "formatted_context_length": len(
                    final_state.get("formatted_context", "")
                ),
            },
        )
        pipeline_stages.append(rerank_stage)

    # Stage 5: Final Selection (this represents the final entities used in context)
    final_entities = (
        final_state.get("reranked_entities")
        or final_state.get("retrieved_entities")
        or []
    )
    if final_entities:
        final_stage = EntityStageInfo(
            stage="final_selection",
            entity_count=len(final_entities),
            entities=final_entities,
            scores={},
            filters_applied=["context_formatting"],
            metadata={
                "formatted_context_length": len(
                    final_state.get("formatted_context", "")
                ),
                "formatter_type": final_state.get("formatter_type", "unknown"),
                "total_errors": len(final_state.get("errors", [])),
            },
        )
        pipeline_stages.append(final_stage)

    return pipeline_stages


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

    # Initialize workflow tracer
    try:
        from app.services.workflow_tracer import workflow_tracer

        # Start a new trace
        trace_id = workflow_tracer.start_trace(
            session_id=session_id, user_query=user_query
        )
        logger.info(f"Started workflow trace: {trace_id}")
    except Exception as e:
        logger.warning(f"Failed to start workflow tracer: {e}")
        trace_id = None

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
        trace_id=trace_id,  # Add trace_id to state for node access
    )

    # Create and run workflow
    workflow = create_rag_workflow()

    logger.info(f"Running RAG workflow for query: {user_query[:50]}...")

    try:
        # Record workflow start
        if trace_id:
            try:
                workflow_tracer.start_node(
                    trace_id, "workflow_execution", initial_state
                )
            except Exception as e:
                logger.warning(f"Failed to record workflow start: {e}")

        final_state = await workflow.ainvoke(initial_state)

        # Record workflow completion
        if trace_id:
            try:
                workflow_tracer.end_node(trace_id, "workflow_execution", final_state)
            except Exception as e:
                logger.warning(f"Failed to record workflow completion: {e}")

        logger.info("RAG workflow completed successfully")

        if final_state.get("errors"):
            logger.warning(f"Workflow completed with errors: {final_state['errors']}")

        # Finish the trace with final state
        if trace_id:
            try:
                # Extract entity pipeline data from final state
                entity_pipeline = _extract_entity_pipeline(final_state)

                # Set entity pipeline data in the trace before ending it
                if trace_id in workflow_tracer.active_traces:
                    trace = workflow_tracer.active_traces[trace_id]
                    trace.entity_pipeline = entity_pipeline

                workflow_tracer.end_trace(
                    trace_id=trace_id,
                    final_result=final_state,
                    errors=final_state.get("errors"),
                )

                logger.info(
                    f"Finished workflow trace: {trace_id} with {len(entity_pipeline)} entity stages"
                )
            except Exception as e:
                logger.warning(f"Failed to finish workflow trace: {e}")

        return final_state

    except Exception as e:
        logger.error(f"RAG workflow failed: {e}")
        error_state = {
            **initial_state,
            "errors": [f"Workflow execution failed: {str(e)}"],
            "final_response": "Error: Workflow execution failed",
        }

        # Finish the trace with error state
        if trace_id:
            try:
                # Extract entity pipeline data even for error cases
                entity_pipeline = _extract_entity_pipeline(error_state)

                # Set entity pipeline data in the trace before ending it
                if trace_id in workflow_tracer.active_traces:
                    trace = workflow_tracer.active_traces[trace_id]
                    trace.entity_pipeline = entity_pipeline

                workflow_tracer.end_trace(
                    trace_id=trace_id,
                    final_result=error_state,
                    errors=error_state.get("errors"),
                )

                logger.info(
                    f"Finished workflow trace with error: {trace_id} with {len(entity_pipeline)} entity stages"
                )
            except Exception as tracer_e:
                logger.warning(f"Failed to finish error trace: {tracer_e}")

        return error_state
