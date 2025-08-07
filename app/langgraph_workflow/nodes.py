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


async def entity_retrieval_node(state: RAGState) -> Dict[str, Any]:
    """Entity retrieval with cluster-first logic and vector fallback."""
    logger.info("EntityRetrieval: Starting cluster-first entity retrieval...")

    try:
        from arango import ArangoClient
        from app.main import retrieve_entities_with_clusters
        from scripts.embedding_backends import get_backend
        import os

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
        optimal_k = state.get("optimal_k", 15)

        # Define cluster types based on scope
        if detected_scope:
            scope_value = detected_scope.value if hasattr(detected_scope, "value") else str(detected_scope)
            if scope_value == "micro":
                cluster_types = ["specific", "device"]
            elif scope_value == "macro":
                cluster_types = ["area", "domain", "specific"]
            else:  # overview
                cluster_types = ["overview", "area", "domain"]
        else:
            cluster_types = ["specific", "area", "domain"]

        # Create scope configuration object
        class ScopeConfig:
            def __init__(self, threshold: float = 0.7):
                self.threshold = threshold

        scope_config = ScopeConfig()

        # Get conversation context for area/domain boosting
        conversation_context = state.get("conversation_context", {})

        logger.info(
            f"Retrieving entities: scope={detected_scope}, k={optimal_k}, "
            f"cluster_types={cluster_types}"
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

        # Separate cluster entities from regular entities
        cluster_entities = []
        regular_entities = []

        for entity in retrieved_entities:
            if entity.get("_cluster_context"):
                cluster_entities.append(entity)
            else:
                regular_entities.append(entity)

        logger.info(
            f"Retrieved {len(retrieved_entities)} entities: "
            f"{len(cluster_entities)} from clusters, "
            f"{len(regular_entities)} from vector search"
        )

        return {
            "retrieved_entities": retrieved_entities,
            "cluster_entities": cluster_entities,
        }

    except Exception as e:
        logger.error(f"Error in entity retrieval: {e}", exc_info=True)
        return {
            "retrieved_entities": [],
            "cluster_entities": [],
            "errors": state.get("errors", [])
            + [f"Entity retrieval failed: {str(e)}"],
        }


async def context_formatting_node(state: RAGState) -> Dict[str, Any]:
    """Context formatting with intelligent formatter selection."""
    logger.info("ContextFormatting: Starting context formatting...")

    try:
        from app.services.entity_reranker import entity_reranker
        from app.services.conversation_analyzer import conversation_analyzer
        
        retrieved_entities = state.get("retrieved_entities", [])
        conversation_context = state.get("conversation_context", {})
        
        if not retrieved_entities:
            logger.warning("No entities to format")
            return {
                "formatted_context": "You are a Home Assistant agent.\n\nNo relevant entities found.",
                "formatter_type": "empty",
            }

        # Convert retrieved entities to EntityScore format for compatibility
        entity_scores = []
        for entity in retrieved_entities:
            # Create a mock EntityScore-like object that has the .entity attribute
            class MockEntityScore:
                def __init__(self, entity_data):
                    self.entity = entity_data
                    self.base_score = entity_data.get("_score", 0.0)
                    self.context_boost = entity_data.get("_cluster_context", {}).get("context_boost", 0.0)
                    self.final_score = self.base_score + self.context_boost
                    self.ranking_factors = {}
            
            entity_scores.append(MockEntityScore(entity))

        # Sort by final score
        entity_scores.sort(key=lambda x: x.final_score, reverse=True)

        # Determine primary vs related entities
        # Primary: top 4 entities with highest scores or cluster context
        primary_entities = []
        related_entities = []
        
        for i, es in enumerate(entity_scores):
            has_cluster_context = es.entity.get("_cluster_context") is not None
            high_score = es.final_score > 0.7
            
            if (i < 4 and (has_cluster_context or high_score)) or len(primary_entities) == 0:
                primary_entities.append(es)
            else:
                related_entities.append(es)

        logger.info(
            f"Context formatting: {len(primary_entities)} primary, "
            f"{len(related_entities)} related entities"
        )

        # Select appropriate formatter based on context
        formatter_type = entity_reranker._select_formatter(
            state["user_query"], primary_entities, related_entities
        )

        # Override formatter selection based on detected scope for optimization
        detected_scope = state.get("detected_scope")
        if detected_scope:
            scope_value = detected_scope.value if hasattr(detected_scope, "value") else str(detected_scope)
            if scope_value == "micro":
                # Micro queries: focus on primary entities, less context
                formatter_type = "compact"
            elif scope_value == "overview":
                # Overview queries: need structured summary
                formatter_type = "tldr" if len(primary_entities) + len(related_entities) > 6 else "grouped_by_area"

        logger.info(f"Selected formatter: {formatter_type}")

        # Generate formatted context using entity reranker's formatter
        # Combine all entities for the hierarchical prompt
        all_entity_scores = primary_entities + related_entities
        formatted_context = entity_reranker.create_hierarchical_system_prompt(
            ranked_entities=all_entity_scores,
            query=state["user_query"],
            max_primary=len(primary_entities),
            max_related=len(related_entities),
            force_formatter=formatter_type
        )

        return {
            "formatted_context": formatted_context,
            "formatter_type": formatter_type,
        }

    except Exception as e:
        logger.error(f"Error in context formatting: {e}", exc_info=True)
        return {
            "formatted_context": f"You are a Home Assistant agent.\n\nError formatting context: {str(e)}",
            "formatter_type": "error",
            "errors": state.get("errors", [])
            + [f"Context formatting failed: {str(e)}"],
        }
