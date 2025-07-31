"""
Embedding similarity threshold configuration for HA-RAG Bridge.
Optimized thresholds based on embedding model characteristics.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class RelevanceLevel(Enum):
    """Relevance levels for search results."""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"


@dataclass
class SimilarityThresholds:
    """Similarity thresholds for different embedding models."""

    excellent: float  # Highly relevant results
    good: float  # Relevant results
    acceptable: float  # May be relevant
    minimum: float  # Filter threshold (below this = filter out)


# Model-specific optimized thresholds based on analysis
MODEL_THRESHOLDS: Dict[str, SimilarityThresholds] = {
    # Current model: paraphrase-multilingual-MiniLM-L12-v2
    "paraphrase-multilingual-minilm-l12-v2": SimilarityThresholds(
        excellent=0.88,  # Very high confidence
        good=0.75,  # Good relevance
        acceptable=0.52,  # Might be relevant
        minimum=0.45,  # Minimum to consider
    ),
    # Alternative models (estimated based on typical performance)
    "all-mpnet-base-v2": SimilarityThresholds(
        excellent=0.85, good=0.70, acceptable=0.50, minimum=0.40
    ),
    "paraphrase-multilingual-mpnet-base-v2": SimilarityThresholds(
        excellent=0.85, good=0.70, acceptable=0.50, minimum=0.40
    ),
    "all-minilm-l6-v2": SimilarityThresholds(
        excellent=0.90, good=0.80, acceptable=0.60, minimum=0.50
    ),
    # OpenAI and Gemini models (different scale)
    "text-embedding-3-large": SimilarityThresholds(
        excellent=0.82, good=0.70, acceptable=0.55, minimum=0.45
    ),
    "gemini-embedding-001": SimilarityThresholds(
        excellent=0.80, good=0.65, acceptable=0.50, minimum=0.40
    ),
    # Default fallback thresholds
    "default": SimilarityThresholds(
        excellent=0.80, good=0.65, acceptable=0.50, minimum=0.40
    ),
}


def get_similarity_thresholds() -> SimilarityThresholds:
    """Get similarity thresholds for the current embedding model."""

    # Get current model from environment
    model_name = os.getenv(
        "SENTENCE_TRANSFORMER_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
    )
    embedding_backend = os.getenv("EMBEDDING_BACKEND", "local").lower()

    # Normalize model name for lookup
    if embedding_backend == "openai":
        model_key = "text-embedding-3-large"
    elif embedding_backend == "gemini":
        model_key = "gemini-embedding-001"
    else:
        # Local model - normalize name
        model_key = model_name.lower().replace("_", "-").replace("/", "-")
        if "sentence-transformers-" in model_key:
            model_key = model_key.replace("sentence-transformers-", "")

    # Get thresholds for the model or use default
    thresholds = MODEL_THRESHOLDS.get(model_key, MODEL_THRESHOLDS["default"])

    # Allow environment override
    excellent_override = os.getenv("SIMILARITY_THRESHOLD_EXCELLENT")
    good_override = os.getenv("SIMILARITY_THRESHOLD_GOOD")
    acceptable_override = os.getenv("SIMILARITY_THRESHOLD_ACCEPTABLE")
    minimum_override = os.getenv("SIMILARITY_THRESHOLD_MINIMUM")

    if any([excellent_override, good_override, acceptable_override, minimum_override]):
        thresholds = SimilarityThresholds(
            excellent=(
                float(excellent_override)
                if excellent_override
                else thresholds.excellent
            ),
            good=float(good_override) if good_override else thresholds.good,
            acceptable=(
                float(acceptable_override)
                if acceptable_override
                else thresholds.acceptable
            ),
            minimum=float(minimum_override) if minimum_override else thresholds.minimum,
        )

    return thresholds


def classify_relevance(similarity_score: float) -> RelevanceLevel:
    """Classify a similarity score into a relevance level."""
    thresholds = get_similarity_thresholds()

    if similarity_score >= thresholds.excellent:
        return RelevanceLevel.EXCELLENT
    elif similarity_score >= thresholds.good:
        return RelevanceLevel.GOOD
    elif similarity_score >= thresholds.acceptable:
        return RelevanceLevel.ACCEPTABLE
    else:
        return RelevanceLevel.POOR


def get_search_threshold(level: RelevanceLevel = RelevanceLevel.ACCEPTABLE) -> float:
    """Get the threshold for a specific relevance level."""
    thresholds = get_similarity_thresholds()

    if level == RelevanceLevel.EXCELLENT:
        return thresholds.excellent
    elif level == RelevanceLevel.GOOD:
        return thresholds.good
    elif level == RelevanceLevel.ACCEPTABLE:
        return thresholds.acceptable
    else:
        return thresholds.minimum


def get_adaptive_threshold(query_context: Optional[str] = None) -> float:
    """Get an adaptive threshold based on query context and model performance."""
    thresholds = get_similarity_thresholds()

    # Default to good threshold
    base_threshold = thresholds.good

    # Adjust based on query context if provided
    if query_context:
        query_lower = query_context.lower()

        # For control queries, be more strict (users expect precise matches)
        if any(
            word in query_lower for word in ["turn", "switch", "kapcsold", "állítsd"]
        ):
            return min(thresholds.excellent, base_threshold + 0.05)

        # For status/read queries, be more lenient (users want information even if not perfect match)
        elif any(
            word in query_lower
            for word in ["status", "mennyi", "hány", "milyen", "what", "how"]
        ):
            return max(thresholds.acceptable, base_threshold - 0.05)

    return base_threshold


# Export commonly used values
def get_current_config() -> Dict[str, Any]:
    """Get current threshold configuration for debugging/monitoring."""
    thresholds = get_similarity_thresholds()
    model_name = os.getenv(
        "SENTENCE_TRANSFORMER_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
    )
    backend_name = os.getenv("EMBEDDING_BACKEND", "local")

    return {
        "model_name": model_name,
        "backend_name": backend_name,
        "thresholds": {
            "excellent": thresholds.excellent,
            "good": thresholds.good,
            "acceptable": thresholds.acceptable,
            "minimum": thresholds.minimum,
        },
        "adaptive_defaults": {
            "control_queries": get_adaptive_threshold("turn on lights"),
            "status_queries": get_adaptive_threshold("what is temperature"),
            "general": get_adaptive_threshold(),
        },
    }
