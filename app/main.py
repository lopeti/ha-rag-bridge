import os
import re
import json
from typing import List, Sequence, Dict, Any, Optional
from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ha_rag_bridge.logging import get_logger
from ha_rag_bridge.settings import HTTP_TIMEOUT
from ha_rag_bridge.similarity_config import get_current_config
from app.middleware.request_id import request_id_middleware

from .routers.graph import router as graph_router
from .routers.admin import router as admin_router
from ha_rag_bridge.utils.env import env_true
import httpx

from arango import ArangoClient

from . import schemas
from scripts.embedding_backends import (
    BaseEmbeddingBackend as EmbeddingBackend,
    LocalBackend,
    OpenAIBackend,
    GeminiBackend,
    get_backend,
)
from .services.state_service import get_last_state
from .services.service_catalog import ServiceCatalog
from .services.entity_reranker import entity_reranker

# Import LangGraph workflow at module level to avoid route registration issues
try:
    from .langgraph_workflow.workflow import run_rag_workflow
    LANGGRAPH_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LangGraph workflow not available: {e}")
    LANGGRAPH_AVAILABLE = False

app = FastAPI()
router = APIRouter()
logger = get_logger(__name__)
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


service_catalog = ServiceCatalog(int(os.getenv("SERVICE_CACHE_TTL", str(6 * 3600))))

# Cache embedding backends globally to avoid reloading models
_cached_backends: Dict[str, EmbeddingBackend] = {}

if env_true("AUTO_BOOTSTRAP", True):
    from ha_rag_bridge.bootstrap import bootstrap

    bootstrap()

backend_name = os.getenv("EMBEDDING_BACKEND", "local").lower()
if backend_name == "gemini":
    backend_dim = GeminiBackend.DIMENSION
elif backend_name == "openai":
    backend_dim = OpenAIBackend.DIMENSION
else:
    backend_dim = LocalBackend.DIMENSION
HEALTH_ERROR: str | None = None

if not os.getenv("SKIP_ARANGO_HEALTHCHECK"):
    try:
        arango_url = os.environ["ARANGO_URL"]
        arango_user = os.environ["ARANGO_USER"]
        arango_pass = os.environ["ARANGO_PASS"]

        arango = ArangoClient(hosts=arango_url)
        db_name = os.getenv("ARANGO_DB", "_system")
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
        "RETURN e) "
        "LET txt = ("
        "FOR e IN v_meta "
        "SEARCH ANALYZER(PHRASE(e.text_system, @msg, 'text_en'), 'text_en') "
        "SORT BM25(e) DESC "
        "LIMIT @k "
        "RETURN e) "
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
    from .services.cluster_manager import cluster_manager

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
    backend_name = os.getenv("EMBEDDING_BACKEND", "local").lower()
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

    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db_name = os.getenv("ARANGO_DB", "_system")
    db = arango.db(
        db_name,
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )

    intent = detect_intent(payload.user_message)

    # Phase 1: Detect query scope for adaptive retrieval
    from .services.query_scope_detector import query_scope_detector

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
                last = get_last_state(top.get("entity_id"))
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
    ha_url = os.getenv("HA_URL")
    token = os.getenv("HA_TOKEN")
    if not ha_url or not token:
        raise HTTPException(status_code=500, detail="Missing HA configuration")

    message = payload.choices[0].message
    tool_calls = message.tool_calls or []
    headers = {"Authorization": f"Bearer {token}"}
    errors: List[str] = []

    async with httpx.AsyncClient(
        base_url=ha_url, headers=headers, timeout=HTTP_TIMEOUT
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
    logger.info(f"WORKFLOW ENDPOINT CALLED: {payload.user_message if payload else 'no payload'}")
    
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
            session_id=session_id,
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
                "errors": ["Workflow execution failed"]
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
                "phase": "3_langgraph_workflow",
            }

        # Build response with Phase 3 enhancements
        response = schemas.ProcessResponse(
            relevant_entities=relevant_entities,
            formatted_content=formatted_context,
            intent=workflow_result.get("conversation_context", {}).get(
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

        logger.info(
            f"Phase 3 workflow completed: {len(relevant_entities)} entities, quality={diagnostics.get('overall_quality', 0.0):.2f}"
        )
        return response

    except Exception as exc:
        logger.error(f"Phase 3 workflow error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Phase 3 workflow error: {str(exc)}"
        )


logger.info("Including main router with routes")
app.include_router(router)
logger.info("Including graph router")
app.include_router(graph_router)
logger.info("Including admin router")
app.include_router(admin_router)
logger.info("All routers included successfully")

# Print all registered routes for debugging
for route in app.routes:
    if hasattr(route, 'path'):
        logger.info(f"Registered route: {route.methods} {route.path}")
    elif hasattr(route, 'routes'):
        for subroute in route.routes:
            if hasattr(subroute, 'path'):
                logger.info(f"Registered subroute: {subroute.methods} {subroute.path}")
