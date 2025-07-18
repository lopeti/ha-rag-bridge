import os
import re
import json
from typing import List, Sequence, Dict, Any
from fastapi import FastAPI, APIRouter, HTTPException

from .routers.graph import router as graph_router
import httpx

from arango import ArangoClient

from . import schemas
from scripts.ingest import LocalBackend, OpenAIBackend, EmbeddingBackend
from .services.state_service import get_last_state
from .services.service_catalog import ServiceCatalog

app = FastAPI()
router = APIRouter()

service_catalog = ServiceCatalog(int(os.getenv("SERVICE_CACHE_TTL", str(6*3600))))

CONTROL_RE = re.compile(r"\b(kapcsold|ind\xEDtsd|\xE1ll\xEDtsd|turn\s+on|turn\s+off)\b", re.IGNORECASE)
READ_RE = re.compile(r"\b(mennyi|h\xE1ny|milyen|fok|temperature|status)\b", re.IGNORECASE)


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


def service_to_tool(domain: str, name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a service spec to a tool definition."""
    return {
        "type": "function",
        "function": {
            "name": f"{domain}.{name}",
            "parameters": {
                "type": "object",
                "properties": spec.get("fields", {}),
                "required": [k for k, v in spec.get("fields", {}).items() if v.get("required")],
            },
        },
    }


def retrieve_entities(db, q_vec: Sequence[float], q_text: str, k_list=(5, 15)) -> List[dict]:
    for k in k_list:
        ents = query_arango(db, q_vec, q_text, k)
        if len(ents) >= 2:
            return ents
    return query_arango_text_only(db, q_text, 10)


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/process-request", response_model=schemas.ProcessResponse)
async def process_request(payload: schemas.Request):
    backend = os.getenv("EMBEDDING_BACKEND", "local").lower()
    if backend == "openai":
        emb_backend: EmbeddingBackend = OpenAIBackend()
    else:
        emb_backend = LocalBackend()

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

    async with httpx.AsyncClient(base_url=ha_url, headers=headers, timeout=5.0) as client:
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
