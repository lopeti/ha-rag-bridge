"""
Query Expansion Service for semantic search enhancement.

Provides multi-query generation with synonyms, translations, and domain-specific variations
to improve search recall and relevance for Hungarian smart home queries.

Examples:
    Query: "hány fok van a nappaliban"
    Expanded: [
        "hány fok van a nappaliban",
        "mennyi a hőmérséklet a nappaliban",
        "what is the temperature in the living room",
        "milyen meleg van a nappaliban"
    ]
"""

import re
from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from ha_rag_bridge.config import get_settings
from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QueryExpansionResult:
    """Result of query expansion operation."""

    original_query: str
    expanded_queries: List[str]
    expansion_methods: List[str]  # ["synonym", "translation", "domain_variant"]
    confidence_scores: List[float]
    processing_time_ms: int
    total_variants: int
    filtered_variants: int


@dataclass
class ExpansionCandidate:
    """Single query expansion candidate."""

    query: str
    method: str
    confidence: float
    source_terms: List[str]
    target_terms: List[str]


class QueryExpander:
    """Semantic query expansion optimized for Hungarian smart home domain."""

    # Domain-specific synonym mappings (Hungarian)
    DOMAIN_SYNONYMS = {
        # Temperature domain
        "temperature": {
            "hu": ["hőmérséklet", "hőfok", "fok", "meleg", "hideg", "langyos"],
            "en": ["temperature", "temp", "degrees", "warm", "cold", "hot"],
        },
        "humidity": {
            "hu": ["páratartalom", "nedvesség", "pára", "fürdő", "vizes"],
            "en": ["humidity", "moisture", "dampness", "wet"],
        },
        "light": {
            "hu": ["világítás", "lámpa", "fény", "villanykörte", "led", "izzó"],
            "en": ["light", "lighting", "lamp", "bulb", "led", "illumination"],
        },
        "energy": {
            "hu": ["energia", "áram", "villany", "fogyasztás", "termelés", "napelem"],
            "en": [
                "energy",
                "power",
                "electricity",
                "consumption",
                "production",
                "solar",
            ],
        },
        "security": {
            "hu": ["biztonság", "riasztó", "védelem", "mozgás", "ajtó", "ablak"],
            "en": ["security", "alarm", "protection", "motion", "door", "window"],
        },
        "climate": {
            "hu": ["klíma", "légkondicionáló", "fűtés", "hűtés", "ventillátor"],
            "en": ["climate", "air conditioning", "heating", "cooling", "fan", "hvac"],
        },
    }

    # Intent transformation patterns
    INTENT_PATTERNS = {
        # Question patterns
        "query": {
            "hány": ["mennyi", "milyen", "mekkora"],
            "mennyi": ["hány", "milyen", "mekkora"],
            "milyen": ["hány", "mennyi", "hogyan"],
            "how much": ["what is", "how many"],
            "what is": ["how much", "what's"],
        },
        # Action patterns
        "control": {
            "kapcsold": ["indítsd", "állítsd", "tedd"],
            "fel": ["be", "on"],
            "le": ["ki", "off"],
            "turn on": ["switch on", "enable"],
            "turn off": ["switch off", "disable"],
        },
    }

    # Area name mappings (Hungarian <-> English)
    AREA_TRANSLATIONS = {
        "nappali": "living room",
        "konyha": "kitchen",
        "hálószoba": "bedroom",
        "fürdőszoba": "bathroom",
        "dolgozószoba": "office",
        "pince": "basement",
        "padlás": "attic",
        "garázs": "garage",
        "kert": "garden",
        "terasz": "terrace",
        "előszoba": "hallway",
        "étkezd": "dining room",
    }

    # Common query reformulation patterns
    REFORMULATION_PATTERNS = [
        # Temperature queries
        (r"(hány|mennyi)\s+fok\s+van\s+(a|az)\s+(\w+)", r"milyen a hőmérséklet a \3"),
        (
            r"(hány|mennyi)\s+fok\s+van\s+(a|az)\s+(\w+)",
            r"what is the temperature in the \3",
        ),
        # Light control queries
        (r"kapcsold\s+fel\s+(a|az)\s+(\w+)", r"turn on the \2"),
        (r"kapcsold\s+le\s+(a|az)\s+(\w+)", r"turn off the \2"),
        # Status queries
        (r"mi\s+van\s+(a|az)\s+(\w+)", r"what is happening in the \2"),
        (r"hogyan\s+áll\s+(a|az)\s+(\w+)", r"how is the \2 doing"),
    ]

    def __init__(self):
        """Initialize the query expander."""
        self.settings = get_settings()
        self.enabled = self.settings.query_expansion_enabled
        self.max_variants = self.settings.max_query_variants
        self.include_translations = self.settings.include_query_translations
        self.include_synonyms = self.settings.include_query_synonyms

        logger.info(
            f"QueryExpander initialized: enabled={self.enabled}, "
            f"max_variants={self.max_variants}, "
            f"translations={self.include_translations}, synonyms={self.include_synonyms}"
        )

    async def expand_query(
        self,
        original_query: str,
        conversation_context: Optional[Dict[str, Any]] = None,
        domain_context: Optional[str] = None,
    ) -> QueryExpansionResult:
        """
        Expand a query into multiple semantic variants.

        Args:
            original_query: The original user query
            conversation_context: Optional conversation context for personalization
            domain_context: Optional domain hint for focused expansion

        Returns:
            QueryExpansionResult with expanded queries and metadata
        """
        start_time = datetime.now()

        if not self.enabled:
            return self._create_disabled_result(original_query, start_time)

        try:
            # Generate expansion candidates
            candidates = await self._generate_candidates(
                original_query, conversation_context, domain_context
            )

            # Filter and rank candidates
            filtered_candidates = self._filter_and_rank_candidates(
                original_query, candidates
            )

            # Select top variants
            selected_variants = self._select_top_variants(
                original_query, filtered_candidates
            )

            processing_time = max(
                1, int((datetime.now() - start_time).total_seconds() * 1000)
            )

            return QueryExpansionResult(
                original_query=original_query,
                expanded_queries=selected_variants,
                expansion_methods=[
                    c.method for c in filtered_candidates[: len(selected_variants)]
                ],
                confidence_scores=[
                    c.confidence for c in filtered_candidates[: len(selected_variants)]
                ],
                processing_time_ms=processing_time,
                total_variants=len(candidates),
                filtered_variants=len(filtered_candidates),
            )

        except Exception as e:
            logger.error(f"Query expansion failed: {e}", exc_info=True)
            return self._create_error_result(original_query, str(e), start_time)

    async def _generate_candidates(
        self, query: str, context: Optional[Dict[str, Any]], domain: Optional[str]
    ) -> List[ExpansionCandidate]:
        """Generate all possible expansion candidates."""
        candidates = []

        # Always include original query
        candidates.append(
            ExpansionCandidate(
                query=query,
                method="original",
                confidence=1.0,
                source_terms=[],
                target_terms=[],
            )
        )

        # Synonym-based expansion
        if self.include_synonyms:
            synonym_candidates = await self._generate_synonym_variants(query, domain)
            candidates.extend(synonym_candidates)

        # Translation-based expansion
        if self.include_translations:
            translation_candidates = await self._generate_translation_variants(query)
            candidates.extend(translation_candidates)

        # Pattern-based reformulation
        reformulation_candidates = await self._generate_reformulation_variants(query)
        candidates.extend(reformulation_candidates)

        # Context-aware expansion
        if context:
            context_candidates = await self._generate_context_variants(query, context)
            candidates.extend(context_candidates)

        return candidates

    async def _generate_synonym_variants(
        self, query: str, domain: Optional[str]
    ) -> List[ExpansionCandidate]:
        """Generate synonym-based query variants."""
        candidates = []
        query_lower = query.lower()

        # Determine relevant domains from query content
        relevant_domains = self._detect_domains(query_lower)
        if domain:
            relevant_domains.add(domain)

        for domain_name in relevant_domains:
            if domain_name not in self.DOMAIN_SYNONYMS:
                continue

            domain_syns = self.DOMAIN_SYNONYMS[domain_name]

            # Hungarian synonyms
            for original_term in domain_syns["hu"]:
                if original_term in query_lower:
                    for synonym in domain_syns["hu"]:
                        if synonym != original_term:
                            variant_query = query_lower.replace(original_term, synonym)
                            candidates.append(
                                ExpansionCandidate(
                                    query=variant_query,
                                    method="synonym_hu",
                                    confidence=0.8,
                                    source_terms=[original_term],
                                    target_terms=[synonym],
                                )
                            )

        return candidates

    async def _generate_translation_variants(
        self, query: str
    ) -> List[ExpansionCandidate]:
        """Generate translation-based query variants."""
        candidates = []
        query_lower = query.lower()

        # Hungarian to English area translations
        for hu_area, en_area in self.AREA_TRANSLATIONS.items():
            if hu_area in query_lower:
                en_variant = query_lower.replace(hu_area, en_area)
                candidates.append(
                    ExpansionCandidate(
                        query=en_variant,
                        method="translation_area",
                        confidence=0.7,
                        source_terms=[hu_area],
                        target_terms=[en_area],
                    )
                )

        # Domain term translations
        for domain_name, domain_terms in self.DOMAIN_SYNONYMS.items():
            hu_terms = domain_terms["hu"]
            en_terms = domain_terms["en"]

            for i, hu_term in enumerate(hu_terms):
                if hu_term in query_lower and i < len(en_terms):
                    en_term = en_terms[i]
                    en_variant = query_lower.replace(hu_term, en_term)
                    candidates.append(
                        ExpansionCandidate(
                            query=en_variant,
                            method="translation_domain",
                            confidence=0.6,
                            source_terms=[hu_term],
                            target_terms=[en_term],
                        )
                    )

        return candidates

    async def _generate_reformulation_variants(
        self, query: str
    ) -> List[ExpansionCandidate]:
        """Generate pattern-based reformulation variants."""
        candidates = []

        for pattern, replacement in self.REFORMULATION_PATTERNS:
            match = re.search(pattern, query.lower())
            if match:
                try:
                    reformulated = re.sub(pattern, replacement, query.lower())
                    if reformulated != query.lower():
                        candidates.append(
                            ExpansionCandidate(
                                query=reformulated,
                                method="reformulation",
                                confidence=0.75,
                                source_terms=[match.group(0)],
                                target_terms=[reformulated],
                            )
                        )
                except Exception as e:
                    logger.debug(f"Reformulation pattern failed: {e}")
                    continue

        # Intent pattern substitutions
        query_lower = query.lower()
        for intent_category, substitutions in self.INTENT_PATTERNS.items():
            for original, alternatives in substitutions.items():
                if original in query_lower:
                    for alternative in alternatives:
                        variant = query_lower.replace(original, alternative)
                        if variant != query_lower:
                            candidates.append(
                                ExpansionCandidate(
                                    query=variant,
                                    method=f"intent_{intent_category}",
                                    confidence=0.65,
                                    source_terms=[original],
                                    target_terms=[alternative],
                                )
                            )

        return candidates

    async def _generate_context_variants(
        self, query: str, context: Dict[str, Any]
    ) -> List[ExpansionCandidate]:
        """Generate context-aware query variants."""
        candidates: List[ExpansionCandidate] = []

        # Use conversation memory for personalization
        if "recent_entities" in context:
            # Could expand query to include recently mentioned entities
            # Implementation depends on conversation memory structure
            pass

        if "preferred_areas" in context:
            # Could bias expansion towards frequently mentioned areas
            pass

        # For now, return empty list - can be enhanced based on actual context structure
        return candidates

    def _detect_domains(self, query: str) -> Set[str]:
        """Detect relevant domains from query content."""
        domains = set()

        for domain_name, domain_terms in self.DOMAIN_SYNONYMS.items():
            for lang_terms in domain_terms.values():
                for term in lang_terms:
                    if term in query:
                        domains.add(domain_name)
                        break

        return domains

    def _filter_and_rank_candidates(
        self, original_query: str, candidates: List[ExpansionCandidate]
    ) -> List[ExpansionCandidate]:
        """Filter and rank expansion candidates by quality."""

        # Remove duplicates
        seen_queries = set()
        unique_candidates = []

        for candidate in candidates:
            query_normalized = candidate.query.strip().lower()
            if query_normalized not in seen_queries:
                seen_queries.add(query_normalized)
                unique_candidates.append(candidate)

        # Filter out low-quality candidates
        quality_filtered = []
        for candidate in unique_candidates:
            # Skip if too similar to original (edit distance check)
            if (
                self._calculate_similarity(original_query.lower(), candidate.query)
                > 0.95
            ):
                continue

            # Skip if confidence too low
            if candidate.confidence < 0.5:
                continue

            # Skip if query is malformed
            if not self._is_valid_query(candidate.query):
                continue

            quality_filtered.append(candidate)

        # Sort by confidence score (descending)
        quality_filtered.sort(key=lambda x: x.confidence, reverse=True)

        return quality_filtered

    def _select_top_variants(
        self, original_query: str, candidates: List[ExpansionCandidate]
    ) -> List[str]:
        """Select top N query variants for final result."""

        selected = [original_query]  # Always include original

        # Add top candidates up to max_variants limit
        for candidate in candidates:
            if len(selected) >= self.max_variants:
                break

            if (
                candidate.method != "original"
            ):  # Skip original since it's already included
                selected.append(candidate.query)

        return selected

    def _calculate_similarity(self, query1: str, query2: str) -> float:
        """Calculate similarity between two queries (simple implementation)."""
        words1 = set(query1.split())
        words2 = set(query2.split())

        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    def _is_valid_query(self, query: str) -> bool:
        """Check if query is valid and well-formed."""
        if not query or not query.strip():
            return False

        # Check minimum length
        if len(query.strip()) < 3:
            return False

        # Check for reasonable word count
        words = query.strip().split()
        if len(words) < 1 or len(words) > 50:
            return False

        return True

    def _create_disabled_result(
        self, query: str, start_time: datetime
    ) -> QueryExpansionResult:
        """Create result when expansion is disabled."""
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return QueryExpansionResult(
            original_query=query,
            expanded_queries=[query],
            expansion_methods=["disabled"],
            confidence_scores=[1.0],
            processing_time_ms=processing_time,
            total_variants=1,
            filtered_variants=1,
        )

    def _create_error_result(
        self, query: str, error: str, start_time: datetime
    ) -> QueryExpansionResult:
        """Create result when expansion fails."""
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return QueryExpansionResult(
            original_query=query,
            expanded_queries=[query],  # Fallback to original
            expansion_methods=["error"],
            confidence_scores=[0.0],
            processing_time_ms=processing_time,
            total_variants=0,
            filtered_variants=0,
        )


# Global instance for use across the application
query_expander = QueryExpander()
