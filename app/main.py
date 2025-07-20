import os
import re
import json
from typing import List, Sequence, Dict, Any
from fastapi import FastAPI, APIRouter, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from ha_rag_bridge.logging import get_logger
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

service_catalog = ServiceCatalog(int(os.getenv("SERVICE_CACHE_TTL", str(6 * 3600))))

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
        logger.warning(
            "embedding dimension mismatch",
            backend=backend_dim,
            index=idx.get("dimensions"),
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


def query_arango(db, q_vec: Sequence[float], q_text: str, k: int) -> List[dict]:
    aql = (
        "FOR e IN v_meta "
        "SEARCH ANALYZER("
        "SIMILARITY(e.embedding, @qv) > 0.7 "
        "OR PHRASE(e.text, @msg, 'text_en')"
        ", 'text_en') "
        "SORT BM25(e) DESC "
        f"LIMIT {k} "
        "RETURN e"
    )
    cursor = db.aql.execute(aql, bind_vars={"qv": q_vec, "msg": q_text})
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
    db, doc_id: str, q_vec: Sequence[float], q_text: str, k: int = 2
) -> List[str]:
    aql = (
        "FOR d IN v_manual "
        "SEARCH d.document_id == @doc AND ANALYZER("
        "SIMILARITY(d.embedding, @qv) > 0.7 OR PHRASE(d.text, @msg, 'text_en')"
        ", 'text_en') "
        "SORT BM25(d) DESC "
        "LIMIT @k "
        "RETURN d.text"
    )
    cursor = db.aql.execute(
        aql,
        bind_vars={"doc": doc_id, "qv": q_vec, "msg": q_text, "k": k},
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


@router.post("/process-request", response_model=schemas.ProcessResponse)
async def process_request(payload: schemas.Request):
    backend_name = os.getenv("EMBEDDING_BACKEND", "local").lower()
    if backend_name == "openai":
        emb_backend: EmbeddingBackend = OpenAIBackend()
    elif backend_name == "local":
        emb_backend = LocalBackend()
    else:
        emb_backend = get_backend(backend_name)

    try:
        query_vector = emb_backend.embed([payload.user_message])[0]
    except Exception as exc:  # pragma: no cover - backend errors
        raise HTTPException(status_code=500, detail=str(exc))

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
        raise HTTPException(status_code=500, detail=str(exc))

    ids = [doc.get("entity_id") for doc in results]
    comma_sep = ",".join(ids)
    domain_set = sorted({doc.get("domain") for doc in results if doc.get("domain")})
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
            services = await service_catalog.get_domain_services(dom)
            for name, spec in services.items():
                tools.append(service_to_tool(dom, name, spec))

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
        base_url=ha_url, headers=headers, timeout=5.0
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
