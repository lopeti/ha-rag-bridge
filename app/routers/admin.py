from __future__ import annotations

import os
import json
import io
import zipfile
from datetime import datetime, timedelta
from time import perf_counter
from fastapi import APIRouter, Request, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from arango import ArangoClient
from ha_rag_bridge.bootstrap import bootstrap, SCHEMA_LATEST
from ha_rag_bridge.utils.env import env_true
from ha_rag_bridge.logging import get_logger

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger(__name__)


def _check_token(request: Request) -> None:
    token = os.getenv("ADMIN_TOKEN", "")
    if not env_true("DEBUG") and request.headers.get("X-Admin-Token") != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@router.post("/migrate", status_code=204)
async def migrate(request: Request) -> Response:
    _check_token(request)
    bootstrap()
    return Response(status_code=204)


@router.post("/reindex")
async def reindex(request: Request) -> dict:
    _check_token(request)
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    target = body.get("collection")
    force = bool(body.get("force"))

    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db = arango.db(
        os.getenv("ARANGO_DB", "_system"),
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )

    collections = [target] if target else [c["name"] for c in db.collections() if not c["name"].startswith("_")]
    embed_dim = int(os.getenv("EMBED_DIM", "1536"))

    dropped = created = 0
    start = perf_counter()
    for name in collections:
        col = db.collection(name)
        idx = next((i for i in col.indexes() if i["type"] == "vector"), None)
        if idx and (force or idx.get("dimensions") != embed_dim):
            col.delete_index(idx["id"])
            logger.warning(
                "vector index recreated", collection=name, force=force
            )
            dropped += 1
            idx = None
        if not idx:
            col.add_index({"type": "vector", "fields": ["embedding"], "dimensions": embed_dim, "metric": "cosine"})
            created += 1
    took_ms = int((perf_counter() - start) * 1000)
    logger.info(
        "reindex finished",
        collection=target or "all",
        dropped=dropped,
        created=created,
        dimensions=embed_dim,
        elapsed_ms=took_ms,
    )
    return {
        "collection": target or "all",
        "dropped": dropped,
        "created": created,
        "dimensions": embed_dim,
        "took_ms": took_ms,
    }


@router.get("/status")
async def status_endpoint(request: Request) -> dict:
    _check_token(request)
    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db = arango.db(
        os.getenv("ARANGO_DB", "_system"),
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )
    version = SCHEMA_LATEST
    if db.has_collection("_meta"):
        doc = db.collection("_meta").get("schema_version")
        if doc:
            version = int(doc.get("value", 0))
    return {
        "db": os.getenv("ARANGO_DB", "ha_graph"),
        "schema": version,
        "latest": SCHEMA_LATEST,
        "vector_dim": int(os.getenv("EMBED_DIM", "1536")),
    }


@router.post("/vacuum")
async def vacuum(request: Request) -> dict:
    _check_token(request)
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    days = int(body.get("days", 30))
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db = arango.db(
        os.getenv("ARANGO_DB", "_system"),
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )

    deleted_events = deleted_sensors = 0
    if db.has_collection("event"):
        cur = db.aql.execute("FOR d IN event FILTER d.ts < @ts REMOVE d IN event RETURN 1", bind_vars={"ts": cutoff})
        deleted_events = len(list(cur))
    if db.has_collection("sensor"):
        cur = db.aql.execute("FOR d IN sensor FILTER d.ts < @ts REMOVE d IN sensor RETURN 1", bind_vars={"ts": cutoff})
        deleted_sensors = len(list(cur))

    return {"deleted_events": deleted_events, "deleted_sensors": deleted_sensors}


@router.get("/export")
async def export(request: Request) -> StreamingResponse:
    _check_token(request)

    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db = arango.db(
        os.getenv("ARANGO_DB", "_system"),
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )

    col_names = [c["name"] for c in db.collections() if not c["name"].startswith("_")]

    def generator():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in col_names:
                docs = list(db.collection(name).all())
                if name == "embeddings":
                    for d in docs:
                        d.pop("embedding", None)
                data = "\n".join(json.dumps(d) for d in docs)
                zf.writestr(f"{name}.jsonl", data)
        buf.seek(0)
        chunk = buf.read(8192)
        while chunk:
            yield chunk
            chunk = buf.read(8192)

    headers = {"Content-Disposition": "attachment; filename=export.zip"}
    return StreamingResponse(generator(), media_type="application/zip", headers=headers)
