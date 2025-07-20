from __future__ import annotations

import os
from fastapi import APIRouter, Request, HTTPException, status, Response
from ha_rag_bridge.bootstrap import bootstrap, SCHEMA_LATEST

router = APIRouter(prefix="/admin", tags=["admin"])


def _check_token(request: Request) -> None:
    token = os.getenv("ADMIN_TOKEN", "")
    if os.getenv("DEBUG") != "true" and request.headers.get("X-Admin-Token") != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@router.post("/migrate", status_code=204)
async def migrate(request: Request) -> Response:
    _check_token(request)
    bootstrap()
    return Response(status_code=204)


@router.post("/reindex", status_code=204)
async def reindex(request: Request) -> Response:
    _check_token(request)
    bootstrap()
    return Response(status_code=204)


@router.get("/status")
async def status_endpoint(request: Request) -> dict:
    _check_token(request)
    return {
        "db": os.getenv("ARANGO_DB", "ha_graph"),
        "schema": SCHEMA_LATEST,
        "vector_dim": int(os.getenv("EMBED_DIM", "1536")),
    }


@router.post("/vacuum", status_code=204)
async def vacuum(request: Request) -> Response:
    _check_token(request)
    return Response(status_code=204)
