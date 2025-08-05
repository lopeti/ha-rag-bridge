"""
Entity reranker service using cross-encoder models for conversation-aware entity prioritization.
Integrates with conversation analyzer to provide context-aware entity ranking.
"""

import time
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from cachetools import TTLCache

from ha_rag_bridge.logging import get_logger
from app.schemas import ChatMessage
from app.services.conversation_analyzer import (
    conversation_analyzer,
    ConversationContext,
)

logger = get_logger(__name__)


@dataclass
class EntityScore:
    """Entity with its relevance score and ranking factors."""

    entity: Dict[str, Any]
    base_score: float
    context_boost: float
    final_score: float
    ranking_factors: Dict[str, float]


class EntityReranker:
    """
    Cross-encoder based entity reranker for conversation-aware prioritization.

    Uses Hugging Face cross-encoder models to score entity relevance based on:
    - Query-entity semantic similarity
    - Conversation context
    - Area/domain relevance boosts
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initialize the entity reranker.

        Args:
            model_name: Cross-encoder model to use for scoring
        """
        self.model_name = model_name
        self._model = None
        self._tokenizer = None

        # Performance optimizations - TTL cache for cross-encoder scores
        self._score_cache = TTLCache(maxsize=1000, ttl=300)  # 5 minute TTL
        self._context_cache = TTLCache(maxsize=500, ttl=300)

        self._load_model()

    def _load_model(self):
        """Load the cross-encoder model with lazy initialization."""
        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"Loading cross-encoder model: {self.model_name}")
            start_time = time.time()

            # Load model on CPU for better VM compatibility
            self._model = CrossEncoder(self.model_name, device="cpu")

            load_time = time.time() - start_time
            logger.info(f"Cross-encoder model loaded in {load_time:.2f}s")

        except Exception as exc:
            logger.error(f"Failed to load cross-encoder model: {exc}")
            self._model = None

    def rank_entities(
        self,
        entities: List[Dict[str, Any]],
        query: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        conversation_id: Optional[str] = None,
        k: int = 10,
    ) -> List[EntityScore]:
        """
        Rank entities based on query relevance and conversation context.

        Args:
            entities: List of entity documents from ArangoDB
            query: User query text
            conversation_history: Previous conversation messages
            conversation_id: Conversation identifier
            k: Number of top entities to return

        Returns:
            List of EntityScore objects sorted by relevance
        """
        if not entities:
            return []

        logger.debug(f"Ranking {len(entities)} entities for query: {query}")

        # Analyze conversation context
        context = conversation_analyzer.analyze_conversation(
            query, conversation_history
        )

        # Score all entities
        entity_scores = []
        for entity in entities:
            score = self._score_entity(entity, query, context)
            entity_scores.append(score)

        # Sort by final score and return top k
        entity_scores.sort(key=lambda x: x.final_score, reverse=True)
        top_entities = entity_scores[:k]

        # Enhanced logging with context details
        if top_entities:
            top_entity = top_entities[0]
            logger.info(
                "Entity reranking completed successfully",
                query=query,
                areas_detected=list(context.areas_mentioned),
                domains_detected=list(context.domains_mentioned),
                device_classes_detected=list(context.device_classes_mentioned),
                intent=context.intent,
                is_follow_up=context.is_follow_up,
                top_entity_id=top_entity.entity.get("entity_id"),
                top_entity_area=top_entity.entity.get("area"),
                top_entity_score=round(top_entity.final_score, 3),
                top_entity_base_score=round(top_entity.base_score, 3),
                top_entity_context_boost=round(top_entity.context_boost, 3),
                ranking_factors=top_entity.ranking_factors,
                total_entities_ranked=len(top_entities),
            )

        return top_entities

    def _score_entity(
        self, entity: Dict[str, Any], query: str, context: ConversationContext
    ) -> EntityScore:
        """
        Score a single entity based on query relevance and context.

        Args:
            entity: Entity document from ArangoDB
            query: User query
            context: Analyzed conversation context

        Returns:
            EntityScore with detailed scoring information
        """
        # Get base semantic similarity score
        base_score = self._get_semantic_score(entity, query)

        # Calculate context boost factors
        ranking_factors = self._calculate_ranking_factors(entity, context)
        context_boost = sum(ranking_factors.values())

        # Calculate final score - additive instead of multiplicative to handle zero base scores
        final_score = base_score + context_boost

        return EntityScore(
            entity=entity,
            base_score=base_score,
            context_boost=context_boost,
            final_score=final_score,
            ranking_factors=ranking_factors,
        )

    def _get_semantic_score(self, entity: Dict[str, Any], query: str) -> float:
        """
        Get semantic similarity score using cross-encoder with caching.

        Args:
            entity: Entity document
            query: User query

        Returns:
            Semantic similarity score (0.0 to 1.0)
        """
        if not self._model:
            # Fallback to simple text matching if model failed to load
            return self._fallback_text_score(entity, query)

        try:
            # Create entity description for cross-encoder
            entity_text = self._create_entity_description(entity)

            # Create cache key from query and entity text
            cache_key = hashlib.md5(f"{query}:{entity_text}".encode()).hexdigest()

            # Check cache first
            if cache_key in self._score_cache:
                return self._score_cache[cache_key]

            # Get cross-encoder score
            score = self._model.predict([(query, entity_text)])

            # Normalize score to 0-1 range (cross-encoder can return negative values)
            normalized_score = max(0.0, min(1.0, (score + 1.0) / 2.0))
            normalized_score = float(normalized_score)

            # Cache the result
            self._score_cache[cache_key] = normalized_score

            return normalized_score

        except Exception as exc:
            logger.warning(f"Cross-encoder scoring failed: {exc}")
            return self._fallback_text_score(entity, query)

    def _create_entity_description(self, entity: Dict[str, Any]) -> str:
        """
        Create a textual description of the entity for cross-encoder scoring.

        Args:
            entity: Entity document

        Returns:
            Human-readable entity description
        """
        parts = []

        # Entity ID and name
        entity_id = entity.get("entity_id", "")
        if entity_id:
            parts.append(entity_id)

        # Friendly name
        friendly_name = entity.get("friendly_name", "")
        if friendly_name:
            parts.append(friendly_name)

        # Area
        area = entity.get("area", "")
        if area:
            parts.append(f"terület: {area}")

        # Domain and device class
        domain = entity.get("domain", "")
        device_class = entity.get("device_class", "")
        if domain:
            if device_class:
                parts.append(f"{domain} {device_class}")
            else:
                parts.append(domain)

        # Text content (if available)
        text = entity.get("text", "")
        if text:
            parts.append(text)

        return " | ".join(parts)

    def _fallback_text_score(self, entity: Dict[str, Any], query: str) -> float:
        """
        Fallback text matching when cross-encoder is not available.

        Args:
            entity: Entity document
            query: User query

        Returns:
            Simple text similarity score
        """
        entity_text = self._create_entity_description(entity).lower()
        query_lower = query.lower()

        # Simple keyword matching
        query_words = query_lower.split()
        matches = sum(1 for word in query_words if word in entity_text)

        if not query_words:
            return 0.5

        return min(1.0, matches / len(query_words))

    def _calculate_ranking_factors(
        self, entity: Dict[str, Any], context: ConversationContext
    ) -> Dict[str, float]:
        """
        Calculate boost factors based on conversation context.

        Args:
            entity: Entity document
            context: Conversation context

        Returns:
            Dictionary of ranking factors and their boost values
        """
        factors = {}

        # Area relevance boost - handle None values safely
        entity_area = entity.get("area") or ""
        if entity_area:
            entity_area = entity_area.lower()
            area_boosts = conversation_analyzer.get_area_boost_factors(context)
            for area, boost in area_boosts.items():
                # Exact match gets highest boost
                if entity_area == area.lower():
                    factors[f"area_{area}"] = boost - 1.0  # Convert to boost factor
                # Partial match gets lower boost (only if no exact match found)
                elif area in entity_area or entity_area in area:
                    if f"area_{area}" not in factors:  # Don't override exact match
                        factors[f"area_{area}"] = (
                            boost - 1.0
                        ) * 0.5  # Reduced boost for partial match

        # Domain relevance boost - handle None values safely
        entity_domain = entity.get("domain") or ""
        if entity_domain:
            domain_boosts = conversation_analyzer.get_domain_boost_factors(context)
            domain_key = f"domain:{entity_domain}"
            if domain_key in domain_boosts:
                factors[f"domain_{entity_domain}"] = domain_boosts[domain_key] - 1.0

        # Device class relevance boost - handle None values safely
        entity_device_class = entity.get("device_class") or ""
        if entity_device_class:
            domain_boosts = conversation_analyzer.get_domain_boost_factors(context)
            class_key = f"device_class:{entity_device_class}"
            if class_key in domain_boosts:
                factors[f"device_class_{entity_device_class}"] = (
                    domain_boosts[class_key] - 1.0
                )

        # Previous entity mention boost - handle None values safely
        entity_id = entity.get("entity_id") or ""
        if entity_id and entity_id in context.previous_entities:
            factors["previous_mention"] = 0.3

        # Intent-specific boosts
        if context.intent == "control":
            # Boost controllable entities for control intents
            if entity_domain in ["light", "switch", "climate", "cover", "lock"]:
                factors["controllable"] = 0.2
        elif context.intent == "read":
            # Boost sensors for read intents
            if entity_domain == "sensor":
                factors["readable"] = 0.1

        return factors

    def create_hierarchical_system_prompt(
        self,
        ranked_entities: List[EntityScore],
        query: str,
        max_primary: int = 1,
        max_related: int = 3,
    ) -> str:
        """
        Create hierarchical system prompt with primary and related entities.

        Args:
            ranked_entities: List of ranked entities
            query: User query
            max_primary: Maximum number of primary entities
            max_related: Maximum number of related entities

        Returns:
            Formatted system prompt string
        """
        if not ranked_entities:
            return "You are a Home Assistant agent.\n"

        primary_entities = ranked_entities[:max_primary]
        related_entities = ranked_entities[max_primary : max_primary + max_related]

        prompt_parts = ["You are a Home Assistant agent.\n"]

        # Primary entities section
        if primary_entities:
            if len(primary_entities) == 1:
                entity = primary_entities[0].entity
                entity_id = entity.get("entity_id", "")
                area = entity.get("area", "")
                area_text = f" [{area}]" if area else ""

                prompt_parts.append(f"Primary entity: {entity_id}{area_text}")

                # Add current state for sensors
                if entity.get("domain") == "sensor":
                    from app.services.state_service import get_last_state

                    current_value = get_last_state(entity_id)
                    if current_value is not None:
                        prompt_parts.append(f"Current value: {current_value}")
            else:
                prompt_parts.append("Primary entities:")
                for score in primary_entities:
                    entity = score.entity
                    entity_id = entity.get("entity_id", "")
                    area = entity.get("area", "")
                    area_text = f" [{area}]" if area else ""

                    # Add current value for each primary sensor
                    if entity.get("domain") == "sensor":
                        from app.services.state_service import get_last_state

                        current_value = get_last_state(entity_id)
                        if current_value is not None:
                            prompt_parts.append(
                                f"- {entity_id}{area_text}: {current_value}"
                            )
                        else:
                            prompt_parts.append(f"- {entity_id}{area_text}")
                    else:
                        prompt_parts.append(f"- {entity_id}{area_text}")

        # Related entities section
        if related_entities:
            prompt_parts.append("\nRelated entities:")
            for score in related_entities:
                entity = score.entity
                entity_id = entity.get("entity_id", "")
                area = entity.get("area", "")
                area_text = f" [{area}]" if area else ""

                # Add current value for related sensors too
                if entity.get("domain") == "sensor":
                    from app.services.state_service import get_last_state

                    current_value = get_last_state(entity_id)
                    if current_value is not None:
                        prompt_parts.append(
                            f"- {entity_id}{area_text}: {current_value}"
                        )
                    else:
                        prompt_parts.append(f"- {entity_id}{area_text}")
                else:
                    prompt_parts.append(f"- {entity_id}{area_text}")

        # All domains for service catalog
        all_entities = primary_entities + related_entities
        domains = sorted(
            [
                domain
                for entity in all_entities
                if (domain := entity.entity.get("domain")) is not None
            ]
        )
        if domains:
            prompt_parts.append(f"\nRelevant domains: {','.join(domains)}")

        return "\n".join(prompt_parts) + "\n"


# Global instance for reuse
entity_reranker = EntityReranker()
