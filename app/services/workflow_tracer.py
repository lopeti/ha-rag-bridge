"""
Workflow Tracer Service for comprehensive pipeline debugging and visualization.
Captures every step of the LangGraph Phase 3 workflow for analysis.
"""

import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from arango import ArangoClient
from ha_rag_bridge.logging import get_logger
import os

logger = get_logger(__name__)


@dataclass
class NodeExecution:
    """Single node execution trace."""

    node_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, success, error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "node_name": self.node_name,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "errors": self.errors,
            "status": self.status,
        }


@dataclass
class EntityStageInfo:
    """Entity information at different pipeline stages."""

    stage: str
    entity_count: int
    entities: List[Dict[str, Any]] = field(default_factory=list)
    scores: Dict[str, Any] = field(default_factory=dict)
    filters_applied: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "stage": self.stage,
            "entity_count": self.entity_count,
            "entities": self.entities,
            "scores": self.scores,
            "filters_applied": self.filters_applied,
            "metadata": self.metadata,
        }


@dataclass
class EnhancedPipelineStage:
    """Detailed pipeline stage with comprehensive information."""

    stage_name: str
    stage_type: str  # "transform", "search", "filter", "rank", "boost"
    input_count: int
    output_count: int
    duration_ms: float

    # Stage-specific details
    query_rewrite: Optional[Dict[str, Any]] = None
    conversation_summary: Optional[Dict[str, Any]] = None
    memory_stage: Optional[Dict[str, Any]] = None
    cluster_search: Optional[Dict[str, Any]] = None
    vector_search: Optional[Dict[str, Any]] = None
    memory_boost: Optional[Dict[str, Any]] = None
    reranking: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "stage_name": self.stage_name,
            "stage_type": self.stage_type,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "duration_ms": self.duration_ms,
            "details": {
                k: v
                for k, v in {
                    "query_rewrite": self.query_rewrite,
                    "conversation_summary": self.conversation_summary,
                    "memory_stage": self.memory_stage,
                    "cluster_search": self.cluster_search,
                    "vector_search": self.vector_search,
                    "memory_boost": self.memory_boost,
                    "reranking": self.reranking,
                }.items()
                if v is not None
            },
        }


@dataclass
class WorkflowTrace:
    """Complete workflow execution trace."""

    trace_id: str
    session_id: str
    user_query: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration_ms: Optional[float] = None

    # External request information
    openwebui_request: Dict[str, Any] = field(default_factory=dict)
    litellm_request: Dict[str, Any] = field(default_factory=dict)

    # Workflow execution
    node_executions: List[NodeExecution] = field(default_factory=list)
    workflow_state: Dict[str, Any] = field(default_factory=dict)
    final_result: Dict[str, Any] = field(default_factory=dict)

    # Entity pipeline tracking
    entity_pipeline: List[EntityStageInfo] = field(default_factory=list)

    # Enhanced pipeline tracking
    enhanced_pipeline_stages: List[EnhancedPipelineStage] = field(default_factory=list)

    # Performance and diagnostics
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, success, error

    # API response tracking
    api_response: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for ArangoDB storage."""
        return {
            "_key": f"trace_{self.trace_id}",
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_query": self.user_query,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_ms": self.total_duration_ms,
            "openwebui_request": self.openwebui_request,
            "litellm_request": self.litellm_request,
            "node_executions": [node.to_dict() for node in self.node_executions],
            "workflow_state": self.workflow_state,
            "final_result": self.final_result,
            "entity_pipeline": [stage.to_dict() for stage in self.entity_pipeline],
            "enhanced_pipeline_stages": [
                stage.to_dict() for stage in self.enhanced_pipeline_stages
            ],
            "performance_metrics": self.performance_metrics,
            "errors": self.errors,
            "status": self.status,
            "api_response": self.api_response,
        }


class WorkflowTracer:
    """Service for tracing and storing workflow executions."""

    def __init__(self):
        """Initialize tracer with database connection."""
        self.db = None
        self.active_traces: Dict[str, WorkflowTrace] = {}
        self._init_database()

    def _init_database(self):
        """Initialize ArangoDB connection and collections."""
        try:
            arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
            db_name = os.getenv("ARANGO_DB", "_system")
            self.db = arango.db(
                db_name,
                username=os.environ["ARANGO_USER"],
                password=os.environ["ARANGO_PASS"],
            )

            # Ensure workflow_traces collection exists
            if not self.db.has_collection("workflow_traces"):
                self.db.create_collection("workflow_traces")
                logger.info("Created workflow_traces collection")

        except Exception as e:
            logger.error(f"Failed to initialize tracer database: {e}")
            self.db = None

    def start_trace(
        self,
        session_id: str,
        user_query: str,
        openwebui_request: Optional[Dict[str, Any]] = None,
        litellm_request: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a new workflow trace."""
        trace_id = str(uuid.uuid4())

        trace = WorkflowTrace(
            trace_id=trace_id,
            session_id=session_id,
            user_query=user_query,
            start_time=datetime.now(timezone.utc),
            openwebui_request=openwebui_request or {},
            litellm_request=litellm_request or {},
            status="running",
        )

        self.active_traces[trace_id] = trace
        logger.info(f"Started workflow trace: {trace_id} for session: {session_id}")

        return trace_id

    def start_node(self, trace_id: str, node_name: str, input_data: Dict[str, Any]):
        """Record start of node execution."""
        if trace_id not in self.active_traces:
            logger.warning(f"Trace not found: {trace_id}")
            return

        trace = self.active_traces[trace_id]

        node_execution = NodeExecution(
            node_name=node_name,
            start_time=datetime.now(timezone.utc),
            input_data=self._sanitize_data(input_data),
            status="running",
        )

        trace.node_executions.append(node_execution)
        logger.debug(f"Started node {node_name} in trace {trace_id}")

    def end_node(
        self,
        trace_id: str,
        node_name: str,
        output_data: Dict[str, Any],
        errors: Optional[List[str]] = None,
    ):
        """Record end of node execution."""
        if trace_id not in self.active_traces:
            logger.warning(f"Trace not found: {trace_id}")
            return

        trace = self.active_traces[trace_id]

        # Find the most recent node execution with this name
        for node in reversed(trace.node_executions):
            if node.node_name == node_name and node.status == "running":
                node.end_time = datetime.now(timezone.utc)
                node.duration_ms = (
                    node.end_time - node.start_time
                ).total_seconds() * 1000
                node.output_data = self._sanitize_data(output_data)
                node.errors = errors or []
                node.status = "error" if errors else "success"

                logger.debug(
                    f"Ended node {node_name} in trace {trace_id} ({node.duration_ms:.1f}ms)"
                )
                break

    def record_entity_stage(
        self,
        trace_id: str,
        stage: str,
        entities: List[Dict[str, Any]],
        scores: Optional[Dict[str, Any]] = None,
        filters_applied: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record entity pipeline stage information."""
        if trace_id not in self.active_traces:
            logger.warning(f"Trace not found: {trace_id}")
            return

        trace = self.active_traces[trace_id]

        entity_stage = EntityStageInfo(
            stage=stage,
            entity_count=len(entities),
            entities=self._sanitize_entities(entities),
            scores=scores or {},
            filters_applied=filters_applied or [],
            metadata=metadata or {},
        )

        trace.entity_pipeline.append(entity_stage)
        logger.debug(f"Recorded entity stage {stage} with {len(entities)} entities")

    def update_workflow_state(self, trace_id: str, state_update: Dict[str, Any]):
        """Update workflow state."""
        if trace_id not in self.active_traces:
            logger.warning(f"Trace not found: {trace_id}")
            return

        trace = self.active_traces[trace_id]
        trace.workflow_state.update(self._sanitize_data(state_update))

    def add_enhanced_pipeline_stage(self, trace_id: str, stage: EnhancedPipelineStage):
        """Add enhanced pipeline stage information to trace."""
        if trace_id not in self.active_traces:
            logger.warning(f"Trace not found: {trace_id}")
            return

        trace = self.active_traces[trace_id]
        trace.enhanced_pipeline_stages.append(stage)
        logger.debug(
            f"Added enhanced pipeline stage '{stage.stage_name}' to trace {trace_id}"
        )

    def update_api_response(self, trace_id: str, api_response: Dict[str, Any]):
        """Update the API response in the trace for debugging purposes."""
        # First try active traces
        if trace_id in self.active_traces:
            trace = self.active_traces[trace_id]
            # Sanitize API response to remove potentially large data
            sanitized_response = self._sanitize_api_response(api_response)
            trace.api_response = sanitized_response
            logger.debug(f"Updated API response for active trace {trace_id}")
            return

        # If trace is not active, update it directly in the database
        if not self.db:
            logger.warning("Cannot update API response: database not available")
            return

        try:
            # Sanitize API response
            sanitized_response = self._sanitize_api_response(api_response)

            # Update the stored trace in database
            trace_key = f"trace_{trace_id}"
            trace_doc = self.db.collection("workflow_traces").get(trace_key)
            if trace_doc:
                trace_doc["api_response"] = sanitized_response
                self.db.collection("workflow_traces").update(trace_doc)
                logger.debug(f"Updated API response for completed trace {trace_id}")
            else:
                logger.warning(f"Trace document not found in database: {trace_id}")

        except Exception as e:
            logger.warning(f"Failed to update API response for trace {trace_id}: {e}")

    def _sanitize_api_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize API response to store only essential debugging information."""
        sanitized: Dict[str, Any] = {}

        # Store response metadata
        sanitized["response_type"] = type(response).__name__
        sanitized["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Store essential fields for debugging
        essential_fields = [
            "relevant_entities",
            "formatted_content",
            "intent",
            "messages",
            "metadata",
        ]

        for essential_field in essential_fields:
            if essential_field in response:
                if essential_field == "relevant_entities":
                    # Store simplified entity information
                    entities = response[essential_field]
                    sanitized[essential_field] = []
                    for entity in entities[:10]:  # Limit to 10 entities
                        if hasattr(entity, "__dict__"):
                            # Handle EntityInfo objects
                            sanitized[essential_field].append(
                                {
                                    "entity_id": getattr(
                                        entity, "entity_id", "unknown"
                                    ),
                                    "domain": getattr(entity, "domain", "unknown"),
                                    "area_name": getattr(entity, "area_name", None),
                                    "similarity": round(
                                        getattr(entity, "similarity", 0.0), 3
                                    ),
                                    "is_primary": getattr(entity, "is_primary", False),
                                }
                            )
                        elif isinstance(entity, dict):
                            # Handle dict entities
                            sanitized[essential_field].append(
                                {
                                    "entity_id": entity.get("entity_id", "unknown"),
                                    "domain": entity.get("domain", "unknown"),
                                    "area_name": entity.get("area_name"),
                                    "similarity": round(
                                        entity.get("similarity", 0.0), 3
                                    ),
                                    "is_primary": entity.get("is_primary", False),
                                }
                            )
                elif essential_field == "formatted_content":
                    # Store content length and preview
                    content = response[essential_field]
                    sanitized[essential_field] = {
                        "length": len(str(content)),
                        "preview": (
                            str(content)[:200] + "..."
                            if len(str(content)) > 200
                            else str(content)
                        ),
                    }
                elif essential_field == "messages":
                    # Store message count and types
                    messages = response[essential_field]
                    sanitized[essential_field] = []
                    for msg in messages[:3]:  # Limit to first 3 messages
                        if hasattr(msg, "__dict__"):
                            sanitized[essential_field].append(
                                {
                                    "role": getattr(msg, "role", "unknown"),
                                    "content_length": len(
                                        str(getattr(msg, "content", ""))
                                    ),
                                    "content_preview": str(getattr(msg, "content", ""))[
                                        :100
                                    ]
                                    + "...",
                                }
                            )
                        elif isinstance(msg, dict):
                            sanitized[essential_field].append(
                                {
                                    "role": msg.get("role", "unknown"),
                                    "content_length": len(str(msg.get("content", ""))),
                                    "content_preview": str(msg.get("content", ""))[:100]
                                    + "...",
                                }
                            )
                else:
                    # For other fields, use sanitize_data
                    sanitized[essential_field] = self._sanitize_data(
                        response[essential_field], max_depth=2
                    )

        return sanitized

    def end_trace(
        self,
        trace_id: str,
        final_result: Dict[str, Any],
        errors: Optional[List[str]] = None,
    ) -> Optional[WorkflowTrace]:
        """End workflow trace and store to database."""
        if trace_id not in self.active_traces:
            logger.warning(f"Trace not found: {trace_id}")
            return None

        trace = self.active_traces[trace_id]
        trace.end_time = datetime.now(timezone.utc)
        trace.total_duration_ms = (
            trace.end_time - trace.start_time
        ).total_seconds() * 1000
        # Store only essential final result data to reduce trace size
        detected_scope = final_result.get("detected_scope")
        sanitized_final_result = {
            "user_query": final_result.get("user_query"),
            "session_id": final_result.get("session_id"),
            "conversation_context": final_result.get("conversation_context"),
            "detected_scope": (
                detected_scope.value
                if detected_scope and hasattr(detected_scope, "value")
                else str(detected_scope) if detected_scope else None
            ),  # Handle QueryScope enum
            "scope_confidence": final_result.get("scope_confidence"),
            "optimal_k": final_result.get("optimal_k"),
            "entity_count": len(
                final_result.get("retrieved_entities", [])
            ),  # Store count, not full entities
            "formatter_type": final_result.get("formatter_type"),
            "formatted_context_length": len(
                str(final_result.get("formatted_context", ""))
            ),  # Store length, not full content
            "errors": final_result.get("errors", []),
            "retry_count": final_result.get("retry_count", 0),
            "fallback_used": final_result.get("fallback_used", False),
        }
        trace.final_result = sanitized_final_result
        trace.errors = errors or []
        trace.status = "error" if errors else "success"

        # Calculate performance metrics
        trace.performance_metrics = self._calculate_metrics(trace)

        # Store to database
        self._store_trace(trace)

        # Remove from active traces
        del self.active_traces[trace_id]

        logger.info(f"Completed trace {trace_id} ({trace.total_duration_ms:.1f}ms)")
        return trace

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get trace by ID from database."""
        if not self.db:
            return None

        try:
            doc = self.db.collection("workflow_traces").get(f"trace_{trace_id}")
            return doc
        except Exception as e:
            logger.error(f"Failed to get trace {trace_id}: {e}")
            return None

    def get_recent_traces(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent traces."""
        if not self.db:
            return []

        try:
            cursor = self.db.aql.execute(
                """
                FOR trace IN workflow_traces
                    SORT trace.start_time DESC
                    LIMIT @limit
                    RETURN trace
                """,
                bind_vars={"limit": limit},
            )
            return list(cursor)
        except Exception as e:
            logger.error(f"Failed to get recent traces: {e}")
            return []

    def _sanitize_data(self, data: Any, max_depth: int = 3) -> Any:
        """Sanitize data for storage, preventing circular references and non-serializable objects."""
        if max_depth <= 0:
            return str(data)

        if isinstance(data, dict):
            # Special handling for entity objects with embeddings
            if "entity_id" in data and "embedding" in data:
                # This is an entity - use specialized sanitization
                return self._sanitize_single_entity(data)
            else:
                # Check for common entity list keys and sanitize them specially
                sanitized = {}
                for k, v in data.items():
                    if k in [
                        "retrieved_entities",
                        "cluster_entities",
                        "memory_entities",
                        "reranked_entities",
                    ] and isinstance(v, list):
                        # These are entity lists - use specialized sanitization
                        sanitized[k] = self._sanitize_entities(v)
                    else:
                        sanitized[k] = self._sanitize_data(v, max_depth - 1)
                return sanitized
        elif isinstance(data, list):
            # Check if this looks like a list of entities
            if data and isinstance(data[0], dict) and "entity_id" in data[0]:
                return self._sanitize_entities(data)
            else:
                return [self._sanitize_data(item, max_depth - 1) for item in data]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        elif hasattr(data, "__dict__"):
            # Handle objects with attributes (like QueryScope enum)
            if hasattr(data, "value"):
                return data.value  # For enum objects, use their value
            else:
                return str(data)
        else:
            return str(data)

    def _sanitize_single_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize a single entity object, removing embedding vector."""
        return {
            "entity_id": entity.get("entity_id"),
            "domain": entity.get("domain"),
            "area": entity.get("area") or entity.get("area_name"),
            "_score": (
                round(entity.get("_score", 0.0), 3) if entity.get("_score") else None
            ),
            "state": (
                str(entity.get("state", ""))[:50] if entity.get("state") else None
            ),
            "_memory_boosted": entity.get("_memory_boosted", False),
            "embedding_dim": len(entity["embedding"]) if entity.get("embedding") else 0,
            # Include other small metadata but exclude embedding vector
            "similarity": (
                round(entity.get("similarity", 0.0), 3)
                if entity.get("similarity")
                else None
            ),
            "is_primary": entity.get("is_primary", False),
        }

    def _sanitize_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Sanitize entity data for storage, keeping only essential fields."""
        sanitized = []

        # Limit to first 20 entities and only store essential data to reduce trace size
        for entity in entities[:20]:
            sanitized_entity = {
                "entity_id": entity.get("entity_id"),
                "domain": entity.get("domain"),
                "area": entity.get("area") or entity.get("area_name"),
                "_score": round(
                    entity.get("_score", 0.0), 3
                ),  # Round score to 3 decimals
                "state": (
                    str(entity.get("state", ""))[:50] if entity.get("state") else None
                ),  # Limit state length
                "_memory_boosted": entity.get("_memory_boosted", False),
                # IMPORTANT: Exclude embedding vector to reduce trace size (768 dims = ~3KB each)
                # "embedding": entity.get("embedding"),  # REMOVED - too large for debugging
                "embedding_dim": (
                    len(entity["embedding"]) if entity.get("embedding") else 0
                ),  # Just store dimension count
            }

            # Store simplified cluster context
            if "_cluster_context" in entity:
                cluster_ctx = entity["_cluster_context"]
                if isinstance(cluster_ctx, dict):
                    sanitized_entity["_cluster_context"] = {
                        "cluster_key": cluster_ctx.get("cluster_key"),
                        "role": cluster_ctx.get("role"),
                        "weight": round(cluster_ctx.get("weight", 0.0), 2),
                    }

            # Store simplified ranking factors (only scores, not full details)
            if "_ranking_factors" in entity:
                factors = entity["_ranking_factors"]
                if isinstance(factors, dict):
                    sanitized_entity["_ranking_factors"] = {
                        "final_score": round(factors.get("final_score", 0.0), 3),
                        "semantic_score": round(factors.get("semantic_score", 0.0), 3),
                        "memory_boost": round(factors.get("memory_boost", 0.0), 2),
                    }

            sanitized.append(sanitized_entity)

        return sanitized

    def _calculate_metrics(self, trace: WorkflowTrace) -> Dict[str, Any]:
        """Calculate performance metrics from trace."""
        metrics: Dict[str, Any] = {
            "total_nodes": len(trace.node_executions),
            "successful_nodes": len(
                [n for n in trace.node_executions if n.status == "success"]
            ),
            "failed_nodes": len(
                [n for n in trace.node_executions if n.status == "error"]
            ),
            "node_times": {},
        }

        # Calculate time spent in each node
        for node in trace.node_executions:
            if node.duration_ms is not None:
                metrics["node_times"][node.node_name] = node.duration_ms

        # Entity pipeline metrics
        if trace.entity_pipeline:
            metrics["entity_stages"] = len(trace.entity_pipeline)
            metrics["final_entity_count"] = (
                trace.entity_pipeline[-1].entity_count if trace.entity_pipeline else 0
            )

        return metrics

    def _store_trace(self, trace: WorkflowTrace):
        """Store trace to database."""
        if not self.db:
            logger.warning("Database not available, trace not stored")
            return

        try:
            self.db.collection("workflow_traces").insert(trace.to_dict())
            logger.debug(f"Stored trace {trace.trace_id} to database")
        except Exception as e:
            logger.error(f"Failed to store trace {trace.trace_id}: {e}")


# Global tracer instance
workflow_tracer = WorkflowTracer()
