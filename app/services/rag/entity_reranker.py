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
from ha_rag_bridge.config import get_settings
from app.schemas import ChatMessage
from app.services.conversation.conversation_analyzer import (
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

    # Cross-encoder debug information
    cross_encoder_raw_score: Optional[float] = None
    cross_encoder_input_text: Optional[str] = None
    cross_encoder_cache_hit: Optional[bool] = None
    cross_encoder_inference_ms: Optional[float] = None
    used_fallback_matching: Optional[bool] = None


class EntityReranker:
    """
    Cross-encoder based entity reranker for conversation-aware prioritization.

    Uses Hugging Face cross-encoder models to score entity relevance based on:
    - Query-entity semantic similarity
    - Conversation context
    - Area/domain relevance boosts
    """

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the entity reranker.

        Args:
            model_name: Cross-encoder model to use for scoring (uses config if None)
        """
        self.settings = get_settings()
        self.model_name = model_name or self.settings.cross_encoder_model
        self._model = None
        self._tokenizer = None

        # Performance optimizations - TTL cache for cross-encoder scores
        self._score_cache = TTLCache(
            maxsize=self.settings.entity_score_cache_maxsize,
            ttl=self.settings.entity_reranker_cache_ttl,
        )
        self._context_cache = TTLCache(
            maxsize=self.settings.entity_context_cache_maxsize,
            ttl=self.settings.entity_reranker_cache_ttl,
        )

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
            candidate_pool = entity_scores[: min(len(entity_scores), k * 2)]

            # Stage 2: Separate active and inactive entities within candidate pool
            # An entity is considered inactive if it has either unavailable_penalty or no has_active_value
            active_entities = [
                es
                for es in candidate_pool
                if (
                    es.ranking_factors.get("has_active_value", 0) > 0
                    and es.ranking_factors.get("unavailable_penalty", 0) == 0
                )
            ]
            inactive_entities = [
                es
                for es in candidate_pool
                if (
                    es.ranking_factors.get("has_active_value", 0) <= 0
                    or es.ranking_factors.get("unavailable_penalty", 0) < 0
                )
            ]

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

        # Entity Proof System: Comprehensive tracking log
        if top_entities:
            top_entity = top_entities[0]
            top_5_entities = top_entities[:5]

            # Primary tracking log - single line with essential data
            logger.info(
                "✅ Entity reranking SUCCESSFUL",
                query=query,
                top_entity=top_entity.entity.get("entity_id"),
                top_score=round(top_entity.final_score, 3),
                ranked_count=len(top_entities),
                system_prompt_type="hierarchical",
            )

            # Detailed tracking for debugging (only top 5 entities)
            logger.debug(
                "Entity tracking details",
                query=query,
                areas_detected=list(context.areas_mentioned),
                domains_detected=list(context.domains_mentioned),
                device_classes_detected=list(context.device_classes_mentioned),
                intent=context.intent,
                is_follow_up=context.is_follow_up,
                top_5_entities=[
                    {
                        "entity_id": es.entity.get("entity_id"),
                        "score": round(es.final_score, 3),
                        "area": es.entity.get("area"),
                        "state": es.entity.get("state", "unknown"),
                    }
                    for es in top_5_entities
                ],
                top_entity_ranking_factors=top_entity.ranking_factors,
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
        # Get base semantic similarity score with debug info
        score_result = self._get_semantic_score_with_debug(entity, query)
        base_score = score_result["score"]

        # Calculate context boost factors
        ranking_factors = self._calculate_ranking_factors(entity, context)
        context_boost = sum(ranking_factors.values())

        # Calculate final score with enhanced area boosting when areas are mentioned
        areas_mentioned = (
            context.areas_mentioned if hasattr(context, "areas_mentioned") else set()
        )

        # If areas are explicitly mentioned and this entity matches, apply multiplicative area boost
        entity_area = entity.get("area") or ""
        area_match = False
        if entity_area and areas_mentioned:
            entity_area_lower = entity_area.lower()
            area_match = any(
                area.lower() == entity_area_lower or area.lower() in entity_area_lower
                for area in areas_mentioned
            )

        if area_match and base_score > 0:
            # For area matches with explicit mentions, use multiplicative boosting to compete with memory
            area_multiplier = 1.0 + (
                context_boost * 0.5
            )  # Convert additive to multiplicative boost
            final_score = base_score * area_multiplier
        else:
            # Default additive boosting for other cases
            final_score = base_score + context_boost

        return EntityScore(
            entity=entity,
            base_score=base_score,
            context_boost=context_boost,
            final_score=final_score,
            ranking_factors=ranking_factors,
            cross_encoder_raw_score=score_result.get("raw_score"),
            cross_encoder_input_text=score_result.get("input_text"),
            cross_encoder_cache_hit=score_result.get("cache_hit"),
            cross_encoder_inference_ms=score_result.get("inference_ms"),
            used_fallback_matching=score_result.get("used_fallback", False),
        )

    def _get_semantic_score_with_debug(
        self, entity: Dict[str, Any], query: str
    ) -> Dict[str, Any]:
        """
        Get semantic similarity score with detailed debug information.

        Args:
            entity: Entity document
            query: User query

        Returns:
            Dictionary with score and debug information
        """
        if not self._model:
            # Fallback to simple text matching if model failed to load
            fallback_score = self._fallback_text_score(entity, query)
            return {
                "score": fallback_score,
                "raw_score": None,
                "input_text": None,
                "cache_hit": False,
                "inference_ms": 0.0,
                "used_fallback": True,
            }

        try:
            # Create entity description for cross-encoder
            entity_text = self._create_entity_description(entity)

            # Create cache key from query and entity text
            cache_key = hashlib.md5(f"{query}:{entity_text}".encode()).hexdigest()

            # Check cache first
            cache_hit = cache_key in self._score_cache
            if cache_hit:
                normalized_score = self._score_cache[cache_key]
                return {
                    "score": normalized_score,
                    "raw_score": None,  # Raw score not stored in cache
                    "input_text": entity_text,
                    "cache_hit": True,
                    "inference_ms": 0.0,
                    "used_fallback": False,
                }

            # Get cross-encoder score with timing
            start_time = time.time()
            raw_score = self._model.predict([(query, entity_text)])
            inference_ms = (time.time() - start_time) * 1000

            # Normalize score to 0-1 range using configured parameters
            scale_factor = self.settings.cross_encoder_scale_factor
            offset = self.settings.cross_encoder_offset
            normalized_score = (raw_score + offset) / scale_factor
            normalized_score = max(0.0, min(1.0, normalized_score))
            normalized_score = float(normalized_score)

            # Cache the result
            self._score_cache[cache_key] = normalized_score

            return {
                "score": normalized_score,
                "raw_score": float(raw_score),
                "input_text": entity_text,
                "cache_hit": False,
                "inference_ms": inference_ms,
                "used_fallback": False,
            }

        except Exception as exc:
            logger.warning(f"Cross-encoder scoring failed: {exc}")
            fallback_score = self._fallback_text_score(entity, query)
            return {
                "score": fallback_score,
                "raw_score": None,
                "input_text": self._create_entity_description(entity),
                "cache_hit": False,
                "inference_ms": 0.0,
                "used_fallback": True,
            }

    def _get_semantic_score(self, entity: Dict[str, Any], query: str) -> float:
        """
        Get semantic similarity score using cross-encoder with caching.

        Args:
            entity: Entity document
            query: User query

        Returns:
            Semantic similarity score (0.0 to 1.0)
        """
        # Backward compatibility - just return the score
        return self._get_semantic_score_with_debug(entity, query)["score"]

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
            factors["previous_mention"] = self.settings.ranking_previous_mention_boost

        # Intent-specific boosts
        if context.intent == "control":
            # Boost controllable entities for control intents
            if entity_domain in ["light", "switch", "climate", "cover", "lock"]:
                factors["controllable"] = self.settings.ranking_controllable_boost
        elif context.intent == "read":
            # Boost sensors for read intents
            if entity_domain == "sensor":
                factors["readable"] = self.settings.ranking_readable_boost

        # Availability boost - strongly prefer entities with active state values
        if entity_domain == "sensor" and entity_id:
            from app.services.core.state_service import get_last_state

            try:
                current_value = get_last_state(entity_id)
                if current_value is not None:
                    factors["has_active_value"] = (
                        self.settings.ranking_active_sensor_boost
                    )
                else:
                    factors["unavailable_penalty"] = (
                        self.settings.ranking_unavailable_penalty
                    )
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
            all_strs = []

            if primary_entities:
                for pe in primary_entities:
                    entity = pe.entity
                    name = cls._get_clean_name(entity)
                    area = cls._get_area_display_name(entity)
                    value = cls._get_value_str(entity, use_fresh_data=True)

                    # Only add area if it's not empty
                    if area:
                        all_strs.append(f"{name} {area}{value}")
                    else:
                        all_strs.append(f"{name}{value}")

            if related_entities:
                for re in related_entities:
                    entity = re.entity
                    name = cls._get_clean_name(entity)
                    area = cls._get_area_display_name(entity)
                    value = cls._get_value_str(entity, use_fresh_data=True)

                    # Only add area if it's not empty
                    if area:
                        all_strs.append(f"{name} {area}{value}")
                    else:
                        all_strs.append(f"{name}{value}")

            return " | ".join(all_strs)

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
                    area = cls._get_area_display_name(entity)
                    value = cls._get_value_str(entity, use_fresh_data=True)
                    parts.append(f"- {name} [{area}]{value}")

            if related_entities:
                parts.append("\nRelated entities:")
                for re in related_entities:
                    entity = re.entity
                    name = cls._get_clean_name(entity)
                    area = cls._get_area_display_name(entity)
                    value = cls._get_value_str(entity, use_fresh_data=True)
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
        def _get_area_display_name(cls, entity):
            """Get human-readable area name with aliases lookup from database"""
            area_id = entity.get("area", "")

            if not area_id:
                return ""

            try:
                # Import here to avoid circular imports
                from ha_rag_bridge.api import get_arango_db

                db = get_arango_db()

                # Try to find area in collection
                cursor = db.aql.execute(
                    "FOR area IN area FILTER area._key == @area_id RETURN area",
                    bind_vars={"area_id": area_id},
                )
                results = list(cursor)

                if results:
                    area_doc = results[0]
                    name = area_doc.get("name", area_id)
                    aliases = area_doc.get("aliases", [])

                    if aliases and any(
                        alias.strip() for alias in aliases
                    ):  # Only if non-empty aliases
                        return f"[{name} ({', '.join(alias for alias in aliases if alias.strip())})]"
                    return f"[{name}]"

            except Exception as e:
                logger.warning(f"Could not lookup area '{area_id}': {e}")

            # Fallback to capitalized area ID
            return f"[{area_id.replace('_', ' ').title()}]"

        @classmethod
        def _get_clean_name(cls, entity):
            """Get clean entity name without area repetition"""
            friendly_name = entity.get("friendly_name", "")
            entity_id = entity.get("entity_id", "")
            domain = entity.get("domain", "")
            device_class = entity.get("device_class", "")

            # Use friendly name if available and meaningful, but avoid generic names
            if friendly_name and friendly_name.lower() not in [
                "temperature",
                "humidity",
                "pressure",
                "power",  # Generic "power" should be improved
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
                elif "power" in entity_id.lower():
                    # Generate descriptive name for power sensors based on entity_id
                    if "tv" in entity_id.lower():
                        return "TV fogyasztás"
                    elif (
                        "ejjeliszekren" in entity_id.lower()
                        or "nightstand" in entity_id.lower()
                    ):
                        return "Éjjeli szekrény fogyasztás"
                    elif "konnektor" in entity_id.lower():
                        # Extract device name from entity_id if possible
                        parts = entity_id.split("_")
                        if len(parts) > 2:
                            device_part = parts[1] if parts[1] != "power" else parts[0]
                            return f"{device_part.title()} fogyasztás"
                        return "Konnektor fogyasztás"
                    else:
                        return "Power"
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
        def _get_value_str(cls, entity, use_fresh_data: bool = False):
            """Get formatted value string for entity with optional fresh data"""
            if use_fresh_data:
                from app.services.core.state_service import get_fresh_state

                get_state_func = get_fresh_state
            else:
                from app.services.core.state_service import get_last_state

                get_state_func = get_last_state

            if entity.get("domain") == "sensor":
                entity_id = entity.get("entity_id", "")
                current_state = get_state_func(entity_id)
                if current_state is not None:
                    # Extract the actual state value and unit from the response
                    if isinstance(current_state, dict) and "state" in current_state:
                        state_value = current_state["state"]
                        # Get unit from attributes if available
                        unit = ""
                        if (
                            "attributes" in current_state
                            and current_state["attributes"]
                        ):
                            unit = current_state["attributes"].get(
                                "unit_of_measurement", ""
                            )

                        if unit:
                            return f": {state_value} {unit}"
                        else:
                            return f": {state_value}"
                    else:
                        # Fallback for simple string/number values
                        return f": {current_state}"
            return ""

        @classmethod
        def hierarchical_format(
            cls, primary_entities, related_entities, areas_info, memory_entities=None
        ):
            """Hierarchical context format separating primary, secondary, and historical context"""
            parts = [
                "You are an intelligent home assistant AI with deep understanding of your user's home environment.\n"
            ]

            # Group memory entities by context type if provided
            memory_primary = []
            memory_secondary = []
            memory_historical = []

            if memory_entities:
                for entity_data in memory_entities:
                    context_type = entity_data.get("context_type", "primary")
                    if context_type == "primary":
                        memory_primary.append(entity_data)
                    elif context_type == "secondary":
                        memory_secondary.append(entity_data)
                    else:
                        memory_historical.append(entity_data)

            # Combine fresh entities with memory entities by priority
            current_primary = [pe.entity for pe in primary_entities]
            current_related = [re.entity for re in related_entities]

            # PRIMARY CONTEXT - High relevance to current query
            if current_primary or memory_primary:
                parts.append("## Primary Context (High Relevance)")

                # Current query primary entities (fresh data)
                if current_primary:
                    for entity in current_primary:
                        name = cls._get_clean_name(entity)
                        area = cls._get_area_display_name(entity)
                        value = cls._get_value_str(entity, use_fresh_data=True)
                        parts.append(f"- [P] {name}: {area} {value}".strip())

                # Memory primary entities that are still highly relevant
                if memory_primary:
                    for mem_entity in memory_primary:
                        if mem_entity["entity_id"] not in [
                            e.get("entity_id") for e in current_primary
                        ]:
                            name = cls._get_clean_name(
                                {"entity_id": mem_entity["entity_id"]}
                            )
                            area = mem_entity.get("area", "")
                            # Always get fresh value for primary context
                            value = cls._get_value_str(
                                {
                                    "entity_id": mem_entity["entity_id"],
                                    "domain": mem_entity.get("domain"),
                                },
                                use_fresh_data=True,
                            )
                            parts.append(f"- [P] {name}: {area} {value}".strip())

                parts.append("")

            # SECONDARY CONTEXT - Supporting information
            if current_related or memory_secondary:
                parts.append("## Secondary Context (Supporting Information)")

                # Current query related entities
                if current_related:
                    for entity in current_related[:3]:  # Limit to avoid clutter
                        name = cls._get_clean_name(entity)
                        area = cls._get_area_display_name(entity)
                        value = cls._get_value_str(entity, use_fresh_data=True)
                        parts.append(f"- [S] {name}: {area} {value}".strip())

                # Memory secondary entities
                if memory_secondary:
                    for mem_entity in memory_secondary[:2]:  # Limit secondary memory
                        if mem_entity["entity_id"] not in [
                            e.get("entity_id") for e in current_related
                        ]:
                            name = cls._get_clean_name(
                                {"entity_id": mem_entity["entity_id"]}
                            )
                            area = mem_entity.get("area", "")
                            value = cls._get_value_str(
                                {
                                    "entity_id": mem_entity["entity_id"],
                                    "domain": mem_entity.get("domain"),
                                },
                                use_fresh_data=True,
                            )
                            parts.append(f"- [S] {name}: {area} {value}".strip())

                parts.append("")

            # HISTORICAL CONTEXT - Previously mentioned (only if relevant and not overwhelming)
            if (
                memory_historical and len(memory_historical) <= 3
            ):  # Only show if manageable
                parts.append("## Previous Context (Previously Mentioned)")

                for mem_entity in memory_historical:
                    if mem_entity["entity_id"] not in [
                        e.get("entity_id") for e in current_primary + current_related
                    ]:
                        name = cls._get_clean_name(
                            {"entity_id": mem_entity["entity_id"]}
                        )
                        area = mem_entity.get("area", "")
                        # For historical context, we can use cached values to save API calls
                        value = cls._get_value_str(
                            {
                                "entity_id": mem_entity["entity_id"],
                                "domain": mem_entity.get("domain"),
                            },
                            use_fresh_data=False,
                        )
                        parts.append(f"- [H] {name}: {area} {value}".strip())

                parts.append("")

            # AREAS INFO
            if areas_info:
                area_strs = []
                for area, aliases in areas_info.items():
                    if aliases:
                        area_strs.append(f"{area} ({', '.join(aliases)})")
                    else:
                        area_strs.append(area)
                parts.append(f"**Areas**: {', '.join(area_strs)}")

            return "\n".join(parts)

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
        from app.services.conversation.conversation_analyzer import (
            conversation_analyzer,
        )

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
        from app.services.conversation.conversation_analyzer import (
            conversation_analyzer,
        )

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
        elif context.is_follow_up:  # Use hierarchical for follow-up queries
            return "hierarchical"
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
        elif formatter_type == "hierarchical":
            # Hierarchical format needs memory entities for full context
            return self.SystemPromptFormatter.hierarchical_format(
                primary_entities, related_entities, areas_info, memory_entities=None
            )
        else:
            return self.SystemPromptFormatter.detailed_format(
                primary_entities, related_entities, areas_info
            )

    async def format_entities_for_prompt(
        self,
        entities: List[Dict[str, Any]],
        force_formatter: Optional[str] = None,
        use_fresh_data: bool = True,
    ) -> str:
        """
        Format entities for LLM prompt injection with fresh state data.

        Args:
            entities: List of entity dictionaries from database
            force_formatter: Force specific formatter ('compact', 'detailed', etc.)
            use_fresh_data: Whether to fetch fresh state/attributes from HA

        Returns:
            Formatted string ready for LLM prompt injection
        """
        if not entities:
            return "No relevant entities found for the conversation."

        logger.info(
            f"Formatting {len(entities)} entities for prompt with fresh_data={use_fresh_data}"
        )

        # Convert to EntityScore objects for consistent formatting
        entity_scores = []
        for entity in entities:
            # Create minimal EntityScore for formatting
            entity_score = EntityScore(
                entity=entity,
                base_score=entity.get("score", 0.0),
                context_boost=0.0,
                final_score=entity.get("score", 0.0),
                ranking_factors={},
            )
            entity_scores.append(entity_score)

        # Use the specified formatter or default to compact
        if force_formatter == "compact":
            return self.SystemPromptFormatter.compact_format(entity_scores, [], {})
        elif force_formatter == "detailed":
            return self.SystemPromptFormatter.detailed_format(entity_scores, [], {})
        else:
            # Default to compact for hook integration
            return self.SystemPromptFormatter.compact_format(entity_scores, [], {})


# Global instance for reuse
entity_reranker = EntityReranker()
