"""
Search Debugger Service for visualizing the multi-stage entity retrieval pipeline.
Captures pipeline state at each stage for debugging and optimization.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)


class PipelineStage(Enum):
    """Pipeline stages for entity retrieval."""

    CLUSTER_SEARCH = "cluster_search"
    VECTOR_FALLBACK = "vector_fallback"
    RERANKING = "reranking"
    FINAL_SELECTION = "final_selection"


@dataclass
class EntityDebugInfo:
    """Debug information for a single entity through the pipeline."""

    entity_id: str
    entity_name: str
    domain: str
    area: str

    # Stage 1: Cluster search
    cluster_score: Optional[float] = None
    source_cluster: Optional[str] = None
    cluster_relevance: Optional[float] = None

    # Stage 2: Vector search
    vector_score: Optional[float] = None
    embedding_similarity: Optional[float] = None

    # Stage 3: Reranking
    base_score: Optional[float] = None
    context_boost: Optional[float] = None
    final_score: Optional[float] = None
    ranking_factors: Optional[Dict[str, float]] = None
    
    # Cross-encoder specific debug info
    cross_encoder_raw_score: Optional[float] = None
    cross_encoder_input_text: Optional[str] = None
    cross_encoder_cache_hit: Optional[bool] = None
    cross_encoder_inference_ms: Optional[float] = None
    used_fallback_matching: Optional[bool] = None

    # Stage 4: Selection
    is_active: Optional[bool] = None
    is_selected: Optional[bool] = None
    selection_rank: Optional[int] = None
    in_prompt: Optional[bool] = None

    # Metadata
    pipeline_stage_reached: Optional[PipelineStage] = None
    score_delta: Optional[float] = None  # final_score - vector_score


@dataclass
class StageResult:
    """Results from a specific pipeline stage."""

    stage: PipelineStage
    stage_name: str
    entities_in: int
    entities_out: int
    execution_time_ms: float
    metadata: Dict[str, Any]


@dataclass
class PipelineDebugInfo:
    """Complete pipeline debug information."""

    query: str
    query_embedding: Optional[List[float]]
    scope_config: Dict[str, Any]

    # Stage results
    stage_results: List[StageResult]
    entities: List[EntityDebugInfo]

    # Summary statistics
    total_execution_time_ms: float
    pipeline_efficiency: Dict[str, float]
    final_entity_count: int
    similarity_threshold: float

    # Query analysis
    detected_scope: Optional[str] = None
    areas_mentioned: Optional[List[str]] = None
    conversation_context: Optional[Dict[str, Any]] = None


class SearchDebugger:
    """
    Service for capturing and analyzing the entity retrieval pipeline.

    Instruments the existing pipeline to collect debug information
    without modifying the core retrieval logic.
    """

    def __init__(self):
        self.debug_session_active = False
        self.current_pipeline: Optional[PipelineDebugInfo] = None
        self.entity_registry: Dict[str, EntityDebugInfo] = {}

    def start_debug_session(
        self,
        query: str,
        query_embedding: List[float],
        scope_config: Dict[str, Any],
        similarity_threshold: float = 0.7,
    ) -> None:
        """Start a new debug session for pipeline tracking."""
        self.debug_session_active = True
        self.entity_registry.clear()

        self.current_pipeline = PipelineDebugInfo(
            query=query,
            query_embedding=query_embedding,
            scope_config=scope_config,
            stage_results=[],
            entities=[],
            total_execution_time_ms=0.0,
            pipeline_efficiency={},
            final_entity_count=0,
            similarity_threshold=similarity_threshold,
        )

        logger.debug(f"Started debug session for query: '{query}'")

    def capture_stage(
        self,
        stage: PipelineStage,
        entities_in: List[Dict[str, Any]],
        entities_out: List[Dict[str, Any]],
        execution_time_ms: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Capture results from a pipeline stage."""
        if not self.debug_session_active or not self.current_pipeline:
            return

        stage_result = StageResult(
            stage=stage,
            stage_name=stage.value.replace("_", " ").title(),
            entities_in=len(entities_in),
            entities_out=len(entities_out),
            execution_time_ms=execution_time_ms,
            metadata=metadata or {},
        )

        self.current_pipeline.stage_results.append(stage_result)

        # Update entity registry with stage-specific information
        if stage == PipelineStage.CLUSTER_SEARCH:
            self._update_cluster_stage(entities_out, metadata)
        elif stage == PipelineStage.VECTOR_FALLBACK:
            self._update_vector_stage(entities_out, metadata)
        elif stage == PipelineStage.RERANKING:
            self._update_reranking_stage(entities_out, metadata)
        elif stage == PipelineStage.FINAL_SELECTION:
            self._update_selection_stage(entities_out, metadata)

        logger.debug(
            f"Captured {stage.value}: {len(entities_in)} -> {len(entities_out)} entities "
            f"in {execution_time_ms:.1f}ms"
        )

    def _update_cluster_stage(
        self, entities: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Update entity registry with cluster search results."""
        for entity in entities:
            entity_id = entity.get("_key") or entity.get("id", "")
            if not entity_id:
                continue

            debug_info = self._get_or_create_entity_debug(entity)
            debug_info.cluster_score = entity.get("cluster_score")
            debug_info.source_cluster = entity.get("source_cluster")
            debug_info.cluster_relevance = entity.get("cluster_relevance")
            debug_info.pipeline_stage_reached = PipelineStage.CLUSTER_SEARCH

    def _update_vector_stage(
        self, entities: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Update entity registry with vector search results."""
        for entity in entities:
            debug_info = self._get_or_create_entity_debug(entity)
            # Check for ArangoDB vector score (_score) first, then fallback to other score fields
            debug_info.vector_score = entity.get(
                "_score", entity.get("score", entity.get("similarity", 0.0))
            )
            debug_info.embedding_similarity = debug_info.vector_score
            debug_info.pipeline_stage_reached = PipelineStage.VECTOR_FALLBACK

    def _update_reranking_stage(
        self, entities: List[Any], metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Update entity registry with reranking results."""
        # entities here are EntityScore objects from entity_reranker
        for entity_score in entities:
            if hasattr(entity_score, "entity"):
                entity = entity_score.entity
                entity_id = entity.get("_key") or entity.get("id", "")
                if not entity_id:
                    continue

                debug_info = self._get_or_create_entity_debug(entity)
                debug_info.base_score = entity_score.base_score
                debug_info.context_boost = entity_score.context_boost
                debug_info.final_score = entity_score.final_score
                debug_info.ranking_factors = entity_score.ranking_factors.copy()
                debug_info.pipeline_stage_reached = PipelineStage.RERANKING
                
                # Copy cross-encoder debug info
                debug_info.cross_encoder_raw_score = getattr(entity_score, 'cross_encoder_raw_score', None)
                debug_info.cross_encoder_input_text = getattr(entity_score, 'cross_encoder_input_text', None)
                debug_info.cross_encoder_cache_hit = getattr(entity_score, 'cross_encoder_cache_hit', None)
                debug_info.cross_encoder_inference_ms = getattr(entity_score, 'cross_encoder_inference_ms', None)
                debug_info.used_fallback_matching = getattr(entity_score, 'used_fallback_matching', None)

                # Calculate score delta
                if (
                    debug_info.vector_score is not None
                    and debug_info.final_score is not None
                ):
                    debug_info.score_delta = (
                        debug_info.final_score - debug_info.vector_score
                    )

    def _update_selection_stage(
        self, entities: List[Any], metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Update entity registry with final selection results."""
        for idx, entity_score in enumerate(entities):
            if hasattr(entity_score, "entity"):
                entity = entity_score.entity
                entity_id = entity.get("_key") or entity.get("id", "")
                if not entity_id:
                    continue

                debug_info = self._get_or_create_entity_debug(entity)

                # Determine if entity is active based on ranking factors
                is_active = False
                if debug_info.ranking_factors:
                    has_active_value = (
                        debug_info.ranking_factors.get("has_active_value", 0) > 0
                    )
                    no_unavailable_penalty = (
                        debug_info.ranking_factors.get("unavailable_penalty", 0) == 0
                    )
                    is_active = has_active_value and no_unavailable_penalty

                debug_info.is_active = is_active
                debug_info.is_selected = True  # All entities here are selected
                debug_info.selection_rank = idx + 1
                debug_info.in_prompt = (
                    debug_info.final_score is not None
                    and self.current_pipeline is not None
                    and debug_info.final_score
                    >= self.current_pipeline.similarity_threshold
                )
                debug_info.pipeline_stage_reached = PipelineStage.FINAL_SELECTION

    def _get_or_create_entity_debug(self, entity: Dict[str, Any]) -> EntityDebugInfo:
        """Get or create EntityDebugInfo for an entity."""
        entity_id = entity.get("_key") or entity.get("id", "")

        if entity_id in self.entity_registry:
            return self.entity_registry[entity_id]

        debug_info = EntityDebugInfo(
            entity_id=entity_id,
            entity_name=entity.get("friendly_name", entity.get("name", entity_id)),
            domain=entity.get("domain", "unknown"),
            area=entity.get("area", "unknown"),
        )

        self.entity_registry[entity_id] = debug_info
        return debug_info

    def finish_debug_session(self) -> Optional[PipelineDebugInfo]:
        """Finish debug session and return complete pipeline information."""
        if not self.debug_session_active or not self.current_pipeline:
            return None

        # Calculate total execution time
        total_time = sum(
            stage.execution_time_ms for stage in self.current_pipeline.stage_results
        )
        self.current_pipeline.total_execution_time_ms = total_time

        # Calculate pipeline efficiency metrics
        self.current_pipeline.pipeline_efficiency = self._calculate_efficiency_metrics()

        # Add entities to pipeline
        self.current_pipeline.entities = list(self.entity_registry.values())
        self.current_pipeline.final_entity_count = len(
            [e for e in self.current_pipeline.entities if e.is_selected]
        )

        result = self.current_pipeline

        # Clean up
        self.debug_session_active = False
        self.current_pipeline = None
        self.entity_registry.clear()

        logger.debug(
            f"Finished debug session: {result.final_entity_count} entities, "
            f"{total_time:.1f}ms total"
        )

        return result

    def _calculate_efficiency_metrics(self) -> Dict[str, float]:
        """Calculate pipeline efficiency metrics."""
        metrics = {}

        if not self.current_pipeline.stage_results:
            return metrics

        # Cluster hit rate
        cluster_stage = next(
            (
                s
                for s in self.current_pipeline.stage_results
                if s.stage == PipelineStage.CLUSTER_SEARCH
            ),
            None,
        )
        vector_stage = next(
            (
                s
                for s in self.current_pipeline.stage_results
                if s.stage == PipelineStage.VECTOR_FALLBACK
            ),
            None,
        )

        if cluster_stage and vector_stage:
            total_entities = cluster_stage.entities_out + vector_stage.entities_out
            if total_entities > 0:
                metrics["cluster_hit_rate"] = (
                    cluster_stage.entities_out / total_entities
                )

        # Reranking impact
        entities_with_scores = [
            e for e in self.entity_registry.values() if e.score_delta is not None
        ]
        if entities_with_scores:
            total_delta = sum(
                e.score_delta for e in entities_with_scores if e.score_delta is not None
            )
            avg_score_delta = total_delta / len(entities_with_scores)
            metrics["avg_reranking_boost"] = avg_score_delta

        # Active vs inactive ratio
        active_entities = [e for e in self.entity_registry.values() if e.is_active]
        inactive_entities = [
            e for e in self.entity_registry.values() if e.is_active is False
        ]
        total_entities = len(active_entities) + len(inactive_entities)

        if total_entities > 0:
            metrics["active_entity_ratio"] = len(active_entities) / total_entities

        # Prompt inclusion rate
        in_prompt_entities = [e for e in self.entity_registry.values() if e.in_prompt]
        if len(self.entity_registry) > 0:
            metrics["prompt_inclusion_rate"] = len(in_prompt_entities) / len(
                self.entity_registry
            )

        return metrics

    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get a summary of the current pipeline state."""
        if not self.current_pipeline:
            return {}

        return {
            "query": self.current_pipeline.query,
            "stages_completed": len(self.current_pipeline.stage_results),
            "entities_tracked": len(self.entity_registry),
            "debug_active": self.debug_session_active,
        }


# Global search debugger instance
search_debugger = SearchDebugger()
