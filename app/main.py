import os
import re
import json
from typing import List, Sequence, Dict, Any
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
        error=str(exc)
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error occurred"}
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
        "SORT APPROX_NEAR_COSINE(e.embedding, @qv, { nProbe: @nprobe }) DESC "
        "LIMIT @k "
        "RETURN e) "
        "LET txt = ("
        "FOR e IN v_meta "
        "SEARCH ANALYZER(PHRASE(e.text, @msg, 'text_en'), 'text_en') "
        "SORT BM25(e) DESC "
        "LIMIT @k "
        "RETURN e) "
        "FOR e IN UNIQUE(UNION(knn, txt)) "
        "LIMIT @k "
        "RETURN e"
    )
    cursor = db.aql.execute(
        aql, bind_vars={"qv": q_vec, "msg": q_text, "k": k, "nprobe": nprobe}
    )
    return list(cursor)


def query_arango_text_only(db, q_text: str, k: int) -> List[dict]:
    aql = (
        "FOR e IN v_meta "
        "SEARCH ANALYZER(PHRASE(e.text, @msg, 'text_en'), 'text_en') "
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
        "FILTER d.document_id == @doc "
        "SORT APPROX_NEAR_COSINE(d.embedding, @qv, { nProbe: @nprobe }) DESC "
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
            "nprobe": nprobe,
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
    db, q_vec: Sequence[float], q_text: str, k_list=(5, 15)
) -> List[dict]:
    for k in k_list:
        ents = query_arango(db, q_vec, q_text, k)
        if len(ents) >= 2:
            return ents
    return query_arango_text_only(db, q_text, 10)


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
        query_vector = emb_backend.embed([payload.user_message])[0]
    except Exception as exc:  # pragma: no cover - backend errors
        logger.error(
            "Embedding backend error",
            backend=backend_name,
            message=payload.user_message,
            exc_info=exc,
            error=str(exc)
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

    try:
        results = retrieve_entities(db, query_vector, payload.user_message)
    except Exception as exc:  # pragma: no cover - db errors
        logger.error(
            "Database query error",
            message=payload.user_message,
            exc_info=exc,
            error=str(exc)
        )
        raise HTTPException(status_code=500, detail=f"Database error: {str(exc)}")

    # Biztonságos konverzió a None értékek kiszűrésével
    ids = [
        str(doc.get("entity_id")) for doc in results if doc.get("entity_id") is not None
    ]
    comma_sep = ",".join(ids)
    # Biztonságos konverzió a None értékek kiszűrésével és str típusúvá alakítással
    domain_set = sorted(
        [str(doc.get("domain")) for doc in results if doc.get("domain") is not None]
    )
    domains = ",".join(domain_set)
    system_prompt = (
        "You are a Home Assistant agent.\n"
        f"Relevant entities: {comma_sep}\n"
        f"Relevant domains: {domains}\n"
    )

    if results:
        top = results[0]
        if top.get("domain") == "sensor":
            last = get_last_state(top.get("entity_id"))
            if last is not None:
                system_prompt += (
                    f"Current value of {top['entity_id'].lower()}: {last}\n"
                )
        device_id = top.get("device_id")
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
                        system_prompt += "Manual hints:\n"
                        for h in hints:
                            system_prompt += f"- {h}\n"
            except Exception:  # pragma: no cover - db errors
                pass

    tools: List[Dict] = []
    if intent == "control":
        for dom in domain_set:
            if dom is not None:  # Ellenőrizzük, hogy a domain nem None
                services = await service_catalog.get_domain_services(str(dom))
                for name, spec in services.items():
                    if name is not None:  # Ellenőrizzük, hogy a name nem None
                        tools.append(service_to_tool(str(dom), name, spec))

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload.user_message},
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


app.include_router(router)
app.include_router(graph_router)
app.include_router(admin_router)
