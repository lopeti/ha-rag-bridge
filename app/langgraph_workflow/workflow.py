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
    """Extract comprehensive entity pipeline data using Enhanced Pipeline Stages as the authoritative source."""
    from app.services.workflow_tracer import EntityStageInfo, workflow_tracer

    pipeline_stages = []

    # Get the trace_id to access Enhanced Pipeline Stages from the active trace
    trace_id = final_state.get("trace_id")
    enhanced_stages = []

    if trace_id and trace_id in workflow_tracer.active_traces:
        # Get Enhanced Pipeline Stages from the active trace
        trace = workflow_tracer.active_traces[trace_id]
        enhanced_stages = trace.enhanced_pipeline_stages

    # Create Entity Pipeline stages based on Enhanced Pipeline stages
    for enhanced_stage in enhanced_stages:
        stage_name = enhanced_stage.stage_name
        stage_type = enhanced_stage.stage_type
        input_count = enhanced_stage.input_count
        output_count = enhanced_stage.output_count

        # Map enhanced stage names to entity data and determine entities to use
        entities = []
        filters_applied = []
        metadata = {}

        if stage_name == "query_rewriting":
            # Query rewriting doesn't have entities, but track the transformation
            entities = []
            filters_applied = ["query_transformation"]
            metadata = {"rewrite_method": "conversational", "processing_stage": "input"}
            entity_count = 1  # Always 1 query in/out

        elif stage_name == "conversation_summary":
            # Conversation summary processes conversation history
            entities = []
            filters_applied = ["conversation_analysis"]
            metadata = {
                "conversation_turns": input_count,
                "processing_stage": "context",
            }
            entity_count = output_count

        elif stage_name == "cluster_search":
            # Use cluster entities from final state
            cluster_entities = final_state.get("cluster_entities", [])
            entities = workflow_tracer._sanitize_entities(cluster_entities)
            filters_applied = ["cluster_based"]
            metadata = {
                "detected_scope": str(final_state.get("detected_scope", "unknown")),
                "cluster_types": getattr(enhanced_stage, "cluster_search", {}).get(
                    "cluster_types", []
                ),
                "optimal_k": final_state.get("optimal_k", 0),
            }
            entity_count = len(cluster_entities)

        elif stage_name == "vector_search":
            # Use retrieved entities from final state
            retrieved_entities = final_state.get("retrieved_entities", [])
            entities = workflow_tracer._sanitize_entities(retrieved_entities)
            filters_applied = ["vector_similarity"]
            metadata = {
                "optimal_k": final_state.get("optimal_k", 0),
                "backend": getattr(enhanced_stage, "vector_search", {}).get(
                    "backend", "unknown"
                ),
                "fallback_used": final_state.get("fallback_used", False),
            }
            entity_count = len(retrieved_entities)

        elif stage_name == "memory_boost":
            # Use memory entities from final state
            memory_entities = final_state.get("memory_entities", [])
            entities = workflow_tracer._sanitize_entities(memory_entities)
            filters_applied = ["conversation_memory"]
            metadata = {
                "session_id": final_state.get("session_id", "unknown"),
                "memory_boost_applied": len(memory_entities) > 0,
                "boosted_count": getattr(enhanced_stage, "memory_boost", {}).get(
                    "boosted_entities", 0
                ),
            }
            entity_count = len(memory_entities)

        elif stage_name == "reranking":
            # Use reranked entities or retrieved entities as fallback
            reranked_entities = final_state.get(
                "reranked_entities", final_state.get("retrieved_entities", [])
            )
            entities = workflow_tracer._sanitize_entities(reranked_entities)
            filters_applied = ["cross_encoder_reranking"]
            metadata = {
                "reranking_method": "semantic_cross_encoder",
                "original_count": input_count,
                "reranked_count": len(reranked_entities),
            }
            entity_count = len(reranked_entities)

        elif stage_name == "final_selection":
            # Use the final entities that made it to the formatted context
            # This should represent the actual entities used in the prompt
            final_entities = (
                final_state.get("reranked_entities")
                or final_state.get("retrieved_entities")
                or []
            )
            # Use output_count from enhanced stage as the authoritative count
            final_entities_limited = (
                final_entities[:output_count] if output_count > 0 else final_entities
            )
            entities = workflow_tracer._sanitize_entities(final_entities_limited)
            filters_applied = ["context_formatting", "entity_limit"]
            metadata = {
                "formatter_type": final_state.get("formatter_type", "unknown"),
                "formatted_context_length": len(
                    final_state.get("formatted_context", "")
                ),
                "entities_selected": output_count,
                "total_available": len(final_entities),
            }
            entity_count = (
                output_count  # Use the authoritative count from enhanced stage
            )
        else:
            # Unknown stage, create a generic entry
            entities = []
            filters_applied = [f"unknown_{stage_type}"]
            metadata = {"stage_type": stage_type}
            entity_count = output_count

        # Create EntityStageInfo using the Enhanced Pipeline data
        entity_stage = EntityStageInfo(
            stage=stage_name,
            entity_count=entity_count,
            entities=entities,
            scores={},
            filters_applied=filters_applied,
            metadata=metadata,
        )
        pipeline_stages.append(entity_stage)

    # Fallback: if no enhanced stages found, use the old logic
    if not pipeline_stages:
        # Fallback to the old method for backward compatibility
        if final_state.get("retrieved_entities"):
            retrieved_entities = final_state["retrieved_entities"]
            vector_stage = EntityStageInfo(
                stage="vector_search_fallback",
                entity_count=len(retrieved_entities),
                entities=workflow_tracer._sanitize_entities(retrieved_entities),
                scores={},
                filters_applied=["vector_similarity"],
                metadata={"fallback_method": "legacy"},
            )
            pipeline_stages.append(vector_stage)

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
