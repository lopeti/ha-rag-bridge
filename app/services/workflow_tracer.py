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

    # Performance and diagnostics
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, success, error

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
            "performance_metrics": self.performance_metrics,
            "errors": self.errors,
            "status": self.status,
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
        trace.final_result = self._sanitize_data(final_result)
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
        """Sanitize data for storage, preventing circular references."""
        if max_depth <= 0:
            return str(data)

        if isinstance(data, dict):
            return {k: self._sanitize_data(v, max_depth - 1) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_data(item, max_depth - 1) for item in data]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            return str(data)

    def _sanitize_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Sanitize entity data for storage, keeping only essential fields."""
        sanitized = []

        for entity in entities:
            sanitized_entity = {
                "entity_id": entity.get("entity_id"),
                "domain": entity.get("domain"),
                "area": entity.get("area") or entity.get("area_name"),
                "_score": entity.get("_score", 0.0),
                "state": entity.get("state"),
                "_memory_boosted": entity.get("_memory_boosted", False),
                "_cluster_context": entity.get("_cluster_context"),
            }

            # Include ranking factors if available
            if "_ranking_factors" in entity:
                sanitized_entity["_ranking_factors"] = entity["_ranking_factors"]

            sanitized.append(sanitized_entity)

        return sanitized

    def _calculate_metrics(self, trace: WorkflowTrace) -> Dict[str, Any]:
        """Calculate performance metrics from trace."""
        metrics = {
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
