"""LangGraph workflow nodes for HA RAG system."""

from typing import Dict, Any, List, Optional, cast
from app.schemas import ChatMessage
from ha_rag_bridge.logging import get_logger
from app.services.conversation.conversation_analyzer import ConversationAnalyzer
from app.services.conversation.conversation_memory import ConversationMemoryService
from app.services.rag.query_rewriter import ConversationalQueryRewriter
from app.services.core.workflow_tracer import EnhancedPipelineStage

from .state import RAGState, QueryScope

logger = get_logger(__name__)


async def conversation_analysis_node(state: RAGState) -> Dict[str, Any]:
    """Analyze conversation context and extract metadata with query rewriting."""
    logger.info(
        f"ConversationAnalysisNode: Processing query: {state['user_query'][:50]}..."
    )

    try:
        # Convert dict messages to ChatMessage objects
        chat_messages = [
            ChatMessage(role=msg["role"], content=msg["content"])
            for msg in state["conversation_history"]
        ]

        # Step 1: Query rewriting for conversational context
        from datetime import datetime

        rewrite_start = datetime.now()

        query_rewriter = ConversationalQueryRewriter()
        rewrite_result = await query_rewriter.rewrite_query(
            current_query=state["user_query"],
            conversation_history=chat_messages,
            conversation_memory=None,  # TODO: Add memory context
        )

        rewrite_duration = (datetime.now() - rewrite_start).total_seconds() * 1000

        # Update state with rewrite information
        result_data: Dict[str, Any] = {}
        if rewrite_result.method != "no_rewrite_needed":
            logger.info(
                f"Query rewritten: '{rewrite_result.original_query}' -> '{rewrite_result.rewritten_query}'"
            )
            result_data["original_query"] = rewrite_result.original_query
            result_data["user_query"] = rewrite_result.rewritten_query
            result_data["query_rewrite_info"] = {
                "original": rewrite_result.original_query,
                "rewritten": rewrite_result.rewritten_query,
                "confidence": rewrite_result.confidence,
                "method": rewrite_result.method,
                "reasoning": rewrite_result.reasoning,
                "processing_time_ms": rewrite_result.processing_time_ms,
                "coreferences_resolved": rewrite_result.coreferences_resolved,
                "intent_inherited": rewrite_result.intent_inherited,
            }
        else:
            logger.debug("No query rewriting needed")

        # Step 2: Conversation analysis (use rewritten query if available)
        analysis_query = (
            rewrite_result.rewritten_query
            if rewrite_result.method != "no_rewrite_needed"
            else state["user_query"]
        )

        analyzer = ConversationAnalyzer()
        context = analyzer.analyze_conversation(analysis_query, chat_messages)

        logger.debug(f"Conversation analysis result: {context}")

        result_data["conversation_context"] = {
            "areas_mentioned": list(context.areas_mentioned),
            "domains_mentioned": list(context.domains_mentioned),
            "is_follow_up": context.is_follow_up,
            "intent": context.intent,
            "confidence": context.confidence,
        }

        # Step 3: NEW - Refactored Async Memory Processing
        memory_start = datetime.now()
        session_id = state.get("session_id", "default")

        # Convert ChatMessage objects to history format
        history_for_processing = []
        for msg in chat_messages:
            if msg.role == "user":
                history_for_processing.append({"user_message": msg.content})
            elif msg.role == "assistant":
                history_for_processing.append({"assistant_message": msg.content})

        try:
            # Step 3a: SZINKRON - Gyors pattern elemzés (<50ms)
            from app.services.conversation.quick_pattern_analyzer import (
                QuickPatternAnalyzer,
            )

            quick_analyzer = QuickPatternAnalyzer()
            quick_context = quick_analyzer.analyze(
                query=analysis_query, history=history_for_processing
            )

            logger.info(
                f"Quick pattern analysis: domains={quick_context.detected_domains}, areas={quick_context.detected_areas}, type={quick_context.query_type}, time={quick_context.processing_time_ms}ms"
            )

            # Step 3b: CACHE CHECK - Van-e előző körből enriched context?
            from app.services.conversation.async_conversation_enricher import (
                AsyncConversationEnricher,
            )

            memory_service = ConversationMemoryService()
            enricher = AsyncConversationEnricher(memory_service)

            cached_enrichment = await enricher.get_cached_enrichment(session_id)

            # Step 3c: KOMBINÁCIÓ - Quick + Cached context
            if cached_enrichment:
                # Merge quick analysis with cached enrichment
                result_data["conversation_summary"] = {
                    "detected_domains": list(
                        set(quick_context.detected_domains)
                        | set(cached_enrichment.detected_domains)
                    ),
                    "mentioned_areas": list(
                        set(quick_context.detected_areas)
                        | set(cached_enrichment.mentioned_areas)
                    ),
                    "query_type": quick_context.query_type,
                    "language": quick_context.language,
                    "processing_source": "quick_analysis + cached_enrichment",
                    "llm_used": True,
                    "cached_context": {
                        "intent_chain": cached_enrichment.intent_chain,
                        "semantic_context": cached_enrichment.semantic_context,
                        "expected_followups": cached_enrichment.expected_followups,
                        "entity_boost_weights": cached_enrichment.entity_boost_weights,
                        "user_patterns": cached_enrichment.user_patterns,
                    },
                }
                logger.info(
                    f"Using cached enrichment for session {session_id}: {len(cached_enrichment.entity_boost_weights)} entity boosts"
                )
            else:
                # Use csak quick analysis
                result_data["conversation_summary"] = {
                    "detected_domains": list(quick_context.detected_domains),
                    "mentioned_areas": list(quick_context.detected_areas),
                    "query_type": quick_context.query_type,
                    "language": quick_context.language,
                    "processing_source": "quick_analysis_only",
                    "llm_used": False,
                }
                logger.debug("Using quick pattern analysis for conversation summary")

            # Step 3d: TRIGGER BACKGROUND ENRICHMENT (fire-and-forget)
            # Fire-and-forget: do NOT await, just trigger background processing
            import asyncio

            asyncio.create_task(
                enricher.enrich_async(
                    session_id=session_id,
                    query=analysis_query,
                    history=history_for_processing,
                    retrieved_entities=None,  # Majd később kapja meg
                    quick_context=cast(
                        Optional[Dict[str, Any]],
                        result_data.get("conversation_summary"),
                    ),
                )
            )
            logger.info(
                f"🔥 Background enrichment triggered (fire-and-forget) for session {session_id}"
            )

            # Add quick analysis details for debugging
            result_data["quick_analysis"] = {
                "detected_domains": list(quick_context.detected_domains),
                "detected_areas": list(quick_context.detected_areas),
                "entity_patterns": list(quick_context.entity_patterns),
                "suggested_entity_types": list(quick_context.suggested_entity_types),
                "confidence": quick_context.confidence,
                "processing_time_ms": quick_context.processing_time_ms,
                "pattern_matches": quick_context.pattern_matches,
                "matched_keywords": quick_context.matched_keywords,
            }

        except Exception as e:
            logger.warning(f"Async memory processing failed: {e}")
            # Fallback to basic conversation analysis
            result_data["conversation_summary"] = {
                "detected_domains": [],
                "mentioned_areas": [],
                "query_type": "unknown",
                "language": "hungarian",  # Default fallback
                "processing_source": "fallback_basic",
                "llm_used": False,
            }
            result_data["quick_analysis"] = {"error": str(e), "processing_time_ms": 0}

        memory_duration = (datetime.now() - memory_start).total_seconds() * 1000

        # Add enhanced pipeline stages to trace if available
        trace_id = state.get("trace_id")
        if trace_id:
            from app.services.core.workflow_tracer import workflow_tracer

            # Trace query rewriting stage
            if rewrite_result.method != "no_rewrite_needed":
                workflow_tracer.add_enhanced_pipeline_stage(
                    trace_id,
                    EnhancedPipelineStage(
                        stage_name="query_rewriting",
                        stage_type="transform",
                        input_count=1,
                        output_count=1,
                        duration_ms=rewrite_duration,
                        query_rewrite={
                            "original": rewrite_result.original_query,
                            "rewritten": rewrite_result.rewritten_query,
                            "method": rewrite_result.method,
                            "confidence": rewrite_result.confidence,
                            "coreferences_resolved": rewrite_result.coreferences_resolved,
                            "processing_time_ms": rewrite_result.processing_time_ms,
                        },
                    ),
                )

            # Trace quick pattern analysis stage
            workflow_tracer.add_enhanced_pipeline_stage(
                trace_id,
                EnhancedPipelineStage(
                    stage_name="quick_pattern_analysis",
                    stage_type="transform",
                    input_count=1,
                    output_count=len(
                        cast(Dict[str, Any], result_data.get("quick_analysis", {})).get(
                            "detected_domains", []
                        )
                    ),
                    duration_ms=cast(
                        Dict[str, Any], result_data.get("quick_analysis", {})
                    ).get("processing_time_ms", 0),
                    conversation_summary=result_data.get("quick_analysis"),
                ),
            )

            # Trace memory processing stage
            workflow_tracer.add_enhanced_pipeline_stage(
                trace_id,
                EnhancedPipelineStage(
                    stage_name="memory_processing",
                    stage_type="transform",
                    input_count=len(chat_messages) + 1,  # history + current query
                    output_count=1,
                    duration_ms=memory_duration,
                    memory_stage={
                        "cache_status": "hit" if cached_enrichment else "miss",
                        "background_enrichment_triggered": True,
                        "processing_source": result_data.get(
                            "conversation_summary", {}
                        ).get("processing_source", "unknown"),
                        "patterns_detected": len(
                            result_data.get("quick_analysis", {}).get(
                                "detected_domains", []
                            )
                        )
                        + len(
                            result_data.get("quick_analysis", {}).get(
                                "detected_areas", []
                            )
                        ),
                        "quick_analysis_time_ms": result_data.get(
                            "quick_analysis", {}
                        ).get("processing_time_ms", 0),
                        "cached_entity_boosts": (
                            len(cached_enrichment.entity_boost_weights)
                            if cached_enrichment
                            else 0
                        ),
                    },
                ),
            )

        return result_data

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
            optimal_k = 20
            confidence = 0.8
            reasoning = "Simple control action without area scope"
        # Temperature-specific queries get climate cluster priority first
        elif (
            any(
                word in query_lower
                for word in ["hány fok", "hőmérséklet", "temperature"]
            )
            and len(areas) == 1
        ):
            # "hány fok van a nappaliban?" → MACRO with climate cluster priority
            scope = QueryScope.MACRO
            optimal_k = 22
            confidence = 0.85
            reasoning = "Temperature query in specific area (climate cluster priority)"
        elif len(areas) == 1 and not any(
            word in query_lower for word in ["otthon", "house", "home"]
        ):
            # Single area mentioned → MACRO (prioritize area-specific queries)
            scope = QueryScope.MACRO
            optimal_k = 22
            confidence = 0.8
            reasoning = "Single area-specific query (takes priority over specific value patterns)"
        elif (
            any(word in query_lower for word in ["mennyi", "hány fok"])
            and not has_quantity_modifier
        ):
            # "hány fok van?" → MICRO (specific value query without area)
            scope = QueryScope.MICRO
            optimal_k = 20
            confidence = 0.7
            reasoning = "Specific value query without area context"
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


async def entity_retrieval_node(state: RAGState) -> Dict[str, Any]:
    """Entity retrieval with cluster-first logic, conversation memory, and vector fallback."""
    logger.info(
        "EntityRetrieval: Starting enhanced entity retrieval with conversation memory..."
    )

    try:
        from arango import ArangoClient
        from app.main import retrieve_entities_with_clusters
        from scripts.embedding_backends import get_backend
        import os

        # Initialize conversation memory service
        memory_service = ConversationMemoryService()
        session_id = state.get("session_id", "default")

        # Get conversation memory entities
        memory_entities = await memory_service.get_relevant_entities(
            conversation_id=session_id,
            current_query=state["user_query"],
            max_entities=5,
        )

        logger.info(
            f"Found {len(memory_entities)} relevant entities from conversation memory"
        )

        # Initialize database connection
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

        # Get scope configuration
        detected_scope = state.get("detected_scope")
        optimal_k = state.get("optimal_k", 15) or 15

        # Define cluster types based on scope
        if detected_scope:
            scope_value = (
                detected_scope.value
                if hasattr(detected_scope, "value")
                else str(detected_scope)
            )
            # Enhanced cluster type selection based on query context
            scope_reasoning = cast(str, state.get("scope_reasoning", ""))
            if scope_value == "micro":
                cluster_types = ["specific", "device"]
            elif scope_value == "macro":
                if "climate cluster priority" in scope_reasoning:
                    # Temperature queries prioritize climate cluster
                    cluster_types = ["climate", "area", "domain"]
                else:
                    cluster_types = ["area", "domain", "specific"]
            else:  # overview
                cluster_types = ["overview", "area", "domain"]

        # Create scope configuration object
        class ScopeConfig:
            def __init__(self, threshold: float = 0.7):
                self.threshold = threshold

        scope_config = ScopeConfig()

        # Enhanced conversation context with memory entities
        conversation_context = (state.get("conversation_context") or {}).copy()
        if memory_entities:
            # Add memory entity areas and domains to conversation context
            memory_areas = {e.get("area") for e in memory_entities if e.get("area")}
            memory_domains = {
                e.get("domain") for e in memory_entities if e.get("domain")
            }

            existing_areas = set(conversation_context.get("areas_mentioned", []))
            existing_domains = set(conversation_context.get("domains_mentioned", []))

            conversation_context["areas_mentioned"] = list(
                existing_areas | memory_areas
            )
            conversation_context["domains_mentioned"] = list(
                existing_domains | memory_domains
            )

            logger.info(
                f"Enhanced context with memory: areas={memory_areas}, domains={memory_domains}"
            )

        logger.info(
            f"Retrieving entities: scope={detected_scope}, k={optimal_k}, "
            f"cluster_types={cluster_types}, memory_boost={len(memory_entities)}"
        )

        # Call the enhanced entity retrieval function
        retrieved_entities = retrieve_entities_with_clusters(
            db=db,
            q_vec=query_vector,
            q_text=state["user_query"],
            scope_config=scope_config,
            cluster_types=cluster_types,
            k=optimal_k,
            conversation_context=conversation_context,
        )

        # Enhanced conversation memory boosting with better integration
        memory_boosted_count = 0
        if memory_entities:
            memory_entity_ids = {e["entity_id"] for e in memory_entities}
            memory_data = {e["entity_id"]: e for e in memory_entities}

            # First pass: boost existing entities
            for entity in retrieved_entities:
                entity_id = entity.get("entity_id")
                if entity_id in memory_entity_ids:
                    memory_info = memory_data[entity_id]
                    boost_weight = memory_info["boost_weight"]
                    memory_relevance = memory_info.get("memory_relevance", 1.0)

                    # Enhanced boosting formula
                    original_score = entity.get("_score", 0.0)
                    boosted_score = (
                        original_score * boost_weight * (1.0 + memory_relevance * 0.5)
                    )

                    entity["_score"] = boosted_score
                    entity["_memory_boosted"] = True
                    entity["_memory_boost"] = boost_weight
                    entity["_memory_relevance"] = memory_relevance
                    memory_boosted_count += 1
                    logger.debug(
                        f"Boosted entity {entity_id}: {original_score:.3f} -> {boosted_score:.3f} (boost={boost_weight:.2f}, relevance={memory_relevance:.2f})"
                    )

            # Second pass: add highly relevant memory entities not found in search
            entity_ids_in_results = {e.get("entity_id") for e in retrieved_entities}
            for memory_entity in memory_entities:
                if (
                    memory_entity["entity_id"] not in entity_ids_in_results
                    and memory_entity.get("memory_relevance", 0) > 1.5
                ):  # High relevance threshold

                    # Create a synthetic entity from memory
                    synthetic_entity = {
                        "entity_id": memory_entity["entity_id"],
                        "area_name": memory_entity.get("area"),
                        "domain": memory_entity.get("domain"),
                        "_score": memory_entity["relevance_score"]
                        * memory_entity["boost_weight"],
                        "_memory_boosted": True,
                        "_memory_boost": memory_entity["boost_weight"],
                        "_memory_relevance": memory_entity["memory_relevance"],
                        "_synthetic_from_memory": True,
                        "state": "unknown",  # Default state for synthetic entities
                        "attributes": {},
                    }
                    retrieved_entities.append(synthetic_entity)
                    memory_boosted_count += 1
                    logger.info(
                        f"Added synthetic entity from memory: {memory_entity['entity_id']} (relevance={memory_entity['memory_relevance']:.2f})"
                    )

        # Separate cluster entities from regular entities
        cluster_entities = []
        regular_entities = []

        for entity in retrieved_entities:
            if entity.get("_cluster_context"):
                cluster_entities.append(entity)
            else:
                regular_entities.append(entity)

        # Store current entities in conversation memory for future queries
        await memory_service.store_conversation_memory(
            conversation_id=session_id,
            entities=retrieved_entities[:10],  # Store top 10 entities
            areas_mentioned=set(conversation_context.get("areas_mentioned", [])),
            domains_mentioned=set(conversation_context.get("domains_mentioned", [])),
            query_context=f"Query: {state['user_query']}",
            conversation_summary=cast(
                Optional[Dict[str, Any]], state.get("conversation_summary")
            ),  # Pass the summary
        )

        logger.info(
            f"Retrieved {len(retrieved_entities)} entities: "
            f"{len(cluster_entities)} from clusters, "
            f"{len(regular_entities)} from vector search, "
            f"{memory_boosted_count} memory boosted"
        )

        # Add enhanced pipeline stages to trace if available
        trace_id = state.get("trace_id")
        if trace_id:
            from app.services.core.workflow_tracer import workflow_tracer

            # Trace cluster search stage (if any cluster entities found)
            if cluster_entities:
                workflow_tracer.add_enhanced_pipeline_stage(
                    trace_id,
                    EnhancedPipelineStage(
                        stage_name="cluster_search",
                        stage_type="search",
                        input_count=1,  # query
                        output_count=len(cluster_entities),
                        duration_ms=50.0,  # estimate, since we don't time individual stages here
                        cluster_search={
                            "cluster_types": cluster_types,
                            "cluster_count": len(cluster_entities),
                            "scope": (
                                detected_scope.value
                                if detected_scope and hasattr(detected_scope, "value")
                                else str(detected_scope) if detected_scope else None
                            ),
                            "optimal_k": optimal_k,
                        },
                    ),
                )

            # Trace vector search stage
            workflow_tracer.add_enhanced_pipeline_stage(
                trace_id,
                EnhancedPipelineStage(
                    stage_name="vector_search",
                    stage_type="search",
                    input_count=1,  # query vector
                    output_count=len(retrieved_entities),
                    duration_ms=100.0,  # estimate
                    vector_search={
                        "backend": backend_name,
                        "vector_dimension": len(query_vector),
                        "total_entities": len(retrieved_entities),
                        "k_value": optimal_k,
                    },
                ),
            )

            # Trace memory boost stage (if any memory entities found)
            if memory_entities:
                workflow_tracer.add_enhanced_pipeline_stage(
                    trace_id,
                    EnhancedPipelineStage(
                        stage_name="memory_boost",
                        stage_type="boost",
                        input_count=len(retrieved_entities),
                        output_count=len(retrieved_entities),
                        duration_ms=25.0,  # estimate
                        memory_boost={
                            "memory_entities_count": len(memory_entities),
                            "boosted_entities": memory_boosted_count,
                            "session_id": session_id,
                            "conversation_turn": state.get("conversation_history", []),
                        },
                    ),
                )

        # Update async memory with successful retrieval
        try:
            from app.services.conversation.conversation_memory import (
                AsyncConversationMemory,
            )

            async_memory = AsyncConversationMemory(memory_service)
            await async_memory.process_turn(
                session_id=session_id,
                query=state["user_query"],
                retrieved_entities=retrieved_entities[:10],  # Top 10 for learning
                success_feedback=1.0,  # Assume successful retrieval
            )
            logger.debug(f"Updated async memory for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to update async memory: {e}")

        return {
            "retrieved_entities": retrieved_entities,
            "cluster_entities": cluster_entities,
            "memory_entities": memory_entities,
        }

    except Exception as e:
        logger.error(f"Error in entity retrieval: {e}", exc_info=True)
        return {
            "retrieved_entities": [],
            "cluster_entities": [],
            "errors": state.get("errors", []) + [f"Entity retrieval failed: {str(e)}"],
        }


async def context_formatting_node(state: RAGState) -> Dict[str, Any]:
    """Context formatting with intelligent formatter selection."""
    logger.info("ContextFormatting: Starting context formatting...")

    try:
        from app.services.rag.entity_reranker import entity_reranker

        retrieved_entities = state.get("retrieved_entities", [])

        if not retrieved_entities:
            logger.warning("No entities to format")
            return {
                "formatted_context": "You are a Home Assistant agent.\n\nNo relevant entities found.",
                "formatter_type": "empty",
            }

        # Use actual entity reranker with area boosting
        conversation_history = state.get("conversation_history", [])
        user_query = state.get("user_query", "")
        session_id = state.get("session_id")

        logger.info(
            f"🔄 ContextFormatting INPUT: {len(retrieved_entities)} entities, top: {retrieved_entities[0].get('entity_id', 'unknown') if retrieved_entities else 'none'}"
        )

        # Actually call the entity reranker to apply area/domain boosting
        # Convert conversation history to ChatMessage objects
        chat_history = (
            [
                ChatMessage(
                    role=msg.get("role", "user"), content=str(msg.get("content", ""))
                )
                for msg in conversation_history
            ]
            if conversation_history
            else None
        )

        entity_scores = entity_reranker.rank_entities(
            entities=retrieved_entities,
            query=user_query,
            conversation_history=chat_history,
            conversation_id=session_id,
            k=len(retrieved_entities),  # Don't limit here, we want all scored entities
        )

        # ===== MULTI-STAGE FILTERING =====
        # Stage 1: Filter to reasonable size based on original optimal_k + scope
        optimal_k = state.get("optimal_k", 15) or 15
        detected_scope = state.get("detected_scope")

        # Calculate target entity count based on scope and optimal_k
        if detected_scope:
            scope_value = (
                detected_scope.value
                if hasattr(detected_scope, "value")
                else str(detected_scope)
            )
            if scope_value == "micro":
                target_entities = min(
                    8, len(entity_scores)
                )  # Tight filtering for specific queries
            elif scope_value == "macro":
                target_entities = min(optimal_k, len(entity_scores))  # Use original k
            else:  # overview
                target_entities = min(
                    optimal_k + 8, len(entity_scores)
                )  # Allow more for house-wide
        else:
            target_entities = min(optimal_k, len(entity_scores))  # Default fallback

        # Apply score-based filtering with minimum threshold
        min_score_threshold = (
            0.2  # Restored original threshold with proper multilingual model
        )
        filtered_entities = [
            es for es in entity_scores if es.final_score > min_score_threshold
        ][:target_entities]

        logger.info(
            f"🎯 Multi-stage filtering: {len(entity_scores)} -> {len(filtered_entities)} entities (target: {target_entities}, scope: {scope_value if detected_scope else 'unknown'})"
        )

        # Stage 2: Determine primary vs related entities from filtered pool
        primary_entities: List[Any] = []
        related_entities: List[Any] = []

        max_primary = min(
            6, len(filtered_entities) // 2
        )  # At most half should be primary, max 6

        for i, es in enumerate(filtered_entities):
            has_cluster_context = es.entity.get("_cluster_context") is not None
            high_score = es.final_score > 0.7

            # Primary entity criteria: top entities with high scores or cluster context
            if len(primary_entities) < max_primary and (
                (i < 4 and (has_cluster_context or high_score))
                or len(primary_entities) == 0  # Ensure at least one primary
            ):
                primary_entities.append(es)
            else:
                related_entities.append(es)

        # Extract entity IDs for tracking
        primary_entity_ids = [
            es.entity.get("entity_id", "unknown") for es in primary_entities[:3]
        ]
        related_entity_ids = [
            es.entity.get("entity_id", "unknown") for es in related_entities[:3]
        ]

        logger.info(
            f"📋 ContextFormatting OUTPUT: {len(primary_entities)} primary + {len(related_entities)} related entities"
        )

        logger.debug(
            f"Entity allocation details - Primary: {primary_entity_ids} | Related: {related_entity_ids}"
        )

        # Select appropriate formatter based on context
        formatter_type = entity_reranker._select_formatter(
            state["user_query"], primary_entities, related_entities
        )

        # Override formatter selection based on detected scope for optimization
        detected_scope = state.get("detected_scope")
        if detected_scope:
            scope_value = (
                detected_scope.value
                if hasattr(detected_scope, "value")
                else str(detected_scope)
            )
            if scope_value == "micro":
                # Micro queries: focus on primary entities, less context
                formatter_type = "compact"
            elif scope_value == "overview":
                # Overview queries: need structured summary
                formatter_type = (
                    "tldr"
                    if len(primary_entities) + len(related_entities) > 6
                    else "grouped_by_area"
                )

        logger.info(f"Selected formatter: {formatter_type}")

        # Generate formatted context using entity reranker's formatter
        # Combine all entities for the hierarchical prompt
        all_entity_scores = primary_entities + related_entities
        formatted_context = entity_reranker.create_hierarchical_system_prompt(
            ranked_entities=all_entity_scores,
            query=state["user_query"],
            max_primary=len(primary_entities),
            max_related=len(related_entities),
            force_formatter=formatter_type,
        )

        # Export ranking factors for debug visibility
        enhanced_entities = []
        for es in entity_scores:
            enhanced_entity = es.entity.copy()
            enhanced_entity["_ranking_factors"] = es.ranking_factors
            enhanced_entity["_score"] = es.final_score
            enhanced_entities.append(enhanced_entity)

        # Add enhanced pipeline stages to trace if available
        trace_id = state.get("trace_id")
        if trace_id:
            from app.services.core.workflow_tracer import workflow_tracer

            # Trace reranking stage
            workflow_tracer.add_enhanced_pipeline_stage(
                trace_id,
                EnhancedPipelineStage(
                    stage_name="reranking",
                    stage_type="rank",
                    input_count=len(retrieved_entities),
                    output_count=len(entity_scores),
                    duration_ms=150.0,  # estimate for reranking time
                    reranking={
                        "algorithm": "entity_reranker",
                        "score_range": {
                            "min": (
                                min(es.final_score for es in entity_scores)
                                if entity_scores
                                else 0.0
                            ),
                            "max": (
                                max(es.final_score for es in entity_scores)
                                if entity_scores
                                else 0.0
                            ),
                        },
                        "primary_count": len(primary_entities),
                        "related_count": len(related_entities),
                        "target_entities": target_entities,
                        "filtered_entities": len(filtered_entities),
                        "formatter_selected": formatter_type,
                    },
                ),
            )

            # Trace final selection stage
            workflow_tracer.add_enhanced_pipeline_stage(
                trace_id,
                EnhancedPipelineStage(
                    stage_name="final_selection",
                    stage_type="filter",
                    input_count=len(filtered_entities),
                    output_count=len(all_entity_scores),
                    duration_ms=50.0,  # estimate for final selection
                    reranking={
                        "context_length": len(formatted_context),
                        "formatter_type": formatter_type,
                        "primary_entities": primary_entity_ids,
                        "related_entities": related_entity_ids,
                        "scope": (
                            detected_scope.value
                            if detected_scope and hasattr(detected_scope, "value")
                            else str(detected_scope) if detected_scope else None
                        ),
                    },
                ),
            )

        return {
            "formatted_context": formatted_context,
            "formatter_type": formatter_type,
            "retrieved_entities": enhanced_entities,  # Enhanced with ranking factors
        }

    except Exception as e:
        logger.error(f"Error in context formatting: {e}", exc_info=True)
        return {
            "formatted_context": f"You are a Home Assistant agent.\n\nError formatting context: {str(e)}",
            "formatter_type": "error",
            "errors": state.get("errors", [])
            + [f"Context formatting failed: {str(e)}"],
        }
