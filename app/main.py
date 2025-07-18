import os
from fastapi import FastAPI, APIRouter, HTTPException

from arango import ArangoClient

from . import schemas
from scripts.ingest import LocalBackend, OpenAIBackend, EmbeddingBackend

app = FastAPI()
router = APIRouter()


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

    aql = (
        "FOR e IN v_meta "
        "SEARCH ANALYZER("
        "SIMILARITY(e.embedding, @qv) > 0.7 "
        "OR PHRASE(e.text, @msg, \"text_en\")"
        ", \"text_en\") "
        "SORT BM25(e) DESC "
        "LIMIT 5 "
        "RETURN e"
    )
    try:
        cursor = db.aql.execute(aql, bind_vars={"qv": query_vector, "msg": payload.user_message})
        results = list(cursor)
    except Exception as exc:  # pragma: no cover - db errors
        raise HTTPException(status_code=500, detail=str(exc))

    ids = [doc.get("entity_id") for doc in results]
    comma_sep = ",".join(ids)
    system_prompt = "You are a Home Assistant agent.\n" f"Relevant entities: {comma_sep}\n"
    tools = [{
        "type": "function",
        "function": {
            "name": "homeassistant.turn_on",
            "parameters": {
                "type": "object",
                "properties": {"entity_id": {"type": "string"}},
                "required": ["entity_id"],
            },
        },
    }]

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload.user_message},
        ],
        "tools": tools,
    }


app.include_router(router)
