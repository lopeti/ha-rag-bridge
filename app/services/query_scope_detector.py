"""Query scope detection service for adaptive RAG retrieval."""

import re
from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass

from ha_rag_bridge.logging import get_logger
from .conversation_analyzer import ConversationAnalyzer

logger = get_logger(__name__)


class QueryScope(Enum):
    """Query scope levels for adaptive entity retrieval."""

    MICRO = "micro"  # Specific entity operations (k=5-10)
    MACRO = "macro"  # Area-based queries (k=15-30)
    OVERVIEW = "overview"  # House-wide queries (k=30-50)


@dataclass
class ScopeConfig:
    """Configuration for each query scope level."""

    k_min: int
    k_max: int
    cluster_types: List[str]
    formatter: str
    threshold: float = 0.7


class QueryScopeDetector:
    """Detects query scope to optimize entity retrieval strategy."""

    # Scope configuration mapping
    SCOPE_CONFIGS = {
        QueryScope.MICRO: ScopeConfig(
            k_min=5,
            k_max=10,
            cluster_types=["micro_cluster"],
            formatter="detailed",
            threshold=0.8,
        ),
        QueryScope.MACRO: ScopeConfig(
            k_min=15,
            k_max=30,
            cluster_types=["micro_cluster", "macro_cluster"],
            formatter="grouped_by_area",
            threshold=0.7,
        ),
        QueryScope.OVERVIEW: ScopeConfig(
            k_min=30,
            k_max=50,
            cluster_types=["overview_cluster", "macro_cluster"],
            formatter="tldr",
            threshold=0.6,
        ),
    }

    def __init__(self):
        """Initialize scope detector with pattern matching."""
        self.conversation_analyzer = ConversationAnalyzer()

        # Hungarian and English patterns for each scope level
        self.scope_patterns = {
            QueryScope.MICRO: [
                # Specific control actions
                r"\b(kapcsold|indítsd|állítsd|turn\s+on|turn\s+off|switch)\b",
                # Specific entity names (will be dynamically enhanced)
                r"\b(sensor\.|light\.|climate\.|switch\.)\w+",
                # Precise value queries
                r"\b(mennyi|exactly|pontosan|specific)\b",
                # Single device references
                r"\b(ez\s+a|this|that|azt\s+a)\b",
            ],
            QueryScope.MACRO: [
                # Area-based queries
                r"\b(nappali|konyha|hálószoba|fürdő|living\s+room|kitchen|bedroom|bathroom)\b",
                r"\b(kert|kerti|garden|outside|kint|kinn)\b",
                # Domain-wide queries
                r"\b(minden\s+lámpa|all\s+lights|összes\s+fény|climate\s+in)\b",
                # Status queries for areas
                r"\b(mi\s+van|what\'?s|helyzet|status|állapot)\s.*(ban|ben|in\s+the)\b",
                # Comparative queries
                r"\b(és\s+a|and\s+the|összehasonlítva|compared)\b",
            ],
            QueryScope.OVERVIEW: [
                # House-wide queries
                r"\b(otthon|house|home|minden|all|összes|entire)\b",
                # Summary requests
                r"\b(összesítés|summary|overview|áttekintés|jelentés|report)\b",
                # Global status
                r"\b(mi\s+újság|what\'?s\s+new|helyzet|situation|status)\s.*(otthon|home)\b",
                # Energy/system-wide
                r"\b(energia|energy|consumption|fogyasztás|termelés|production)\b",
                # Security overview
                r"\b(biztonság|security|all\s+sensors|minden\s+érzékelő)\b",
            ],
        }

        # Compile patterns for performance
        self.compiled_patterns = {
            scope: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for scope, patterns in self.scope_patterns.items()
        }

    def detect_scope(
        self, query: str, conversation_context: Optional[Dict] = None
    ) -> Tuple[QueryScope, ScopeConfig, Dict[str, Any]]:
        """Detect the appropriate scope for a query.

        Args:
            query: User query text
            conversation_context: Optional conversation context from analyzer

        Returns:
            Tuple of (detected_scope, scope_config, detection_details)
        """
        # Analyze conversation context if not provided
        if conversation_context is None:
            conversation_context = self.conversation_analyzer.analyze_conversation(
                query, conversation_history=[]
            )

        # Score each scope based on pattern matching
        scope_scores = {scope: 0.0 for scope in QueryScope}
        matched_patterns: Dict[QueryScope, List[str]] = {scope: [] for scope in QueryScope}

        # Pattern-based scoring
        for scope, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(query):
                    scope_scores[scope] += 1.0
                    matched_patterns[scope].append(pattern.pattern)

        # Context-based adjustments
        self._adjust_scores_by_context(scope_scores, conversation_context, query)

        # Determine winning scope
        detected_scope = max(scope_scores.keys(), key=lambda x: scope_scores[x])

        # Fallback logic for ambiguous cases
        if scope_scores[detected_scope] == 0:
            detected_scope = self._fallback_scope_detection(query, conversation_context)

        scope_config = self.SCOPE_CONFIGS[detected_scope]

        # Calculate optimal k value within range
        optimal_k = self._calculate_optimal_k(
            detected_scope, scope_config, conversation_context
        )

        detection_details = {
            "scope_scores": scope_scores,
            "matched_patterns": matched_patterns,
            "optimal_k": optimal_k,
            "confidence": scope_scores[detected_scope],
            "context_factors": self._get_context_factors(conversation_context),
            "reasoning": self._generate_reasoning(
                detected_scope, matched_patterns[detected_scope], conversation_context
            ),
        }

        logger.debug(
            f"Query scope detected: {detected_scope.value}",
            query=query[:50],
            optimal_k=optimal_k,
            confidence=round(scope_scores[detected_scope], 2),
            matched_patterns=len(matched_patterns[detected_scope]),
        )

        return detected_scope, scope_config, detection_details

    def _adjust_scores_by_context(
        self,
        scope_scores: Dict[QueryScope, float],
        context,  # Can be ConversationContext object or dict
        query: str,
    ) -> None:
        """Adjust scope scores based on conversation context."""

        # Handle both dataclass and dict context
        if hasattr(context, "areas_mentioned"):
            # ConversationContext dataclass
            areas_mentioned = list(context.areas_mentioned)
            domains_mentioned = list(context.domains_mentioned)
            is_follow_up = context.is_follow_up
            intent = context.intent
        else:
            # Dictionary context
            areas_mentioned = context.get("areas_mentioned", [])
            domains_mentioned = list(context.get("domains_mentioned", set()))
            is_follow_up = context.get("is_follow_up", False)
            intent = context.get("intent", "read")

        # Area mentions boost MACRO scope
        if areas_mentioned:
            if len(areas_mentioned) == 1:
                scope_scores[QueryScope.MACRO] += 2.0  # Single area = MACRO
            elif len(areas_mentioned) > 1:
                scope_scores[QueryScope.OVERVIEW] += 1.5  # Multiple areas = OVERVIEW

        # Domain-specific boosts
        if domains_mentioned:
            # Multiple domains suggest broader scope
            if len(domains_mentioned) > 2:
                scope_scores[QueryScope.OVERVIEW] += 1.0
            elif len(domains_mentioned) == 1:
                scope_scores[QueryScope.MICRO] += 0.5

        # Follow-up detection boosts context inheritance
        if is_follow_up:
            # Follow-ups tend to maintain or expand scope
            scope_scores[QueryScope.MACRO] += 1.0

        # Intent-based adjustments
        if intent == "control":
            # Control actions are typically micro or macro
            scope_scores[QueryScope.MICRO] += 1.0
            scope_scores[QueryScope.OVERVIEW] -= 0.5
        elif intent == "read":
            # Read queries can be any scope
            pass

    def _fallback_scope_detection(
        self, query: str, context: Dict[str, Any]
    ) -> QueryScope:
        """Fallback scope detection for ambiguous queries."""

        # Query length heuristic
        if len(query.split()) <= 3:
            return QueryScope.MICRO  # Short queries are usually specific
        elif len(query.split()) >= 10:
            return QueryScope.OVERVIEW  # Long queries are usually broad

        # Default to MACRO for moderate complexity
        return QueryScope.MACRO

    def _calculate_optimal_k(
        self,
        scope: QueryScope,
        config: ScopeConfig,
        context,  # Can be ConversationContext object or dict
    ) -> int:
        """Calculate optimal k value within scope range."""

        base_k = (config.k_min + config.k_max) // 2

        # Handle both dataclass and dict context
        if hasattr(context, "areas_mentioned"):
            areas_count = len(context.areas_mentioned)
            domains_count = len(context.domains_mentioned)
        else:
            areas_count = len(context.get("areas_mentioned", []))
            domains_count = len(context.get("domains_mentioned", set()))

        if scope == QueryScope.MICRO:
            # Fewer entities for specific queries
            if areas_count <= 1 and domains_count <= 1:
                return config.k_min
            else:
                return min(base_k, config.k_max)

        elif scope == QueryScope.MACRO:
            # Scale with area/domain complexity
            adjustment = min(areas_count + domains_count - 1, 5) * 2
            return min(base_k + adjustment, config.k_max)

        else:  # OVERVIEW
            # Use maximum for comprehensive coverage
            return config.k_max

    def _get_context_factors(self, context) -> Dict[str, Any]:
        """Extract context factors that influenced scope detection."""
        if hasattr(context, "areas_mentioned"):
            return {
                "areas_count": len(context.areas_mentioned),
                "domains_count": len(context.domains_mentioned),
                "is_follow_up": context.is_follow_up,
                "intent": context.intent,
                "confidence_level": 0.0,  # Not available in ConversationContext
            }
        else:
            return {
                "areas_count": len(context.get("areas_mentioned", [])),
                "domains_count": len(context.get("domains_mentioned", set())),
                "is_follow_up": context.get("is_follow_up", False),
                "intent": context.get("intent", "unknown"),
                "confidence_level": context.get("confidence", 0.0),
            }

    def _generate_reasoning(
        self,
        scope: QueryScope,
        matched_patterns: List[str],
        context,  # Can be ConversationContext object or dict
    ) -> str:
        """Generate human-readable reasoning for scope detection."""

        reasons = []

        if matched_patterns:
            reasons.append(f"Matched {len(matched_patterns)} {scope.value} patterns")

        # Handle both dataclass and dict context
        if hasattr(context, "areas_mentioned"):
            areas = list(context.areas_mentioned)
            is_follow_up = context.is_follow_up
            intent = context.intent
        else:
            areas = context.get("areas_mentioned", [])
            is_follow_up = context.get("is_follow_up", False)
            intent = context.get("intent", "")

        if areas:
            if len(areas) == 1:
                reasons.append(f"Single area mentioned: {areas[0]}")
            else:
                reasons.append(f"Multiple areas mentioned: {', '.join(areas)}")

        if is_follow_up:
            reasons.append("Follow-up question detected")

        if intent == "control":
            reasons.append("Control intent detected")

        return "; ".join(reasons) if reasons else "Fallback heuristics applied"


# Global instance for use in main application
query_scope_detector = QueryScopeDetector()
