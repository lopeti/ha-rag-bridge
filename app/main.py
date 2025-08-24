import re
import json
import uuid
from typing import List, Sequence, Dict, Any, Optional, Union
from datetime import datetime, timezone
from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from ha_rag_bridge.logging import get_logger
from ha_rag_bridge.config import get_settings
from ha_rag_bridge.similarity_config import get_current_config
from app.middleware.request_id import request_id_middleware

# Import the new RAG strategy system
from app.rag_strategies import registry, StrategyConfig
from app.conversation_utils import extract_messages

logger = get_logger(__name__)

# Global debug session management
debug_sessions: Dict[str, bool] = {}
debug_results: Dict[str, Dict[str, Any]] = {}

from .routers.graph import router as graph_router  # noqa: E402
from .routers.admin import router as admin_router  # noqa: E402
from .routers.ui import router as ui_router  # noqa: E402
import httpx  # noqa: E402

from arango import ArangoClient  # noqa: E402

from . import schemas  # noqa: E402
from app.services.integrations.embeddings import (  # noqa: E402
    BaseEmbeddingBackend as EmbeddingBackend,
    LocalBackend,
    OpenAIBackend,
    GeminiBackend,
    get_backend,
)
from .services.core.state_service import get_last_state  # noqa: E402
from .services.core.service_catalog import ServiceCatalog  # noqa: E402
from .services.rag.entity_reranker import entity_reranker  # noqa: E402

# Import LangGraph workflow at module level to avoid route registration issues
try:
    from .langgraph_workflow.workflow import run_rag_workflow

    LANGGRAPH_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LangGraph workflow not available: {e}")
    LANGGRAPH_AVAILABLE = False

app = FastAPI()
router = APIRouter()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(BaseHTTPMiddleware, dispatch=request_id_middleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to log all unhandled exceptions."""
    logger.error(
        "Unhandled exception occurred",
        method=request.method,
        url=str(request.url),
        exc_info=exc,
        error=str(exc),
    )
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error occurred"}
    )


# Initialize settings
settings = get_settings()

service_catalog = ServiceCatalog(settings.service_cache_ttl)

# Cache embedding backends globally to avoid reloading models
_cached_backends: Dict[str, EmbeddingBackend] = {}

if settings.auto_bootstrap:
    from ha_rag_bridge.bootstrap import bootstrap

    bootstrap()

backend_name = settings.embedding_backend.lower()
if backend_name == "gemini":
    backend_dim = GeminiBackend.DIMENSION
elif backend_name == "openai":
    backend_dim = OpenAIBackend.DIMENSION
else:
    backend_dim = LocalBackend.DIMENSION
HEALTH_ERROR: str | None = None

if not settings.skip_arango_healthcheck:
    try:
        arango_url = settings.arango_url
        arango_user = settings.arango_user
        arango_pass = settings.arango_pass

        arango = ArangoClient(hosts=arango_url)
        db_name = settings.arango_db
        db = arango.db(
            db_name,
            username=arango_user,
            password=arango_pass,
        )
        col = db.collection("entity")
        idx = next(
            (
                i
                for i in col.indexes()
                if i["type"] == "vector" and i["fields"][0] == "embedding"
            ),
            None,
        )
        if idx and idx.get("dimensions") != backend_dim:
            idx_dim = idx.get("dimensions")
            if idx_dim is None:
                idx_dim = idx.get("params", {}).get("dimension")

            if idx_dim is None:
                logger.warning("vector index found, but no dimension info")
            elif idx_dim != backend_dim:
                logger.warning(
                    "embedding dimension mismatch",
                    backend=backend_dim,
                    index=idx_dim,
                )
                HEALTH_ERROR = "dimension mismatch"
    except KeyError:
        pass
    except Exception as exc:  # pragma: no cover - db errors
        logger.warning("Health check init failed", error=str(exc))
        HEALTH_ERROR = "dimension check failed"

CONTROL_RE = re.compile(
    r"\b(kapcsold|ind\xEDtsd|\xE1ll\xEDtsd|turn\s+on|turn\s+off)\b", re.IGNORECASE
)
READ_RE = re.compile(
    r"\b(mennyi|h\xE1ny|milyen|fok|temperature|status)\b", re.IGNORECASE
)


def detect_intent(text: str) -> str:
    """Return simple intent based on regex patterns."""
    if CONTROL_RE.search(text):
        return "control"
    return "read"


def get_embedding_backend(backend_name: str) -> EmbeddingBackend:
    """Get cached embedding backend instance."""
    if backend_name not in _cached_backends:
        logger.info(f"Initializing embedding backend: {backend_name}")
        if backend_name == "openai":
            _cached_backends[backend_name] = OpenAIBackend()
        elif backend_name == "local":
            _cached_backends[backend_name] = LocalBackend()
        else:
            _cached_backends[backend_name] = get_backend(backend_name)
    return _cached_backends[backend_name]


def query_arango(
    db, q_vec: Sequence[float], q_text: str, k: int, nprobe: int = 4
) -> List[dict]:
    aql = (
        "LET knn = ("
        "FOR e IN entity "
        "FILTER LENGTH(e.embedding) > 0 "
        "LET score = COSINE_SIMILARITY(e.embedding, @qv) "
        "SORT score DESC "
        "LIMIT @k "
        "RETURN MERGE(e, {_score: score})) "
        "LET txt = ("
        "FOR e IN v_meta "
        "SEARCH ANALYZER(PHRASE(e.text_system, @msg, 'text_en'), 'text_en') "
        "SORT BM25(e) DESC "
        "LIMIT @k "
        "RETURN MERGE(e, {_score: BM25(e)})) "
        "FOR e IN UNIQUE(UNION(knn, txt)) "
        "LIMIT @k "
        "RETURN e"
    )
    cursor = db.aql.execute(aql, bind_vars={"qv": q_vec, "msg": q_text, "k": k})
    return list(cursor)


def query_arango_text_only(db, q_text: str, k: int) -> List[dict]:
    aql = (
        "FOR e IN v_meta "
        "SEARCH ANALYZER(PHRASE(e.text_system, @msg, 'text_en'), 'text_en') "
        "SORT BM25(e) DESC "
        f"LIMIT {k} "
        "RETURN e"
    )
    cursor = db.aql.execute(aql, bind_vars={"msg": q_text})
    return list(cursor)


def query_manual(
    db, doc_id: str, q_vec: Sequence[float], q_text: str, k: int = 2, nprobe: int = 4
) -> List[str]:
    aql = (
        "LET knn = ("
        "FOR d IN document "
        "FILTER d.document_id == @doc AND LENGTH(d.embedding) > 0 "
        "LET score = COSINE_SIMILARITY(d.embedding, @qv) "
        "SORT score DESC "
        "LIMIT @k "
        "RETURN d.text) "
        "LET txt = ("
        "FOR d IN v_manual "
        "SEARCH d.document_id == @doc AND ANALYZER(PHRASE(d.text, @msg, 'text_en'), 'text_en') "
        "SORT BM25(d) DESC "
        "LIMIT @k "
        "RETURN d.text) "
        "FOR t IN UNIQUE(UNION(knn, txt)) "
        "LIMIT @k "
        "RETURN t"
    )
    cursor = db.aql.execute(
        aql,
        bind_vars={
            "doc": doc_id,
            "qv": q_vec,
            "msg": q_text,
            "k": k,
        },
    )
    return list(cursor)


def service_to_tool(domain: str, name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a service spec to a tool definition."""
    return {
        "type": "function",
        "function": {
            "name": f"{domain}.{name}",
            "parameters": {
                "type": "object",
                "properties": spec.get("fields", {}),
                "required": [
                    k for k, v in spec.get("fields", {}).items() if v.get("required")
                ],
            },
        },
    }


def retrieve_entities(
    db, q_vec: Sequence[float], q_text: str, k_list=(15, 15)
) -> List[dict]:
    """Legacy retrieve_entities function for fallback compatibility."""
    for k in k_list:
        ents = query_arango(db, q_vec, q_text, k)
        if len(ents) >= 2:
            return ents
    return query_arango_text_only(db, q_text, 10)


def retrieve_entities_with_clusters(
    db,
    q_vec: Sequence[float],
    q_text: str,
    scope_config,
    cluster_types: List[str],
    k: int = 15,
    conversation_context: Optional[dict] = None,
) -> List[dict]:
    """Enhanced entity retrieval with cluster-first logic.

    Args:
        db: ArangoDB database connection
        q_vec: Query embedding vector
        q_text: Query text
        scope_config: Query scope configuration
        cluster_types: Types of clusters to search
        k: Number of entities to retrieve
        conversation_context: Optional conversation context

    Returns:
        List of relevant entities prioritized by semantic clusters
    """
    from .services.rag.cluster_manager import cluster_manager

    try:
        # Phase 1: Search for relevant clusters
        relevant_clusters = cluster_manager.search_clusters(
            query_vector=list(q_vec),
            cluster_types=cluster_types,
            k=min(5, k // 3),  # Search fewer clusters but expand to more entities
            threshold=scope_config.threshold,
        )

        cluster_entities = []
        if relevant_clusters:
            # Phase 2: Expand clusters to entities
            cluster_keys = [c["_key"] for c in relevant_clusters]
            cluster_entities = cluster_manager.get_cluster_entities(cluster_keys)

            # Apply cluster boost to entity scores
            for ce in cluster_entities:
                entity = ce["entity"]
                # Add cluster context metadata
                entity["_cluster_context"] = {
                    "cluster_key": ce["cluster_key"],
                    "role": ce["role"],
                    "weight": ce["weight"],
                    "context_boost": ce["context_boost"],
                }

            logger.debug(
                f"Cluster-first retrieval found {len(cluster_entities)} entities "
                f"from {len(relevant_clusters)} clusters"
            )

        # Phase 3: Hybrid fallback - combine cluster entities with vector search
        cluster_entity_ids = {
            ce["entity"]["entity_id"]
            for ce in cluster_entities
            if ce["entity"].get("entity_id")
        }

        # Multi-stage retrieval: broad → rerank → filter
        # Stage 1: Broad retrieval (3x target k for better candidate pool)
        broad_k = k * 3  # Get 3x more entities initially
        vector_entities = query_arango(db, q_vec, q_text, broad_k)

        # Combine results, prioritizing cluster entities
        combined_entities = []

        # Add cluster entities first
        combined_entities.extend([ce["entity"] for ce in cluster_entities])

        # Add vector entities that aren't already in cluster results
        for ve in vector_entities:
            if ve.get("entity_id") not in cluster_entity_ids:
                combined_entities.append(ve)
                # Don't limit here - we want the full broad candidate pool

        # If still not enough entities, use text-only fallback
        if len(combined_entities) < 2:
            logger.debug("Falling back to text-only search")
            return query_arango_text_only(db, q_text, k)

        logger.info(
            f"Enhanced retrieval: {len(cluster_entities)} from clusters, "
            f"{len(combined_entities) - len(cluster_entities)} from vector search, "
            f"total candidates: {len(combined_entities)} (target: {k})"
        )

        # Return full candidate pool for reranking - reranker will filter down to k
        return combined_entities

    except Exception as exc:
        logger.warning(
            f"Cluster-first retrieval failed, falling back to vector search: {exc}"
        )
        # Fallback to original logic
        return retrieve_entities(db, q_vec, q_text, (k, k))


@router.get("/health")
async def health():
    if HEALTH_ERROR:
        raise HTTPException(status_code=500, detail=HEALTH_ERROR)
    return {"status": "ok"}


@router.get("/similarity-config")
async def get_similarity_config():
    """Get current similarity threshold configuration."""
    return get_current_config()


@router.post("/process-request", response_model=schemas.ProcessResponse)
async def process_request(payload: schemas.Request):
    backend_name = settings.embedding_backend.lower()
    emb_backend = get_embedding_backend(backend_name)

    try:
        # Run sync embedding in thread executor to avoid asyncio conflicts
        import asyncio

        loop = asyncio.get_event_loop()
        query_vector = await loop.run_in_executor(
            None, lambda: emb_backend.embed([payload.user_message])[0]
        )
    except Exception as exc:  # pragma: no cover - backend errors
        logger.error(
            "Embedding backend error",
            backend=backend_name,
            message=payload.user_message,
            exc_info=exc,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"Embedding error: {str(exc)}")

    arango = ArangoClient(hosts=settings.arango_url)
    db_name = settings.arango_db
    db = arango.db(
        db_name,
        username=settings.arango_user,
        password=settings.arango_pass,
    )

    intent = detect_intent(payload.user_message)

    # Phase 1: Detect query scope for adaptive retrieval
    from .services.rag.query_scope_detector import query_scope_detector

    try:
        detected_scope, scope_config, detection_details = (
            query_scope_detector.detect_scope(
                payload.user_message,
                conversation_context=None,  # Will be enhanced with conversation analyzer integration
            )
        )

        optimal_k = detection_details["optimal_k"]

        logger.info(
            f"Query scope detection: {detected_scope.value}",
            query=payload.user_message[:50],
            optimal_k=optimal_k,
            confidence=round(detection_details["confidence"], 2),
            formatter=scope_config.formatter,
        )

        # Phase 2: Use cluster-first retrieval with adaptive parameters
        results = retrieve_entities_with_clusters(
            db=db,
            q_vec=query_vector,
            q_text=payload.user_message,
            scope_config=scope_config,
            cluster_types=scope_config.cluster_types,
            k=optimal_k,
            conversation_context=detection_details.get("context_factors", {}),
        )

    except Exception as exc:  # pragma: no cover - db errors
        logger.error(
            "Database query error",
            message=payload.user_message,
            exc_info=exc,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"Database error: {str(exc)}")

    # Use entity reranker for context-aware prioritization
    try:
        logger.info(
            "Starting entity reranking",
            query=payload.user_message,
            entity_count=len(results),
            has_conversation_history=bool(payload.conversation_history),
            conversation_id=payload.conversation_id,
        )

        ranked_entities = entity_reranker.rank_entities(
            entities=results,
            query=payload.user_message,
            conversation_history=payload.conversation_history,
            conversation_id=payload.conversation_id,
            k=min(
                optimal_k, len(results)
            ),  # Use adaptive k but respect available results
        )

        # Log successful reranking
        if ranked_entities:
            top_entity_id = ranked_entities[0].entity.get("entity_id", "unknown")
            top_score = ranked_entities[0].final_score
            logger.info(
                "✅ Entity reranking SUCCESSFUL",
                query=payload.user_message,
                top_entity=top_entity_id,
                top_score=round(top_score, 3),
                ranked_count=len(ranked_entities),
                system_prompt_type="hierarchical",
            )

        # Create hierarchical system prompt with adaptive formatting based on query scope
        system_prompt = entity_reranker.create_hierarchical_system_prompt(
            ranked_entities=ranked_entities,
            query=payload.user_message,
            max_primary=(
                4 if detected_scope.value != "micro" else 2
            ),  # Fewer entities for micro queries
            max_related=(
                6 if detected_scope.value == "overview" else 4
            ),  # More entities for overview
            force_formatter=scope_config.formatter,  # Use scope-detected formatter
        )

        # Add manual hints for primary entity if available
        if ranked_entities:
            primary_entity = ranked_entities[0].entity
            device_id = primary_entity.get("device_id")
            if device_id:
                try:
                    cur = db.aql.execute(
                        "FOR e IN edge FILTER e._from == @d AND e.label == 'device_has_manual' RETURN PARSE_IDENTIFIER(e._to).key",
                        bind_vars={"d": f"device/{device_id}"},
                    )
                    manual_id = next(iter(cur), None)
                    if manual_id:
                        hints = query_manual(
                            db, manual_id, query_vector, payload.user_message
                        )
                        if hints:
                            system_prompt += "\nManual hints:\n"
                            for h in hints:
                                system_prompt += f"- {h}\n"
                except Exception:  # pragma: no cover - db errors
                    pass

        # Extract domains for service catalog (fallback to old logic if reranking fails)
        if ranked_entities:
            domain_set = sorted(
                [
                    domain
                    for entity in ranked_entities[:5]  # Top 5 entities
                    if (domain := entity.entity.get("domain")) is not None
                ]
            )
        else:
            domain_set = sorted(
                [
                    str(domain)
                    for doc in results
                    if (domain := doc.get("domain")) is not None
                ]
            )

    except Exception as exc:
        # Log fallback with detailed error information
        logger.warning(
            "❌ Entity reranking FAILED - using FALLBACK logic",
            query=payload.user_message,
            error=str(exc),
            error_type=type(exc).__name__,
            entity_count=len(results),
            system_prompt_type="legacy_fallback",
        )

        # Fallback to original logic if reranking fails
        ids = [
            str(doc.get("entity_id"))
            for doc in results
            if doc.get("entity_id") is not None
        ]
        comma_sep = ",".join(ids)
        domain_set = sorted(
            [
                str(domain)
                for doc in results
                if (domain := doc.get("domain")) is not None
            ]
        )
        domains = ",".join(domain_set)
        system_prompt = (
            "You are a Home Assistant agent.\n"
            f"Relevant entities: {comma_sep}\n"
            f"Relevant domains: {domains}\n"
        )

        if results:
            top = results[0]
            fallback_entity_id = top.get("entity_id", "unknown")
            logger.info(
                "Using fallback entity selection",
                query=payload.user_message,
                fallback_entity=fallback_entity_id,
                selection_method="first_result",
            )

            if top.get("domain") == "sensor":
                entity_id = top.get("entity_id")
                if entity_id:
                    last = get_last_state(str(entity_id))
                    if last is not None:
                        system_prompt += (
                            f"Current value of {top['entity_id'].lower()}: {last}\n"
                        )

    tools: List[Dict] = []
    if intent == "control":
        for dom in domain_set:
            if dom is not None:  # Ellenőrizzük, hogy a domain nem None
                services = await service_catalog.get_domain_services(str(dom))
                for name, spec in services.items():
                    if name is not None:  # Ellenőrizzük, hogy a name nem None
                        tools.append(service_to_tool(str(dom), name, spec))

    # Cache-friendly approach: static system prompt + dynamic context in user message
    STATIC_SYSTEM_PROMPT = """You are an intelligent home assistant AI with deep understanding of your user's home environment.

**Your Capabilities:**
- Answer questions about home status, device states, and environmental conditions  
- Control smart home devices through available services
- Provide proactive insights and recommendations
- Understand context from previous conversations

**Response Guidelines:**
- Be concise but informative - avoid unnecessary explanations
- When controlling devices, confirm the action taken  
- For status queries, provide current values with context (e.g., "Living room is 22.5°C, which is comfortable")
- If multiple entities are relevant, prioritize the most important ones
- For Hungarian queries, respond in Hungarian; for English queries, respond in English
- When you don't have enough information, ask specific clarifying questions

**Smart Reasoning:**
- Consider relationships between entities (e.g., if heating is on but windows are open)
- Provide seasonal or time-appropriate context when relevant
- Suggest energy-saving or comfort optimizations when appropriate

Help the user efficiently and naturally, as if you truly understand their home."""

    # Dynamic context goes in user message for better LLM caching
    user_message_with_context = f"""Current home context:
{system_prompt}

User question: {payload.user_message}"""

    return {
        "messages": [
            {"role": "system", "content": STATIC_SYSTEM_PROMPT},
            {"role": "user", "content": user_message_with_context},
        ],
        "tools": tools,
    }


@router.post("/process-response", response_model=schemas.ExecResult)
async def process_response(payload: schemas.LLMResponse):
    """Execute tool-calls returned by the LLM and respond with a summary."""
    ha_url = settings.ha_url
    token = settings.ha_token
    if not ha_url or not token:
        raise HTTPException(status_code=500, detail="Missing HA configuration")

    message = payload.choices[0].message
    tool_calls = message.tool_calls or []
    headers = {"Authorization": f"Bearer {token}"}
    errors: List[str] = []

    async with httpx.AsyncClient(
        base_url=ha_url, headers=headers, timeout=settings.http_timeout
    ) as client:
        for call in tool_calls:
            func = call.function
            try:
                args = json.loads(func.arguments)
            except Exception:
                errors.append(func.arguments)
                continue
            domain, service = func.name.split(".", 1)
            ent = args.get("entity_id", func.name)
            try:
                resp = await client.post(f"/api/services/{domain}/{service}", json=args)
                if resp.status_code != 200:
                    errors.append(ent)
            except Exception:
                errors.append(ent)

    if errors:
        ids = ",".join(errors)
        return {"status": "error", "message": f"Nem sikerült végrehajtani: {ids}"}
    return {"status": "ok", "message": message.content}


@router.post("/process-request-workflow")
async def process_request_workflow(payload: schemas.Request):
    """Process request using Phase 3 LangGraph workflow (used by hook integration)."""
    logger.info(
        f"WORKFLOW ENDPOINT CALLED: {payload.user_message if payload else 'no payload'}"
    )

    if not LANGGRAPH_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangGraph workflow not available")

    from . import schemas as app_schemas

    logger.info(
        f"Processing request via Phase 3 workflow: {payload.user_message[:50]}..."
    )

    try:
        # Convert conversation history to the format expected by workflow
        conversation_history = []
        if payload.conversation_history:
            for msg in payload.conversation_history:
                conversation_history.append({"role": msg.role, "content": msg.content})

        # Extract session_id from payload
        session_id = getattr(payload, "session_id", None) or getattr(
            payload, "conversation_id", "default_session"
        )

        logger.info(f"Using session_id: {session_id}")

        # Run the Phase 3 LangGraph workflow
        workflow_result = await run_rag_workflow(
            user_query=payload.user_message,
            session_id=str(session_id),
            conversation_history=conversation_history,
        )

        # Check if workflow returned valid result
        if workflow_result is None:
            logger.error("LangGraph workflow returned None")
            workflow_result = {
                "formatted_context": "Error: Workflow returned empty result",
                "retrieved_entities": [],
                "conversation_context": {"intent": "read"},
                "diagnostics": {"error": "workflow_returned_none"},
                "errors": ["Workflow execution failed"],
            }

        # Ensure workflow_result has required fields with safe defaults
        if not isinstance(workflow_result, dict):
            logger.error(f"Invalid workflow result type: {type(workflow_result)}")
            workflow_result = {
                "formatted_context": "Error: Invalid workflow result",
                "retrieved_entities": [],
                "conversation_context": {"intent": "read"},
                "diagnostics": {"error": "invalid_workflow_result_type"},
                "errors": ["Invalid workflow result type"],
            }

        # Extract results from workflow
        formatted_context = workflow_result.get("formatted_context", "")
        retrieved_entities = workflow_result.get("retrieved_entities", [])
        diagnostics = workflow_result.get("diagnostics", {})
        errors = workflow_result.get("errors", [])

        # Convert entities to the format expected by the response schema
        relevant_entities = []
        for entity in retrieved_entities[:15]:  # Limit to 15 entities
            relevant_entities.append(
                schemas.EntityInfo(
                    entity_id=entity.get("entity_id", "unknown"),
                    name=entity.get(
                        "display_entity_id", entity.get("entity_id", "unknown")
                    ),
                    state=entity.get("state", "unknown"),
                    domain=entity.get("domain", "unknown"),
                    area_name=entity.get("area_name"),
                    similarity=entity.get("_score", entity.get("similarity", 0.0)),
                    aliases=[],  # Phase 3 doesn't use aliases in the same way
                    is_primary=entity.get("_memory_boosted", False),
                )
            )

        # Add Phase 3 diagnostics as metadata
        metadata = None
        if diagnostics:
            logger.info(
                f"Phase 3 workflow quality: {diagnostics.get('overall_quality', 0.0):.2f}"
            )

            metadata = {
                "workflow_quality": diagnostics.get("overall_quality", 0.0),
                "memory_entities_count": len(
                    workflow_result.get("memory_entities", [])
                ),
                "memory_boosted_count": len(
                    [e for e in retrieved_entities if e.get("_memory_boosted")]
                ),
                "entity_count": len(relevant_entities),
                "phase": "3_langgraph_workflow",
            }

        # Build response with Phase 3 enhancements
        response = schemas.ProcessResponse(
            relevant_entities=relevant_entities,
            formatted_content=formatted_context,
            intent=(workflow_result.get("conversation_context") or {}).get(
                "intent", "read"
            ),
            messages=[
                app_schemas.ChatMessage(role="system", content=formatted_context)
            ],
            metadata=metadata,
        )

        # Log workflow errors as warnings
        if errors:
            logger.warning(f"Phase 3 workflow completed with errors: {errors[:3]}")

        # Store API response in trace for debugging
        trace_id = workflow_result.get("trace_id")
        if trace_id:
            try:
                from app.services.core.workflow_tracer import workflow_tracer

                # Convert response to dict for storage
                response_dict = {
                    "relevant_entities": relevant_entities,
                    "formatted_content": formatted_context,
                    "intent": (workflow_result.get("conversation_context") or {}).get(
                        "intent", "read"
                    ),
                    "messages": [{"role": "system", "content": formatted_context}],
                    "metadata": metadata,
                }
                workflow_tracer.update_api_response(trace_id, response_dict)
                logger.debug(f"Stored API response in trace {trace_id}")
            except Exception as e:
                logger.warning(f"Failed to store API response in trace: {e}")

        logger.info(
            f"Phase 3 workflow completed: {len(relevant_entities)} entities, quality={diagnostics.get('overall_quality', 0.0):.2f}"
        )
        return response

    except Exception as exc:
        logger.error(f"Phase 3 workflow error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Phase 3 workflow error: {str(exc)}"
        )


# Initialize strategy config
default_strategy_config = StrategyConfig(
    max_messages=5, user_weight=1.0, assistant_weight=0.5, recency_boost=0.3
)


def is_meta_task(user_msg: str) -> bool:
    """Check if this is an OpenWebUI meta-task (title/tag generation)."""
    return "### Task:" in user_msg and (
        "Generate" in user_msg or "categoriz" in user_msg
    )


def extract_user_query_from_meta_task(user_msg: str) -> str | None:
    """Extract the actual user query from OpenWebUI meta-task format."""
    # Look for chat history section
    chat_history_match = re.search(
        r"<chat_history>(.*?)</chat_history>", user_msg, re.DOTALL
    )
    if not chat_history_match:
        return None

    chat_content = chat_history_match.group(1).strip()

    # Extract the LAST user question (most recent)
    user_questions = re.findall(
        r"USER:\s*(.*?)(?=\nASSISTANT:|$)", chat_content, re.DOTALL
    )

    if user_questions:
        last_question = user_questions[-1].strip()
        return last_question
    else:
        return None


def detect_hook_source(raw_input: str | dict, session_id: Optional[str] = None) -> dict:
    """Detect if this is a hook call and extract source information."""
    debug_info = {
        "source": "manual_test",
        "is_meta_task": False,
        "meta_task_details": None,
        "extracted_query": None,
    }

    # Convert to string if dict
    input_str = str(raw_input)

    # Check if session_id indicates this is from a hook
    is_hook_call = session_id and session_id.startswith("hook_")

    # Check if it's a meta-task (likely from LiteLLM hook)
    if is_meta_task(input_str):
        debug_info["source"] = "litellm_hook"
        debug_info["is_meta_task"] = True

        # Extract meta-task details
        extracted_query = extract_user_query_from_meta_task(input_str)
        if extracted_query:
            debug_info["extracted_query"] = extracted_query

        # Extract task type
        task_match = re.search(r"### Task:\s*(.*?)(?=\n|$)", input_str)
        if task_match:
            task_type = task_match.group(1).strip()
            debug_info["meta_task_details"] = {
                "task_type": task_type,
                "full_meta_task": (
                    input_str[:500] + "..." if len(input_str) > 500 else input_str
                ),
            }
    elif is_hook_call:
        # Direct user query from hook (not meta-task)
        debug_info["source"] = "litellm_hook"
        debug_info["is_meta_task"] = False
        debug_info["extracted_query"] = (
            input_str if len(input_str) < 500 else input_str[:500] + "..."
        )

    return debug_info


@router.post("/process-conversation")
async def process_conversation(
    request: Union[schemas.Request, Dict[str, Any]], include_debug: bool = False
):
    """Process conversation using configurable RAG strategies

    This endpoint supports:
    1. Raw OpenWebUI queries (string with meta-task format)
    2. Structured conversation messages
    3. Legacy single-query format

    Uses strategy pattern for flexible A/B testing of different approaches.
    """

    try:
        # Handle different input formats
        if isinstance(request, dict):
            if "user_message" in request:
                # Legacy format
                raw_input = request["user_message"]
            elif "messages" in request:
                # Already structured messages
                raw_input = request["messages"]
            elif "query" in request:
                # Simple query format
                raw_input = request["query"]
            else:
                # Assume the whole dict is the raw query content
                raw_input = str(request)
        else:
            # ProcessRequestPayload or ProcessWorkflowRequest
            raw_input = request.user_message

        # Extract session_id from request
        if isinstance(request, dict):
            session_id = request.get("session_id") or request.get(
                "conversation_id", "default_session"
            )
        else:
            session_id = getattr(request, "session_id", None) or getattr(
                request, "conversation_id", "default_session"
            )

        logger.info(f"Using session_id: {session_id}")

        # Extract structured messages from input
        if isinstance(raw_input, list):
            # Already a messages array - use directly for conversation processing
            messages = raw_input
            logger.info(f"Using direct messages array: {len(messages)} messages")
        else:
            # String input - needs parsing
            messages = extract_messages(raw_input)
            logger.info(f"Parsed messages from string: {len(messages)} messages")

        if not messages:
            logger.warning(
                f"No valid messages extracted from input: {str(raw_input)[:100]}..."
            )
            return {
                "success": False,
                "error": "No valid messages found in input",
                "entities": [],
                "formatted_content": "",
            }

        logger.info(f"Processing conversation with {len(messages)} messages")

        # Detect hook source and meta-task information
        hook_source_info = detect_hook_source(raw_input, session_id)

        # Check if debug mode is enabled globally or via parameter
        debug_enabled = include_debug or any(debug_sessions.values())

        # Determine strategy (default to hybrid, can be configured)
        if isinstance(request, dict):
            strategy_name = request.get("strategy", "hybrid")
        else:
            strategy_name = getattr(request, "strategy", "hybrid")

        logger.info(f"Using RAG strategy: {strategy_name}")

        debug_info = {}
        if debug_enabled:
            # Start enhanced debug capture
            debug_session_id = str(uuid.uuid4())
            # Calculate message weights for debug display
            from app.conversation_utils.embedding_utils import calculate_message_weights

            # Use the global default_strategy_config defined in this file

            message_weights = []
            if messages:
                try:
                    message_weights = calculate_message_weights(
                        messages, default_strategy_config
                    )
                except Exception as e:
                    logger.warning(f"Failed to calculate message weights: {e}")
                    message_weights = [1.0] * len(messages)

            # Conversation statistics
            conversation_stats = {
                "total_messages": len(messages),
                "user_messages": len([m for m in messages if m.get("role") == "user"]),
                "assistant_messages": len(
                    [m for m in messages if m.get("role") == "assistant"]
                ),
                "system_messages": len(
                    [m for m in messages if m.get("role") == "system"]
                ),
                "conversation_turns": len(
                    [m for m in messages if m.get("role") == "user"]
                ),
                "is_multi_turn": len([m for m in messages if m.get("role") == "user"])
                > 1,
                "message_weights": message_weights,
            }

            debug_info = {
                "session_id": debug_session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "raw_input": (
                    str(raw_input)[:1000] + "..."
                    if len(str(raw_input)) > 1000
                    else str(raw_input)
                ),
                "extracted_messages": messages,
                "conversation_stats": conversation_stats,
                "strategy_name": strategy_name,
                "hook_source_info": hook_source_info,
                "source_label": (
                    "From LiteLLM Hook"
                    if hook_source_info["source"] == "litellm_hook"
                    else "Manual Test"
                ),
                "pipeline_stages": [],
            }

        # Execute strategy using registry
        strategy_result = await registry.execute(
            strategy_name, messages, default_strategy_config
        )

        entities = strategy_result.entities
        execution_time = strategy_result.execution_time_ms

        logger.info(
            f"Strategy '{strategy_result.strategy_used}' retrieved {len(entities)} entities in {execution_time:.1f}ms"
        )

        # Format entities for prompt injection using entity reranker service
        if entities:
            try:
                # Use the entity reranker service to format entities properly
                formatted_content = await entity_reranker.format_entities_for_prompt(
                    entities,
                    force_formatter="compact",  # Use compact format for hook integration
                )
            except Exception as e:
                logger.warning(f"Entity formatting failed, using simple format: {e}")
                # Fallback to simple formatting
                formatted_entities = []
                for entity in entities[:10]:  # Limit to 10 entities
                    entity_text = f"{entity.get('entity_id', 'unknown')}"
                    if entity.get("text"):
                        entity_text += f": {entity['text'][:100]}"
                    if entity.get("state"):
                        entity_text += f" (current: {entity['state']})"
                    formatted_entities.append(entity_text)
                formatted_content = "\n".join(formatted_entities)
        else:
            formatted_content = "No relevant entities found for the conversation."

        # Store enhanced debug info if enabled
        if debug_enabled and debug_info:
            debug_info.update(
                {
                    "strategy_result": {
                        "strategy_used": strategy_result.strategy_used,
                        "execution_time_ms": execution_time,
                        "entity_count": len(entities),
                        "success": strategy_result.success,
                    },
                    "entities": (
                        entities[:15] if entities else []
                    ),  # Store more entities for debugging
                    "formatted_content": (
                        formatted_content[:2000] if formatted_content else ""
                    ),  # More content
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "pipeline_summary": f"{len(entities)} entities retrieved in {execution_time:.1f}ms via {strategy_result.strategy_used}",
                    "processing_info": {
                        "messages_extracted": len(messages),
                        "conversation_turns": len(
                            [m for m in messages if m.get("role") == "user"]
                        ),
                        "is_multi_turn": len(
                            [m for m in messages if m.get("role") == "user"]
                        )
                        > 1,
                        "embedding_strategy": strategy_name,
                        "weights_applied": len(
                            [
                                w
                                for w in debug_info.get("conversation_stats", {}).get(
                                    "message_weights", []
                                )
                                if w > 0
                            ]
                        ),
                        "raw_input_length": len(str(raw_input)),
                        "formatted_content_length": (
                            len(formatted_content) if formatted_content else 0
                        ),
                    },
                }
            )

            # Store in global debug results
            debug_results[debug_info["session_id"]] = debug_info
            logger.info(
                f"Stored debug result: {debug_info['source_label']} - {debug_info['session_id']}"
            )

            # Keep only last 100 results to prevent memory issues
            if len(debug_results) > 100:
                oldest_key = min(
                    debug_results.keys(),
                    key=lambda k: debug_results[k].get("timestamp", ""),
                )
                del debug_results[oldest_key]

        response = {
            "success": strategy_result.success,
            "entities": entities,
            "formatted_content": formatted_content,
            "strategy_used": strategy_result.strategy_used,
            "execution_time_ms": execution_time,
            "message_count": len(messages),
        }

        # Add debug info to response if requested
        if include_debug and debug_info:
            response["debug"] = debug_info

        return response

    except Exception as e:
        logger.error(f"Error in process_conversation: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "entities": [],
            "formatted_content": "",
        }


# Debug endpoints moved to admin router


logger.info("Including main router with routes")
app.include_router(router)
logger.info("Including graph router")
app.include_router(graph_router)
logger.info("Including admin router")
app.include_router(admin_router)
logger.info("Including UI router")
app.include_router(ui_router)
logger.info("All routers included successfully")

# Print all registered routes for debugging
for route in app.routes:
    if hasattr(route, "path"):
        methods = (
            getattr(route, "methods", ["WEBSOCKET"])
            if hasattr(route, "methods")
            else ["WEBSOCKET"]
        )
        logger.info(f"Registered route: {methods} {route.path}")
    elif hasattr(route, "routes"):
        for subroute in route.routes:
            if hasattr(subroute, "path"):
                methods = (
                    getattr(subroute, "methods", ["WEBSOCKET"])
                    if hasattr(subroute, "methods")
                    else ["WEBSOCKET"]
                )
                logger.info(f"Registered subroute: {methods} {subroute.path}")
