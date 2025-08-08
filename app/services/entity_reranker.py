"""
Entity reranker service using cross-encoder models for conversation-aware entity prioritization.
Integrates with conversation analyzer to provide context-aware entity ranking.
"""

import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from cachetools import TTLCache  # type: ignore

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

        # Sort by final score
        entity_scores.sort(key=lambda x: x.final_score, reverse=True)
        
        # Multi-stage filtering: prefer active entities within top k*2 candidates
        if len(entity_scores) > k:
            # Stage 1: Get top k*2 by relevance score
            candidate_pool = entity_scores[:min(len(entity_scores), k * 2)]
            
            # Stage 2: Separate active and inactive entities within candidate pool
            active_entities = [es for es in candidate_pool if es.ranking_factors.get("has_active_value", 0) > 0]
            inactive_entities = [es for es in candidate_pool if es.ranking_factors.get("has_active_value", 0) <= 0]
            
            # Stage 3: Prioritize active entities, fill remaining with best inactive
            top_entities = []
            
            # Fill with active entities first
            top_entities.extend(active_entities[:k])
            
            # Fill remaining slots with best inactive entities if needed
            remaining_slots = k - len(top_entities)
            if remaining_slots > 0:
                top_entities.extend(inactive_entities[:remaining_slots])
            
            logger.debug(
                f"Multi-stage filtering: {len(active_entities)} active, "
                f"{len(inactive_entities)} inactive from {len(candidate_pool)} candidates"
            )
        else:
            # Not enough entities for multi-stage filtering
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

        # Availability boost - strongly prefer entities with active state values
        if entity_domain == "sensor" and entity_id:
            from app.services.state_service import get_last_state

            try:
                current_value = get_last_state(entity_id)
                if current_value is not None:
                    factors["has_active_value"] = (
                        2.0  # Very strong boost for active sensors
                    )
                else:
                    factors["unavailable_penalty"] = (
                        -0.5  # Lighter penalty - still consider inactive sensors
                    )  # Penalize unavailable sensors but don't exclude them
            except Exception:
                pass  # Don't fail ranking on state service errors

        return factors

    def _create_human_readable_entity_name(self, entity: Dict[str, Any]) -> str:
        """
        Create a human-readable entity name with area information.

        Args:
            entity: Entity document

        Returns:
            Human-readable entity description
        """
        friendly_name = entity.get("friendly_name", "")
        area = entity.get("area", "")
        entity_id = entity.get("entity_id", "")

        # Extract aliases from text field if available
        text = entity.get("text", "")
        aliases = ""
        if "Aliases:" in text:
            aliases_part = text.split("Aliases:")[-1].strip()
            if aliases_part:
                aliases = f" ({aliases_part})"

        # Create readable name
        if friendly_name and friendly_name.lower() != "temperature":
            name = friendly_name
        else:
            # Use domain-specific naming
            domain = entity.get("domain", "")

            if domain == "sensor":
                if "temperature" in entity_id.lower():
                    name = "Hőmérséklet szenzor"
                elif "humidity" in entity_id.lower():
                    name = "Páratartalom szenzor"
                elif "pressure" in entity_id.lower():
                    name = "Légnyomás szenzor"
                else:
                    name = f"{friendly_name or 'Szenzor'}"
            elif domain == "light":
                name = "Világítás"
            elif domain == "switch":
                name = "Kapcsoló"
            else:
                name = friendly_name or entity_id

        # Add area information
        if area:
            area_name = area.replace("_", " ").title()
            name += f" ({area_name} területen)"

        # Add aliases if available
        name += aliases

        return name

    class SystemPromptFormatter:
        """Different formatting strategies for system prompts based on context"""

        @classmethod
        def compact_format(cls, primary_entities, related_entities, areas_info):
            """Ultra-compact format for token-limited contexts or many entities"""
            parts = ["You are a Home Assistant agent.\n"]

            if primary_entities:
                primary_strs = []
                for pe in primary_entities:
                    entity = pe.entity
                    name = cls._get_clean_name(entity)
                    area = entity.get("area", "")
                    value = cls._get_value_str(entity)
                    primary_strs.append(f"{name} [{area}]{value}")
                parts.append(f"Primary: {' | '.join(primary_strs)}")

            if related_entities:
                related_strs = []
                for re in related_entities:
                    entity = re.entity
                    name = cls._get_clean_name(entity)
                    area = entity.get("area", "")
                    value = cls._get_value_str(entity)
                    related_strs.append(f"{name} [{area}]{value}")
                parts.append(f"Related: {' | '.join(related_strs)}")

            if areas_info:
                area_strs = []
                for area, aliases in areas_info.items():
                    if aliases:
                        area_strs.append(f"{area} ({', '.join(aliases)})")
                    else:
                        area_strs.append(area)
                parts.append(f"Areas: {', '.join(area_strs)}")

            return "\n".join(parts)

        @classmethod
        def detailed_format(cls, primary_entities, related_entities, areas_info):
            """Standard detailed format"""
            parts = ["You are a Home Assistant agent.\n"]

            if primary_entities:
                if len(primary_entities) == 1:
                    parts.append("Primary entity:")
                else:
                    parts.append("Primary entities:")

                for pe in primary_entities:
                    entity = pe.entity
                    name = cls._get_clean_name(entity)
                    area = entity.get("area", "")
                    value = cls._get_value_str(entity)
                    parts.append(f"- {name} [{area}]{value}")

            if related_entities:
                parts.append("\nRelated entities:")
                for re in related_entities:
                    entity = re.entity
                    name = cls._get_clean_name(entity)
                    area = entity.get("area", "")
                    value = cls._get_value_str(entity)
                    parts.append(f"- {name} [{area}]{value}")

            if areas_info:
                parts.append("\nAreas:")
                for area, aliases in areas_info.items():
                    if aliases:
                        parts.append(f"- {area}: {', '.join(aliases)}")
                    else:
                        parts.append(f"- {area}")

            return "\n".join(parts)

        @classmethod
        def grouped_by_area_format(cls, primary_entities, related_entities, areas_info):
            """Group entities by area for spatial queries"""
            parts = ["You are a Home Assistant agent.\n"]
            parts.append("Entities by area:\n")

            # Group all entities by area
            area_groups = {}
            all_entities = primary_entities + related_entities

            for entity_score in all_entities:
                entity = entity_score.entity
                area = entity.get("area", "unknown")
                if area not in area_groups:
                    area_groups[area] = []

                name = cls._get_clean_name(entity)
                value = cls._get_value_str(entity)
                is_primary = entity_score in primary_entities
                prefix = "[P] " if is_primary else "[R] "
                area_groups[area].append(f"- {prefix}{name}{value}")

            for area, entities in area_groups.items():
                area_aliases = areas_info.get(area, [])
                if area_aliases:
                    parts.append(f"{area} ({', '.join(area_aliases)}):")
                else:
                    parts.append(f"{area}:")
                parts.extend(entities)
                parts.append("")  # Empty line between areas

            return "\n".join(parts).rstrip()

        @classmethod
        def tldr_format(cls, primary_entities, related_entities, areas_info):
            """Detailed format with TL;DR summary"""
            detailed = cls.detailed_format(
                primary_entities, related_entities, areas_info
            )

            # Generate TL;DR summary
            summary_parts = []

            # Count entities by area
            area_counts = {}
            all_entities = primary_entities + related_entities
            for entity_score in all_entities:
                area = entity_score.entity.get("area", "unknown")
                area_counts[area] = area_counts.get(area, 0) + 1

            # Create concise summary
            if area_counts:
                area_summaries = []
                for area, count in area_counts.items():
                    area_summaries.append(f"{area} ({count} entities)")
                summary_parts.append(f"Monitoring: {', '.join(area_summaries)}")

            if summary_parts:
                tldr = f"\nTL;DR: {' | '.join(summary_parts)}"
                return detailed + tldr

            return detailed

        @classmethod
        def _get_clean_name(cls, entity):
            """Get clean entity name without area repetition"""
            friendly_name = entity.get("friendly_name", "")
            entity_id = entity.get("entity_id", "")
            domain = entity.get("domain", "")
            device_class = entity.get("device_class", "")

            # Use friendly name if available and meaningful
            if friendly_name and friendly_name.lower() not in [
                "temperature",
                "humidity",
                "pressure",
            ]:
                return friendly_name

            # Generate descriptive name based on domain/device_class
            if domain == "sensor":
                if "temperature" in entity_id.lower() or device_class == "temperature":
                    return "Hőmérséklet"
                elif "humidity" in entity_id.lower() or device_class == "humidity":
                    return "Páratartalom"
                elif "pressure" in entity_id.lower() or device_class == "pressure":
                    return "Légnyomás"
                elif "motion" in entity_id.lower():
                    return "Mozgás"
                elif "door" in entity_id.lower():
                    return "Ajtó"
                elif "window" in entity_id.lower():
                    return "Ablak"
                else:
                    return friendly_name or "Szenzor"
            elif domain == "light":
                return "Világítás"
            elif domain == "switch":
                return "Kapcsoló"
            elif domain == "climate":
                return "Klíma"
            else:
                return friendly_name or entity_id

        @classmethod
        def _get_value_str(cls, entity):
            """Get formatted value string for entity"""
            from app.services.state_service import get_last_state

            if entity.get("domain") == "sensor":
                entity_id = entity.get("entity_id", "")
                current_value = get_last_state(entity_id)
                if current_value is not None:
                    return f": {current_value}"
            return ""

    def _categorize_entities(
        self,
        ranked_entities: List[EntityScore],
        query: str,
        max_primary: int,
        max_related: int,
    ) -> Tuple[List[EntityScore], List[EntityScore]]:
        """
        Intelligently categorize entities into primary and related based on
        score thresholds, area context, and device classes.

        Args:
            ranked_entities: List of ranked entities
            query: User query
            max_primary: Maximum primary entities
            max_related: Maximum related entities

        Returns:
            Tuple of (primary_entities, related_entities)
        """
        if not ranked_entities:
            return [], []

        # Get top score for normalization
        top_score = ranked_entities[0].final_score if ranked_entities else 0

        # Analyze query context
        from app.services.conversation_analyzer import conversation_analyzer

        context = conversation_analyzer.analyze_conversation(query)
        areas_mentioned = context.areas_mentioned
        device_classes_mentioned = context.device_classes_mentioned

        primary_entities: List[EntityScore] = []
        related_entities: List[EntityScore] = []

        # Track what we've seen to ensure diversity
        seen_device_classes: set[str] = set()
        seen_areas: set[str] = set()

        for entity_score in ranked_entities:
            entity = entity_score.entity
            score = entity_score.final_score
            entity_area = entity.get("area", "")
            device_class = entity.get("device_class", "")

            # Calculate if this should be primary based on multiple factors
            is_primary = False

            # Factor 1: High relevance score (relative to top score)
            score_threshold = max(0.3, top_score * 0.7) if top_score > 0 else 0.3
            high_score = score >= score_threshold

            # Factor 2: Matches area context perfectly
            perfect_area_match = entity_area in areas_mentioned

            # Factor 3: Matches device class context perfectly
            perfect_device_match = device_class in device_classes_mentioned

            # Factor 4: Is in same area as other primary entities (clustering)
            same_area_as_primary = any(
                pe.entity.get("area") == entity_area for pe in primary_entities
            )

            # Factor 5: Provides complementary information (different device classes)
            complementary_device = (
                device_class not in seen_device_classes
                and len(seen_device_classes)
                < 3  # Max 3 different device classes as primary
            )

            # Decision logic for primary entities
            if len(primary_entities) < max_primary:
                # First entity is always primary if it has decent score
                if not primary_entities and score > 0.1:
                    is_primary = True
                # Perfect matches are primary
                elif perfect_area_match and (perfect_device_match or high_score):
                    is_primary = True
                # High scoring entities in same area as existing primaries
                elif same_area_as_primary and high_score and complementary_device:
                    is_primary = True
                # High scoring entities with complementary device classes
                elif high_score and complementary_device and len(primary_entities) < 3:
                    is_primary = True

            if is_primary:
                primary_entities.append(entity_score)
                seen_device_classes.add(device_class)
                seen_areas.add(entity_area)
            elif len(related_entities) < max_related:
                related_entities.append(entity_score)

        logger.debug(
            f"Categorized {len(primary_entities)} primary and {len(related_entities)} related entities",
            primary_areas=list(seen_areas),
            primary_device_classes=list(seen_device_classes),
        )

        return primary_entities, related_entities

    def _select_formatter(
        self,
        query: str,
        primary_entities: List[EntityScore],
        related_entities: List[EntityScore],
    ) -> str:
        """Intelligently select the best formatter based on query and entity context"""
        from app.services.conversation_analyzer import conversation_analyzer

        context = conversation_analyzer.analyze_conversation(query)
        total_entities = len(primary_entities) + len(related_entities)
        areas_mentioned = context.areas_mentioned

        # Select formatter based on context
        if total_entities > 8:
            return "compact"
        elif len(areas_mentioned) > 2:
            return "tldr"
        elif len(areas_mentioned) == 1:
            return "grouped_by_area"
        else:
            return "detailed"

    def _collect_areas_info(self, entities: List[EntityScore]) -> Dict[str, List[str]]:
        """Collect area information and aliases from entities"""
        areas_info = {}

        for entity_score in entities:
            entity = entity_score.entity
            area = entity.get("area", "")
            if not area:
                continue

            if area not in areas_info:
                # Extract aliases from entity text if available
                text = entity.get("text", "")
                aliases = []
                if "Aliases:" in text:
                    aliases_part = text.split("Aliases:")[-1].strip()
                    if aliases_part:
                        aliases = [
                            alias.strip()
                            for alias in aliases_part.split()
                            if alias.strip()
                        ]
                areas_info[area] = aliases

        return areas_info

    def create_hierarchical_system_prompt(
        self,
        ranked_entities: List[EntityScore],
        query: str,
        max_primary: int = 7,  # Increased for more entities
        max_related: int = 8,  # Increased for more entities
        force_formatter: Optional[
            str
        ] = None,  # Force specific formatter based on query scope
    ) -> str:
        """
        Create hierarchical system prompt with multiple primary and related entities.
        Uses intelligent formatting based on query context and entity count.

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

        # Intelligently determine primary entities based on score thresholds and context
        primary_entities, related_entities = self._categorize_entities(
            ranked_entities, query, max_primary, max_related
        )

        # Collect areas information
        all_entities = primary_entities + related_entities
        areas_info = self._collect_areas_info(all_entities)

        # Select the best formatter (use force_formatter if provided)
        formatter_type = force_formatter or self._select_formatter(
            query, primary_entities, related_entities
        )

        # Apply the selected formatter
        if formatter_type == "compact":
            return self.SystemPromptFormatter.compact_format(
                primary_entities, related_entities, areas_info
            )
        elif formatter_type == "grouped_by_area":
            return self.SystemPromptFormatter.grouped_by_area_format(
                primary_entities, related_entities, areas_info
            )
        elif formatter_type == "tldr":
            return self.SystemPromptFormatter.tldr_format(
                primary_entities, related_entities, areas_info
            )
        else:
            return self.SystemPromptFormatter.detailed_format(
                primary_entities, related_entities, areas_info
            )


# Global instance for reuse
entity_reranker = EntityReranker()
