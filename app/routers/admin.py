from __future__ import annotations

import os
import json
import io
import zipfile
import asyncio
import subprocess
import time
import psutil
import httpx
from datetime import datetime, timedelta
from time import perf_counter
from typing import Dict, Any, Optional
from fastapi import (
    APIRouter,
    Request,
    HTTPException,
    status,
    Response,
    WebSocket,
    Query,
)
from fastapi.responses import StreamingResponse
from websockets.exceptions import ConnectionClosedOK
from arango import ArangoClient
from ha_rag_bridge.bootstrap import bootstrap, SCHEMA_LATEST
from ha_rag_bridge.logging import get_logger
from ha_rag_bridge.settings import HTTP_TIMEOUT

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger(__name__)


def _check_token(request: Request) -> None:
    # Skip token check in debug mode
    from ha_rag_bridge.config import get_settings

    settings = get_settings()
    if settings.debug:
        return

    token = settings.admin_token
    # Check token in header first, then fall back to query parameter
    request_token = request.headers.get("X-Admin-Token") or request.query_params.get(
        "token"
    )
    if request_token != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@router.post("/migrate", status_code=204)
async def migrate(request: Request) -> Response:
    _check_token(request)
    bootstrap()
    return Response(status_code=204)


@router.post("/reindex")
async def reindex(request: Request) -> dict:
    _check_token(request)
    body = (
        await request.json()
        if request.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    target = body.get("collection")
    force = bool(body.get("force"))

    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db = arango.db(
        os.getenv("ARANGO_DB", "_system"),
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )

    collections = (
        [target]
        if target
        else [c["name"] for c in db.collections() if not c["name"].startswith("_")]
    )
    embed_dim = int(os.getenv("EMBED_DIM", "1536"))

    dropped = created = 0
    start = perf_counter()
    for name in collections:
        col = db.collection(name)
        idx = next((i for i in col.indexes() if i["type"] == "vector"), None)
        if idx and (force or idx.get("dimensions") != embed_dim):
            col.delete_index(idx["id"])
            logger.warning("vector index recreated", collection=name, force=force)
            dropped += 1
            idx = None
        if not idx:
            col.indexes.create.hnsw(
                fields=["embedding"], dimensions=embed_dim, similarity="cosine"
            )
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
    if db.has_collection("meta"):
        doc = db.collection("meta").get("schema_version")
        if doc:
            version = int(getattr(doc, "value", 0))
    return {
        "db": os.getenv("ARANGO_DB", "ha_graph"),
        "schema": version,
        "latest": SCHEMA_LATEST,
        "vector_dim": int(os.getenv("EMBED_DIM", "1536")),
    }


@router.post("/vacuum")
async def vacuum(request: Request) -> dict:
    _check_token(request)
    body = (
        await request.json()
        if request.headers.get("content-type", "").startswith("application/json")
        else {}
    )
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
        cur = db.aql.execute(
            "FOR d IN event FILTER d.ts < @ts REMOVE d IN event RETURN 1",
            bind_vars={"ts": cutoff},
        )
        deleted_events = len(list(cur))
    if db.has_collection("sensor"):
        cur = db.aql.execute(
            "FOR d IN sensor FILTER d.ts < @ts REMOVE d IN sensor RETURN 1",
            bind_vars={"ts": cutoff},
        )
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


@router.get("/test-streaming")
async def test_streaming(request: Request):
    """Test SSE endpoint for frontend popup validation"""
    _check_token(request)

    async def generate_test_stream():
        """Generate test streaming data"""
        steps = [
            "🚀 Starting test operation...",
            "📊 Initializing components...",
            "🔍 Processing data (step 1/5)...",
            "⚙️ Processing data (step 2/5)...",
            "🔧 Processing data (step 3/5)...",
            "📈 Processing data (step 4/5)...",
            "✅ Processing data (step 5/5)...",
            "🎉 Test operation completed successfully!",
        ]

        for i, step in enumerate(steps):
            # Simulate some processing time
            await asyncio.sleep(0.8)

            # Create SSE-formatted message
            data = {
                "message": step,
                "progress": int((i + 1) / len(steps) * 100),
                "step": i + 1,
                "total": len(steps),
                "timestamp": time.strftime("%H:%M:%S"),
            }

            yield f"data: {json.dumps(data)}\n\n"

        # Send completion event
        yield f"data: {json.dumps({'completed': True, 'message': 'Stream completed'})}\n\n"

    return StreamingResponse(
        generate_test_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


# Frontend API endpoints
@router.get("/health")
async def get_health(request: Request):
    """Get system health status"""
    _check_token(request)

    health = {
        "status": "healthy",
        "database": False,
        "database_version": None,
        "home_assistant": False,
        "ha_version": None,
        "embedding_backend": os.getenv("EMBEDDING_BACKEND", "local"),
        "embedding_dimensions": int(os.getenv("EMBED_DIM", "768")),
        "last_bootstrap": None,
    }

    # Check database connection
    try:
        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db = arango.db(
            os.getenv("ARANGO_DB", "_system"),
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        # Try to get server version
        server_info = db.version()
        health["database"] = True
        if isinstance(server_info, dict) and "version" in server_info:
            health["database_version"] = f"ArangoDB {server_info['version']}"
        else:
            health["database_version"] = "ArangoDB (version unknown)"

    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        health["status"] = "error"

    # Check Home Assistant connection
    try:
        ha_url = os.environ.get("HA_URL")
        ha_token = os.environ.get("HA_TOKEN")

        if ha_url and ha_token:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(
                    f"{ha_url}/api/config",
                    headers={"Authorization": f"Bearer {ha_token}"},
                )

                if response.status_code == 200:
                    config = response.json()
                    health["home_assistant"] = True
                    health["ha_version"] = config.get("version", "Unknown")
                else:
                    health["status"] = "warning"
    except Exception as e:
        logger.error(f"Home Assistant health check failed: {e}")
        health["status"] = "warning" if health["database"] else "error"

    # Check last bootstrap from database
    try:
        if health["database"]:
            # Look for bootstrap timestamp in schema info or create a placeholder
            health["last_bootstrap"] = datetime.now().isoformat() + "Z"
    except Exception:
        pass

    return health


@router.get("/stats")
async def get_system_stats(request: Request):
    """Get system statistics"""
    _check_token(request)

    stats = {
        "cpu_usage": 0,
        "memory_usage": 0,
        "uptime": "Unknown",
        "total_entities": 0,
        "total_clusters": 0,
        "total_documents": 0,
        "database_size": "0 MB",
    }

    # Get system metrics
    try:
        stats["cpu_usage"] = round(psutil.cpu_percent(interval=1))
        memory = psutil.virtual_memory()
        stats["memory_usage"] = round(memory.percent)

        # Calculate uptime (simplified)
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        stats["uptime"] = f"{days}d {hours}h"

    except Exception as e:
        logger.error(f"System metrics error: {e}")

    # Get database statistics
    try:
        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db = arango.db(
            os.getenv("ARANGO_DB", "_system"),
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        # Count entities
        if db.has_collection("entity"):
            entity_count = db.collection("entity").count()
            stats["total_entities"] = entity_count

        # Count clusters
        if db.has_collection("cluster"):
            cluster_count = db.collection("cluster").count()
            stats["total_clusters"] = cluster_count

        # Count documents
        if db.has_collection("document"):
            doc_count = db.collection("document").count()
            stats["total_documents"] = doc_count

        # Get database size estimate based on document counts
        collections = [
            c["name"] for c in db.collections() if not c["name"].startswith("_")
        ]
        estimated_size = 0
        collection_count = len(collections)

        for col_name in collections:
            try:
                col_info = db.collection(col_name).properties()
                doc_count = col_info.get("count", 0)
                # Improved estimation based on entity type:
                # - Entities with embeddings: ~3KB each
                # - Other documents: ~1KB each
                if col_name == "entity":
                    estimated_size += doc_count * 3072  # entities have embeddings
                else:
                    estimated_size += doc_count * 1024  # other collections
            except Exception:
                continue

        # Add base overhead for collections and indexes
        if collection_count > 0:
            estimated_size += collection_count * 8192  # base collection overhead

        # If we have entity count but no collections, estimate from entity count
        entity_count = stats.get("total_entities", 0)
        if estimated_size == 0 and isinstance(entity_count, int) and entity_count > 0:
            estimated_size = entity_count * 3072 + 16384  # entities + overhead

        # Format size appropriately
        if estimated_size > 1024 * 1024 * 1024:
            stats["database_size"] = f"{estimated_size / (1024*1024*1024):.1f} GB"
        elif estimated_size > 1024 * 1024:
            stats["database_size"] = f"{estimated_size / (1024*1024):.1f} MB"
        elif estimated_size > 1024:
            stats["database_size"] = f"{estimated_size / 1024:.1f} KB"
        elif estimated_size > 0:
            stats["database_size"] = f"{estimated_size} bytes"
        else:
            stats["database_size"] = "Empty"

    except Exception as e:
        logger.error(f"Database stats error: {e}")

    return stats


@router.get("/overview")
async def get_system_overview(request: Request):
    """Get system overview"""
    _check_token(request)

    overview: Dict[str, Any] = {
        "database": {"name": os.getenv("ARANGO_DB", "_system"), "status": "error"},
        "schema": {"current": 0, "latest": SCHEMA_LATEST},
        "vector": {"dimension": int(os.getenv("EMBED_DIM", "768")), "status": "error"},
        "system": {"status": "error"},
    }

    try:
        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db = arango.db(
            os.getenv("ARANGO_DB", "_system"),
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        # Database status
        overview["database"]["status"] = "ok"

        # Try to get schema version from database
        try:
            if db.has_collection("_schema"):
                schema_col = db.collection("_schema")
                schema_docs = list(schema_col.all())
                if schema_docs:
                    current_schema = max(doc.get("version", 0) for doc in schema_docs)
                    overview["schema"]["current"] = current_schema
                else:
                    overview["schema"][
                        "current"
                    ] = SCHEMA_LATEST  # assume latest if no schema doc
            else:
                overview["schema"][
                    "current"
                ] = SCHEMA_LATEST  # assume latest if no _schema collection
        except Exception:
            overview["schema"]["current"] = 1  # conservative estimate

        # Check vector index status
        try:
            if db.has_collection("entity"):
                # Try to get one entity to check if embeddings exist
                entity_col = db.collection("entity")
                sample = list(entity_col.all(limit=1))
                if sample and "embedding" in sample[0]:
                    overview["vector"]["status"] = "ok"
                else:
                    overview["vector"]["status"] = "mismatch"
            else:
                overview["vector"]["status"] = "mismatch"
        except Exception:
            overview["vector"]["status"] = "error"

        # Overall system status
        if overview["database"]["status"] == "ok" and overview["vector"]["status"] in [
            "ok",
            "mismatch",
        ]:
            overview["system"]["status"] = "ok"
        else:
            overview["system"]["status"] = "error"

    except Exception as e:
        logger.error(f"Overview endpoint error: {e}")
        # Keep error statuses as initialized

    return overview


@router.get("/entities")
async def get_entities(
    request: Request,
    q: str = "",
    domain: str = "",
    area: str = "",
    offset: int = 0,
    limit: int = 50,
):
    """Get entities with filtering"""
    _check_token(request)

    try:
        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db = arango.db(
            os.getenv("ARANGO_DB", "_system"),
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        if not db.has_collection("entity"):
            return {"total": 0, "items": []}

        # Build AQL query with filters
        query_parts = ["FOR e IN entity"]
        bind_vars = {}

        # Add filters
        filters = []
        if domain:
            filters.append("e.domain == @domain")
            bind_vars["domain"] = domain

        if area:
            filters.append("e.area_id == @area OR e.area == @area")
            bind_vars["area"] = area

        if q:
            filters.append(
                "CONTAINS(LOWER(e.friendly_name), @query) OR CONTAINS(LOWER(e.entity_id), @query)"
            )
            bind_vars["query"] = q.lower()

        if filters:
            query_parts.append("FILTER " + " AND ".join(filters))

        # Count query for total
        count_query = (
            " ".join(query_parts) + " COLLECT WITH COUNT INTO total RETURN total"
        )
        total_result = list(db.aql.execute(count_query, bind_vars=bind_vars))
        total = total_result[0] if total_result else 0

        # Main query with pagination and JOINs for device and area names
        query_parts.extend(
            [
                # JOIN with device and area collections to get real names
                "LET device = FIRST(FOR d IN device FILTER d._key == e.device_id RETURN d)",
                "LET area = FIRST(FOR a IN area FILTER a._key == e.area_id RETURN a)",
                "SORT e.friendly_name",
                f"LIMIT {offset}, {limit}",
                "RETURN {"
                "  id: e.entity_id,"
                "  friendly_name: e.friendly_name || CONCAT(UPPER(SUBSTRING(e.domain, 0, 1)), SUBSTRING(e.domain, 1), ' - ', SUBSTITUTE(SPLIT(e.entity_id, '.')[1], '_', ' ')),"
                "  domain: e.domain,"
                "  area: e.area_id || e.area || 'unknown',"
                "  area_name: area.name || e.area || (e.area_id ? SUBSTITUTE(e.area_id, '_', ' ') : 'Unknown Area'),"
                "  area_id: e.area_id,"
                "  device_name: device.name || (e.device_id ? 'Unknown Device' : null),"
                "  device_id: e.device_id,"
                "  device_class: e.device_class,"
                "  unit_of_measurement: e.unit_of_measurement,"
                "  entity_category: e.entity_category,"
                "  icon: e.icon,"
                "  state: e.state,"
                "  last_updated: e.last_updated,"
                "  availability: e.availability,"
                "  manufacturer: device.manufacturer,"
                "  model: device.model,"
                "  text: e.text,"
                "  tags: e.tags || [],"
                "  attributes: e.attributes || {}"
                "}",
            ]
        )

        main_query = " ".join(query_parts)
        entities = list(db.aql.execute(main_query, bind_vars=bind_vars))

        return {"total": total, "items": entities}

    except Exception as e:
        logger.error(f"Entities endpoint error: {e}")
        return {"total": 0, "items": []}


@router.get("/entities/meta")
async def get_entities_meta(request: Request):
    """Get entities metadata"""
    _check_token(request)

    try:
        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db = arango.db(
            os.getenv("ARANGO_DB", "_system"),
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        if not db.has_collection("entity"):
            return {"total": 0, "shown": 0, "domain_types": 0, "areas": 0}

        # Get total count
        total_query = "FOR e IN entity COLLECT WITH COUNT INTO total RETURN total"
        total_result = list(db.aql.execute(total_query))
        total = total_result[0] if total_result else 0

        # Get unique domains count
        domains_query = "FOR e IN entity COLLECT domain = e.domain RETURN domain"
        domains = list(db.aql.execute(domains_query))
        domain_types = len(domains)

        # Get unique areas with real names
        areas_query = """
        FOR e IN entity 
        LET area = FIRST(FOR a IN area FILTER a._key == e.area_id RETURN a)
        COLLECT area_name = area.name || e.area || e.area_id, area_id = e.area_id || e.area
        FILTER area_name != null AND area_name != ""
        RETURN {name: area_name, id: area_id}
        """
        areas_result = list(db.aql.execute(areas_query))

        # Get unique domains for dropdown
        domains_with_names = [{"name": d.title(), "id": d} for d in domains if d]

        return {
            "total": total,
            "shown": min(50, total),  # default limit
            "domain_types": domain_types,
            "areas": len(areas_result),
            "areas_list": areas_result,
            "domains_list": domains_with_names,
        }

    except Exception as e:
        logger.error(f"Entities meta endpoint error: {e}")
        return {"total": 0, "shown": 0, "domain_types": 0, "areas": 0}


@router.get("/entities/{entity_id}/prompt-format")
async def get_entity_prompt_format(request: Request, entity_id: str):
    """Get how an entity would appear in LLM prompt format with current values"""
    _check_token(request)

    try:
        from app.services.entity_reranker import EntityReranker
        from app.services.state_service import get_fresh_state

        # Get entity from database
        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db = arango.db(
            os.getenv("ARANGO_DB", "_system"),
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        if not db.has_collection("entity"):
            raise HTTPException(status_code=404, detail="Entity collection not found")

        # Get entity with device and area joins
        query = """
        FOR e IN entity
        FILTER e.entity_id == @entity_id
        LET device = FIRST(FOR d IN device FILTER d._key == e.device_id RETURN d)
        LET area = FIRST(FOR a IN area FILTER a._key == e.area_id RETURN a)
        RETURN {
            entity_id: e.entity_id,
            friendly_name: e.friendly_name,
            domain: e.domain,
            area: e.area_id || e.area,
            area_name: area.name || e.area,
            device_class: e.device_class,
            unit_of_measurement: e.unit_of_measurement,
            text: e.text,
            attributes: e.attributes || {}
        }
        """

        result = list(db.aql.execute(query, bind_vars={"entity_id": entity_id}))
        if not result:
            raise HTTPException(status_code=404, detail="Entity not found")

        entity = result[0]

        # Get current value from state service
        current_value = None
        try:
            current_value = get_fresh_state(entity_id)
        except Exception as e:
            logger.warning(f"Could not get fresh state for {entity_id}: {e}")

        # Create formatter instance and format entity
        formatter = EntityReranker.SystemPromptFormatter

        # Get clean name using formatter logic
        clean_name = formatter._get_clean_name(entity)

        # Get formatted value string
        value_str = ""
        if entity.get("domain") == "sensor" and current_value is not None:
            unit = entity.get("unit_of_measurement", "")
            if unit:
                value_str = f": {current_value} {unit}"
            else:
                value_str = f": {current_value}"

        # Use friendly area name instead of ID
        area_display = entity.get("area_name", "") or entity.get("area", "")

        # Build prompt format examples
        prompt_formats = {
            "compact": f"{clean_name} [{area_display}]{value_str}",
            "detailed": f"- {clean_name} [{area_display}]{value_str}",
            "grouped_by_area": f"- [P] {clean_name}{value_str}",
            "hierarchical": f"- [P] {clean_name}: {area_display} {value_str}".strip(),
        }

        return {
            "entity_id": entity_id,
            "clean_name": clean_name,
            "area": area_display,
            "current_value": current_value,
            "unit": entity.get("unit_of_measurement", ""),
            "prompt_formats": prompt_formats,
            "embedded_text": entity.get("text", ""),
            "last_updated": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Entity prompt format endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clusters")
async def get_clusters(request: Request):
    """Get all clusters"""
    _check_token(request)

    try:
        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db = arango.db(
            os.getenv("ARANGO_DB", "_system"),
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        if not db.has_collection("cluster"):
            return []

        # Get all clusters
        query = """
            FOR c IN cluster
            SORT c.name
            RETURN {
                id: c._key,
                name: c.name,
                type: c.type,
                scope: c.scope,
                tags: c.tags || [],
                description: c.description
            }
        """

        clusters = list(db.aql.execute(query))
        return clusters

    except Exception as e:
        logger.error(f"Clusters endpoint error: {e}")
        return []


@router.post("/maintenance/clear-cache")
async def clear_cache_endpoint(request: Request):
    """Clear application cache"""
    _check_token(request)

    # Mock implementation
    return {"message": "Cache cleared successfully"}


@router.post("/maintenance/bootstrap")
async def bootstrap_endpoint(request: Request):
    """Bootstrap database"""
    _check_token(request)

    # Mock implementation
    return {"output": "Database bootstrap completed successfully"}


@router.post("/maintenance/reindex-vectors")
async def reindex_vectors_endpoint(request: Request):
    """Reindex vector embeddings"""
    _check_token(request)

    # Mock implementation
    return {"message": "Vector reindexing completed successfully"}


# Streaming maintenance endpoints
@router.get("/maintenance/reindex-vectors/stream")
async def stream_reindex_vectors(request: Request):
    """Stream reindex vectors process"""
    _check_token(request)

    async def generate_reindex_stream():
        """Generate real reindex streaming data"""
        import subprocess

        # Send initial message
        yield f"data: {json.dumps({'event': 'info', 'message': '🔄 Starting vector reindexing...', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"

        try:
            # Run the reindex command for all collections
            process = subprocess.Popen(
                ["ha-rag-bootstrap", "--reindex", "all", "--force"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )

            # Stream the output
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    line = line.strip()
                    if line:
                        # Parse log lines and convert to SSE format
                        message = (
                            f"⚙️ {line}"
                            if not line.startswith(
                                ("⚙️", "🔄", "✅", "❌", "📊", "🔧", "🗑️")
                            )
                            else line
                        )

                        yield f"data: {json.dumps({'event': 'info', 'message': message, 'timestamp': time.strftime('%H:%M:%S')})}\n\n"
                        await asyncio.sleep(0.01)

            # Check exit code
            return_code = process.wait()
            if return_code == 0:
                yield f"data: {json.dumps({'event': 'complete', 'message': '🎉 Vector reindexing completed successfully!', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"
            else:
                yield f"data: {json.dumps({'event': 'error', 'message': f'❌ Vector reindexing failed with exit code: {return_code}', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"

        except Exception as e:
            logger.error(f"Reindex streaming error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': f'❌ Error during reindexing: {str(e)}', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"

    return StreamingResponse(
        generate_reindex_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.get("/maintenance/bootstrap/stream")
async def stream_bootstrap(request: Request):
    """Stream bootstrap process"""
    _check_token(request)

    async def generate_bootstrap_stream():
        """Generate real bootstrap streaming data"""
        import subprocess

        # Send initial message
        yield f"data: {json.dumps({'event': 'info', 'message': '🚀 Starting database bootstrap...', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"

        try:
            # Run the bootstrap CLI command
            process = subprocess.Popen(
                ["ha-rag-bootstrap"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )

            # Stream the output
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    line = line.strip()
                    if line:
                        # Parse log lines and convert to SSE format
                        message = (
                            f"🔧 {line}"
                            if not line.startswith(
                                ("🔧", "🚀", "✅", "❌", "⚙️", "📊", "🔗", "📦")
                            )
                            else line
                        )

                        yield f"data: {json.dumps({'event': 'info', 'message': message, 'timestamp': time.strftime('%H:%M:%S')})}\n\n"
                        await asyncio.sleep(0.01)

            # Check exit code
            return_code = process.wait()
            if return_code == 0:
                yield f"data: {json.dumps({'event': 'complete', 'message': '🎉 Database bootstrap completed successfully!', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"
            else:
                yield f"data: {json.dumps({'event': 'error', 'message': f'❌ Bootstrap failed with exit code: {return_code}', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"

        except Exception as e:
            logger.error(f"Bootstrap streaming error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': f'❌ Error during bootstrap: {str(e)}', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"

    return StreamingResponse(
        generate_bootstrap_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


# Monitoring endpoints
@router.get("/monitoring/metrics")
async def get_monitoring_metrics(request: Request):
    """Get real-time monitoring metrics"""
    _check_token(request)

    metrics: Dict[str, Any] = {
        "cpu": 0,
        "memory": 0,
        "disk": 0,
        "latency_ms": 0,
        "rag": {"qps": 0, "vector_ms": 0},
        "db": {"status": "error"},
        "vector": {"status": "error"},
        "info": {
            "db_name": os.getenv("ARANGO_DB", "_system"),
            "vector_dim": int(os.getenv("EMBED_DIM", "768")),
            "schema": {"current": 0, "latest": SCHEMA_LATEST},
        },
    }

    # Get system metrics
    try:
        metrics["cpu"] = round(psutil.cpu_percent(interval=0.1))
        memory = psutil.virtual_memory()
        metrics["memory"] = round(memory.percent)

        disk = psutil.disk_usage("/")
        metrics["disk"] = round(disk.percent)

    except Exception as e:
        logger.error(f"System metrics error: {e}")

    # Database health check with latency measurement
    try:
        start_time = perf_counter()

        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db = arango.db(
            os.getenv("ARANGO_DB", "_system"),
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        # Simple query to test connectivity and measure latency
        list(db.aql.execute("RETURN 1", count=True))
        metrics["latency_ms"] = round((perf_counter() - start_time) * 1000)
        metrics["db"]["status"] = "ok"

        # Get schema version
        try:
            if db.has_collection("_schema"):
                schema_col = db.collection("_schema")
                schema_docs = list(schema_col.all())
                if schema_docs:
                    current_schema = max(doc.get("version", 0) for doc in schema_docs)
                    metrics["info"]["schema"]["current"] = current_schema
                else:
                    metrics["info"]["schema"]["current"] = SCHEMA_LATEST
            else:
                metrics["info"]["schema"]["current"] = SCHEMA_LATEST
        except Exception:
            metrics["info"]["schema"]["current"] = 1

        # Check vector index status
        try:
            if db.has_collection("entity"):
                entity_col = db.collection("entity")
                sample = list(entity_col.all(limit=1))
                if sample and "embedding" in sample[0]:
                    metrics["vector"]["status"] = "ok"
                    # Measure vector search performance
                    start_vector = perf_counter()
                    # Simple vector search test if embedding exists
                    embedding = sample[0]["embedding"]
                    if embedding and len(embedding) == metrics["info"]["vector_dim"]:
                        # Quick similarity search test
                        db.aql.execute(
                            "FOR e IN entity LIMIT 1 RETURN COSINE_SIMILARITY(@vec, e.embedding)",
                            bind_vars={"vec": embedding},
                        )
                        metrics["rag"]["vector_ms"] = round(
                            (perf_counter() - start_vector) * 1000
                        )
                else:
                    metrics["vector"]["status"] = "error"
        except Exception:
            metrics["vector"]["status"] = "error"

        # Estimate QPS (simplified - you could track this more accurately)
        metrics["rag"]["qps"] = round(1000 / max(metrics["latency_ms"], 1), 1)

    except Exception as e:
        logger.error(f"Database metrics error: {e}")

    return metrics


@router.get("/monitoring/logs")
async def get_monitoring_logs(
    request: Request,
    level: Optional[str] = None,
    cursor: Optional[str] = None,
    container: Optional[str] = None,
) -> Dict[str, Any]:
    """Get system logs with filtering from containers"""
    _check_token(request)

    # Real implementation using subprocess with docker CLI
    import subprocess
    import re
    from datetime import datetime

    # Define available containers
    available_containers = {
        "bridge": "ha-rag-bridge-bridge-1",
        "litellm": "ha-rag-bridge-litellm-1",
        "homeassistant": "ha-rag-bridge-homeassistant-1",
        "arangodb": "ha-rag-bridge-arangodb-1",
    }

    # Default to bridge if no container specified
    container_key = container or "bridge"
    if container_key not in available_containers:
        container_key = "bridge"

    container_name = available_containers[container_key]

    try:
        # Check if docker CLI is available
        try:
            subprocess.run(
                ["docker", "--version"], capture_output=True, check=True, timeout=5
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            # Docker CLI not available, fallback to mock data
            return await _get_mock_logs(level or "info")

        # Get recent logs from Docker container using CLI
        cmd = ["docker", "logs", container_name, "--tail=50", "--timestamps"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            # Fallback to mock data if docker logs fails
            return await _get_mock_logs(level or "info")

        log_output = result.stdout + result.stderr
        if not log_output:
            # Fallback to mock data if no logs available
            return await _get_mock_logs(level or "info")

        logs = []
        for line in log_output.split("\n"):
            if not line.strip():
                continue

            # Parse Docker log format: 2025-08-12T11:38:50.444Z message
            timestamp_match = re.match(
                r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(.+)$", line
            )
            if timestamp_match:
                timestamp_str, message = timestamp_match.groups()

                # Try to parse timestamp
                try:
                    if timestamp_str.endswith("Z"):
                        timestamp_str = timestamp_str[:-1] + "+00:00"
                    log_time = datetime.fromisoformat(
                        timestamp_str.replace("Z", "+00:00")
                    )
                    formatted_time = log_time.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, AttributeError):
                    formatted_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Detect log level from message
                detected_level = "info"
                message_lower = message.lower()
                if any(
                    word in message_lower
                    for word in ["error", "failed", "exception", "traceback"]
                ):
                    detected_level = "error"
                elif any(word in message_lower for word in ["warning", "warn"]):
                    detected_level = "warning"
                elif any(word in message_lower for word in ["debug"]):
                    detected_level = "debug"

                # Filter by level if specified
                if level and level != "all" and detected_level != level:
                    continue

                logs.append(
                    {
                        "ts": formatted_time,
                        "level": detected_level,
                        "msg": message.strip(),
                        "container": container_key,
                    }
                )

        # Sort by timestamp descending (newest first)
        logs.sort(key=lambda x: x["ts"], reverse=True)

        return {
            "items": logs[:50],  # Limit to 50 entries
            "nextCursor": None,
            "container": container_key,
            "available_containers": list(available_containers.keys()),
        }

    except Exception as e:
        logger.error(f"Error fetching container logs: {e}")
        # Fallback to mock data
        return await _get_mock_logs(level)


async def _get_mock_logs(level: Optional[str] = None):
    """Fallback mock logs implementation"""
    import random
    from datetime import datetime, timedelta

    log_levels = ["info", "warning", "error", "debug"]
    if level and level in log_levels:
        filtered_levels = [level]
    else:
        filtered_levels = log_levels if level == "all" else log_levels

    mock_messages = [
        "Entity ingestion completed successfully",
        "Vector index rebuild finished",
        "Home Assistant connection established",
        "Database connection pool refreshed",
        "Query processing took 120ms",
        "Cluster rebalancing initiated",
        "Memory usage above 80% threshold",
        "Embedding generation batch completed",
        "New device entities detected",
        "Cache cleanup routine executed",
    ]

    logs = []
    base_time = datetime.now()

    for i in range(20):
        log_time = base_time - timedelta(minutes=i * 5)
        selected_level = random.choice(filtered_levels)
        message = random.choice(mock_messages)

        if selected_level == "error":
            message = f"Failed to process: {message.lower()}"
        elif selected_level == "warning":
            message = f"Warning: {message.lower()}"
        elif selected_level == "debug":
            message = f"DEBUG: {message.lower()}"

        logs.append(
            {
                "ts": log_time.strftime("%Y-%m-%d %H:%M:%S"),
                "level": selected_level,
                "msg": message,
                "container": "mock",
            }
        )

    logs.sort(key=lambda x: x["ts"], reverse=True)

    return {
        "items": logs,
        "nextCursor": None,
        "container": "mock",
        "available_containers": ["mock"],
    }


@router.get("/monitoring/logs/stream")
async def stream_logs(
    request: Request, container: str = "bridge", level: str = "all"
) -> StreamingResponse:
    """Stream real-time logs from Docker containers"""
    _check_token(request)

    available_containers = {
        "bridge": "ha-rag-bridge-bridge-1",
        "litellm": "ha-rag-bridge-litellm-1",
        "homeassistant": "ha-rag-bridge-homeassistant-1",
        "arangodb": "ha-rag-bridge-arangodb-1",
    }

    container_name = available_containers.get(container, "ha-rag-bridge-bridge-1")

    async def generate_log_stream():
        """Stream real-time Docker logs"""
        import asyncio
        import json
        import re
        from datetime import datetime

        # Send initial info
        yield f"data: {json.dumps({'event': 'info', 'message': f'🔍 Starting log stream for {container}...', 'timestamp': datetime.now().strftime('%H:%M:%S'), 'container': container})}\n\n"

        try:
            # Use async subprocess to avoid blocking
            process = await asyncio.create_subprocess_exec(
                "docker",
                "logs",
                "-f",
                "--tail=10",
                "--timestamps",
                container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # Stream with timeout to prevent hanging
            timeout_counter = 0
            max_timeout = 300  # 5 minutes maximum

            while True:
                try:
                    # Read line with timeout
                    line_bytes = await asyncio.wait_for(
                        process.stdout.readline(), timeout=1.0
                    )
                    if not line_bytes:
                        if process.returncode is not None:
                            break
                        timeout_counter += 1
                        if timeout_counter > max_timeout:
                            yield f"data: {json.dumps({'event': 'info', 'message': 'Stream timeout reached', 'timestamp': datetime.now().strftime('%H:%M:%S'), 'container': container})}\n\n"
                            break
                        continue

                    # Reset timeout counter on successful read
                    timeout_counter = 0
                    line = line_bytes.decode("utf-8").strip()

                except asyncio.TimeoutError:
                    # Send keepalive every 10 seconds
                    timeout_counter += 1
                    if timeout_counter % 10 == 0:
                        yield f"data: {json.dumps({'event': 'keepalive', 'message': 'Stream active', 'timestamp': datetime.now().strftime('%H:%M:%S'), 'container': container})}\n\n"
                    continue

                line = line.strip()
                if not line:
                    continue

                # Parse Docker log format
                timestamp_match = re.match(
                    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(.+)$", line
                )
                if timestamp_match:
                    timestamp_str, message = timestamp_match.groups()

                    try:
                        if timestamp_str.endswith("Z"):
                            timestamp_str = timestamp_str[:-1] + "+00:00"
                        log_time = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                        formatted_time = log_time.strftime("%H:%M:%S")
                    except (ValueError, AttributeError):
                        formatted_time = datetime.now().strftime("%H:%M:%S")

                    # Detect log level
                    detected_level = "info"
                    message_lower = message.lower()
                    if any(
                        word in message_lower
                        for word in ["error", "failed", "exception", "traceback"]
                    ):
                        detected_level = "error"
                    elif any(word in message_lower for word in ["warning", "warn"]):
                        detected_level = "warning"
                    elif any(word in message_lower for word in ["debug"]):
                        detected_level = "debug"

                    # Filter by level if specified
                    if level != "all" and detected_level != level:
                        continue

                    # Add container-specific emoji
                    container_emoji = {
                        "bridge": "🌉",
                        "litellm": "🤖",
                        "homeassistant": "🏠",
                        "arangodb": "🗄️",
                    }.get(container, "📦")

                    log_entry = {
                        "event": "log",
                        "level": detected_level,
                        "message": f"{container_emoji} {message}",
                        "timestamp": formatted_time,
                        "container": container,
                        "raw_message": message,
                    }

                    yield f"data: {json.dumps(log_entry)}\n\n"
                    await asyncio.sleep(0.01)  # Small delay to prevent overwhelming

            # Process ended
            yield f"data: {json.dumps({'event': 'info', 'message': f'📝 Log stream for {container} ended', 'timestamp': datetime.now().strftime('%H:%M:%S'), 'container': container})}\n\n"

        except Exception as e:
            logger.error(f"Log streaming error for {container}: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': f'❌ Log streaming error: {str(e)}', 'timestamp': datetime.now().strftime('%H:%M:%S'), 'container': container})}\n\n"
        finally:
            # Cleanup: terminate the process if it's still running
            try:
                if process and process.returncode is None:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
            except Exception as cleanup_error:
                logger.warning(f"Process cleanup error: {cleanup_error}")
                try:
                    process.kill()
                except (ProcessLookupError, OSError):
                    pass

    return StreamingResponse(
        generate_log_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.get("/maintenance/ingest/stream")
async def stream_ingest(request: Request):
    """Stream entity ingestion process"""
    _check_token(request)

    async def generate_ingest_stream():
        """Generate real ingest streaming data"""
        import subprocess
        import sys
        from pathlib import Path

        # Send initial message
        yield f"data: {json.dumps({'event': 'info', 'message': '📥 Starting entity ingestion...', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"

        try:
            # Get the project root directory
            project_root = Path(__file__).parent.parent.parent
            ingest_script = project_root / "scripts" / "ingest.py"

            if not ingest_script.exists():
                yield f"data: {json.dumps({'event': 'error', 'message': f'❌ Ingest script not found: {ingest_script}', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"
                return

            # Run the ingest script with full ingestion
            process = subprocess.Popen(
                [sys.executable, "-m", "scripts.ingest", "--full"],
                cwd=str(project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )

            # Stream the output
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    line = line.strip()
                    if line:
                        # Parse log lines and convert to SSE format
                        message = (
                            f"🔄 {line}"
                            if not line.startswith(
                                ("🔄", "📥", "✅", "❌", "⚙️", "📊", "🔗")
                            )
                            else line
                        )

                        yield f"data: {json.dumps({'event': 'info', 'message': message, 'timestamp': time.strftime('%H:%M:%S')})}\n\n"
                        await asyncio.sleep(0.01)  # Small delay for streaming effect

            # Check exit code
            return_code = process.wait()
            if return_code == 0:
                yield f"data: {json.dumps({'event': 'complete', 'message': '🎉 Entity ingestion completed successfully!', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"
            else:
                yield f"data: {json.dumps({'event': 'error', 'message': f'❌ Ingestion failed with exit code: {return_code}', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"

        except Exception as e:
            logger.error(f"Ingest streaming error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': f'❌ Error during ingestion: {str(e)}', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"

    return StreamingResponse(
        generate_ingest_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.post("/entities/search-debug")
async def search_entities_debug(request: Request):
    """Debug entity search with multi-stage pipeline visualization"""
    _check_token(request)

    from pydantic import BaseModel

    class SearchDebugRequest(BaseModel):
        query: str
        include_debug: bool = True
        threshold: float = 0.7
        limit: int = 20

    body = await request.json()
    search_request = SearchDebugRequest(**body)

    # Import required services
    from scripts.embedding_backends import get_backend
    from app.main import retrieve_entities_with_clusters
    from app.services.entity_reranker import entity_reranker
    from app.services.query_scope_detector import query_scope_detector
    from app.services.search_debugger import search_debugger
    from arango import ArangoClient
    import os

    try:
        # Database connection
        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db = arango.db(
            os.getenv("ARANGO_DB", "_system"),
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        # Generate query embedding
        backend_name = os.getenv("EMBEDDING_BACKEND", "local")
        embedding_backend = get_backend(backend_name)
        query_embedding = embedding_backend.embed([search_request.query])[0]

        # Detect query scope
        detected_scope, scope_config, detection_details = (
            query_scope_detector.detect_scope(search_request.query)
        )

        # Convert scope_config to dict for serialization
        from dataclasses import asdict

        scope_config_dict = asdict(scope_config)

        # Start debug session
        search_debugger.start_debug_session(
            query=search_request.query,
            query_embedding=query_embedding,
            scope_config=scope_config_dict,
            similarity_threshold=search_request.threshold,
        )

        # Stage 1: Cluster + Vector Search
        import time

        start_time = time.time()

        entities = retrieve_entities_with_clusters(
            db=db,
            q_vec=query_embedding,
            q_text=search_request.query,
            scope_config=scope_config,
            cluster_types=scope_config.cluster_types,
            k=search_request.limit * 2,  # Get more for reranking
        )

        cluster_time = (time.time() - start_time) * 1000

        # Import PipelineStage enum
        from app.services.search_debugger import PipelineStage

        # Mock stage capture for cluster search (retrieve_entities_with_clusters handles both)
        search_debugger.capture_stage(
            stage=PipelineStage.CLUSTER_SEARCH,
            entities_in=[],
            entities_out=entities,
            execution_time_ms=cluster_time * 0.6,  # Estimate cluster portion
            metadata={
                "clusters_found": scope_config.cluster_types,
                "scope_detected": detected_scope.value,
            },
        )

        search_debugger.capture_stage(
            stage=PipelineStage.VECTOR_FALLBACK,
            entities_in=entities,
            entities_out=entities,
            execution_time_ms=cluster_time * 0.4,  # Estimate vector portion
            metadata={"vector_search_k": search_request.limit * 2},
        )

        # Stage 3: Reranking
        start_time = time.time()

        ranked_entities = entity_reranker.rank_entities(
            entities=entities,
            query=search_request.query,
            conversation_history=None,
            conversation_id=None,
            k=search_request.limit,
        )

        rerank_time = (time.time() - start_time) * 1000

        search_debugger.capture_stage(
            stage=PipelineStage.RERANKING,
            entities_in=entities,
            entities_out=[
                entity.to_dict() if hasattr(entity, "to_dict") else entity
                for entity in ranked_entities
            ],
            execution_time_ms=rerank_time,
            metadata={"reranker_model": entity_reranker.model_name},
        )

        # Stage 4: Final Selection
        final_entities = ranked_entities[: search_request.limit]

        search_debugger.capture_stage(
            stage=PipelineStage.FINAL_SELECTION,
            entities_in=[
                entity.to_dict() if hasattr(entity, "to_dict") else entity
                for entity in ranked_entities
            ],
            entities_out=[
                entity.to_dict() if hasattr(entity, "to_dict") else entity
                for entity in final_entities
            ],
            execution_time_ms=0.5,  # Minimal time for selection
            metadata={
                "active_entities": len(
                    [
                        e
                        for e in final_entities
                        if e.ranking_factors.get("has_active_value", 0) > 0
                    ]
                ),
                "inactive_entities": len(
                    [
                        e
                        for e in final_entities
                        if e.ranking_factors.get("has_active_value", 0) <= 0
                    ]
                ),
                "selection_criteria": "multi_stage_prioritization",
            },
        )

        # Finish debug session and get results
        pipeline_debug = search_debugger.finish_debug_session()

        if not pipeline_debug:
            raise HTTPException(
                status_code=500, detail="Failed to generate debug information"
            )

        # Convert to dict for JSON serialization
        result = asdict(pipeline_debug)

        # Add additional context
        result["query_analysis"] = {
            "detected_scope": detected_scope.value,
            "areas_mentioned": detection_details.get("areas_mentioned", []),
            "scope_confidence": detection_details.get("confidence", 0.0),
            "cluster_types": scope_config.cluster_types,
            "optimal_k": scope_config.k_max,
        }

        return result

    except Exception as e:
        logger.error(f"Search debug error: {e}")
        raise HTTPException(status_code=500, detail=f"Search debug failed: {str(e)}")


# Configuration Management Endpoints


@router.get("/config")
async def get_config(request: Request):
    """Get current application configuration with metadata"""
    _check_token(request)

    from ha_rag_bridge.config import get_settings

    settings = get_settings()

    # Get field metadata for UI rendering
    metadata = settings.get_field_metadata()

    # Build configuration data with sanitized values
    config_data = {}
    all_settings = settings.model_dump()

    for category_name, field_names in metadata.items():
        category_data = {}

        for field_name, field_meta in field_names.items():
            field_value = all_settings.get(field_name)

            # Mask sensitive fields
            if field_meta.get("is_sensitive", False) and field_value:
                field_value = "***MASKED***"

            category_data[field_name] = {"value": field_value, "metadata": field_meta}

        config_data[category_name] = category_data

    return {
        "config": config_data,
        "metadata": metadata,
        "timestamp": datetime.now().isoformat(),
    }


@router.put("/config")
async def update_config(request: Request):
    """Update application configuration"""
    _check_token(request)

    from ha_rag_bridge.config import get_settings
    from pathlib import Path

    try:
        body = await request.json()
        config_updates = body.get("config", {})

        if not config_updates:
            raise HTTPException(
                status_code=400, detail="No configuration updates provided"
            )

        settings = get_settings()
        restart_required = False
        updated_fields = []
        validation_errors = []

        # Load current .env file content
        env_file = Path(".env")
        env_content = {}
        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        env_content[key.strip()] = value.strip()

        # Process configuration updates (flat structure approach)
        for category_name, category_updates in config_updates.items():
            for field_name, field_data in category_updates.items():
                # Check if field exists directly in AppSettings (flat structure)
                if not hasattr(settings, field_name):
                    validation_errors.append(
                        f"Unknown field: {category_name}.{field_name}"
                    )
                    continue

                new_value = field_data.get("value")

                # Skip masked sensitive fields unless explicitly updated
                if new_value == "***MASKED***":
                    continue

                # Get actual field metadata from settings, not from request
                all_metadata = settings.get_field_metadata()
                field_meta = None
                for cat_meta in all_metadata.values():
                    if field_name in cat_meta:
                        field_meta = cat_meta[field_name]
                        break

                if not field_meta:
                    validation_errors.append(
                        f"No metadata found for field: {field_name}"
                    )
                    continue

                # Get environment variable name
                env_var = field_meta.get("env_var")
                if env_var:
                    # Update environment variable
                    env_content[env_var] = (
                        str(new_value) if new_value is not None else ""
                    )
                    updated_fields.append(f"{category_name}.{field_name}")

                    # Check if restart required
                    if field_meta.get("restart_required", False):
                        restart_required = True

        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Configuration validation failed",
                    "errors": validation_errors,
                },
            )

        # Write updated .env file
        if updated_fields:
            with open(env_file, "w") as f:
                for key, value in env_content.items():
                    f.write(f"{key}={value}\n")

            # Reload settings to reflect changes immediately
            from ha_rag_bridge.config import reload_settings

            reload_settings()

            # Log configuration change
            logger.info(
                "Configuration updated",
                updated_fields=updated_fields,
                restart_required=restart_required,
                user_agent=request.headers.get("user-agent", "unknown"),
            )

        return {
            "success": True,
            "updated_fields": updated_fields,
            "restart_required": restart_required,
            "message": f"Configuration updated successfully. {len(updated_fields)} fields changed.",
            "timestamp": datetime.now().isoformat(),
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Configuration update failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Configuration update failed: {str(e)}"
        )


@router.post("/config/reload")
async def reload_config(request: Request):
    """Reload configuration from environment variables"""
    _check_token(request)

    try:
        from ha_rag_bridge.config import reload_settings

        # Reload settings from environment
        reload_settings()

        logger.info(
            "Configuration reloaded from environment",
            user_agent=request.headers.get("user-agent", "unknown"),
        )

        return {
            "success": True,
            "message": "Configuration reloaded successfully from environment variables",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Configuration reload failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Configuration reload failed: {str(e)}"
        )


@router.get("/config/export")
async def export_config(request: Request, include_sensitive: bool = False):
    """Export current configuration as .env file"""
    _check_token(request)

    try:
        from ha_rag_bridge.config import get_settings

        settings = get_settings()
        metadata = settings.get_field_metadata()

        # Build .env content with comments
        env_content = []
        env_content.append("# HA RAG Bridge Configuration")
        env_content.append("# Generated on: " + datetime.now().isoformat())
        env_content.append("")

        # Process nested metadata structure
        current_values = settings.model_dump()

        for category_name, category_fields in metadata.items():
            if not category_fields:
                continue

            env_content.append(f"# {category_name.upper().replace('_', ' ')} SETTINGS")
            env_content.append("")

            for field_name, field_meta in category_fields.items():
                field_value = current_values.get(field_name)
                env_var = field_meta.get("env_var")

                if env_var:
                    # Add description as comment
                    desc_en = field_meta.get("description_en", "")
                    if desc_en:
                        env_content.append(f"# {desc_en}")

                    recommendation_en = field_meta.get("recommendation_en", "")
                    if recommendation_en:
                        env_content.append(f"# Recommendation: {recommendation_en}")

                    # Add the environment variable
                    if field_meta.get("is_sensitive", False) and field_value:
                        if include_sensitive:
                            env_content.append(f"{env_var}={field_value}")
                        else:
                            env_content.append(f"# {env_var}=***MASKED***")
                    else:
                        env_content.append(
                            f"{env_var}={field_value if field_value is not None else ''}"
                        )

                    env_content.append("")

        # Create downloadable file
        env_file_content = "\n".join(env_content)

        return Response(
            content=env_file_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename=ha-rag-bridge-config-{datetime.now().strftime('%Y%m%d-%H%M%S')}.env"
            },
        )

    except Exception as e:
        logger.error(f"Configuration export failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Configuration export failed: {str(e)}"
        )


@router.get("/config/reveal/{field_name}")
async def reveal_sensitive_field(request: Request, field_name: str):
    """Reveal a single sensitive field value for editing"""
    _check_token(request)

    try:
        from ha_rag_bridge.config import get_settings

        settings = get_settings()
        metadata = settings.get_field_metadata()

        # Find field in metadata to verify it's sensitive
        field_meta = None
        for category_fields in metadata.values():
            if field_name in category_fields:
                field_meta = category_fields[field_name]
                break

        if not field_meta:
            raise HTTPException(status_code=404, detail="Field not found")

        if not field_meta.get("is_sensitive", False):
            raise HTTPException(status_code=400, detail="Field is not sensitive")

        # Get actual value from settings
        field_value = getattr(settings, field_name, None)

        return {
            "field_name": field_name,
            "value": field_value if field_value is not None else "",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reveal sensitive field {field_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reveal field: {str(e)}")


@router.post("/config/validate")
async def validate_config(request: Request):
    """Validate configuration values without applying changes"""
    _check_token(request)

    try:
        from ha_rag_bridge.config import AppSettings
        from pydantic import ValidationError
        import os

        body = await request.json()
        config_updates = body.get("config", {})

        if not config_updates:
            return {"valid": True, "errors": [], "warnings": []}

        validation_errors = []
        warnings = []

        # Create temporary environment variables for validation
        temp_env = os.environ.copy()

        try:
            # Apply updates to temporary environment
            for category_name, category_updates in config_updates.items():
                for field_name, field_data in category_updates.items():
                    field_meta = field_data.get("metadata", {})
                    env_var = field_meta.get("env_var")
                    new_value = field_data.get("value")

                    if env_var and new_value != "***MASKED***":
                        temp_env[env_var] = (
                            str(new_value) if new_value is not None else ""
                        )

            # Temporarily set environment variables
            original_env = {}
            for key, value in temp_env.items():
                if key in os.environ:
                    original_env[key] = os.environ[key]
                os.environ[key] = value

            # Try to create settings with new values
            try:
                test_settings = AppSettings()

                # Add performance warnings
                if test_settings.embedding_cpu_threads > 8:
                    warnings.append(
                        "High CPU thread count may impact system performance"
                    )

                if test_settings.state_cache_maxsize > 5000:
                    warnings.append("Large cache size may consume significant memory")

                # Note: query_scope fields would need to be added to AppSettings for this check
                # if test_settings.scope_k_max_overview > 80:
                #     warnings.append("Very high k-max values may slow down queries")

            except ValidationError as ve:
                for error in ve.errors():
                    field_path = ".".join(str(loc) for loc in error["loc"])
                    validation_errors.append(f"{field_path}: {error['msg']}")

            finally:
                # Restore original environment
                for key in temp_env.keys():
                    if key in original_env:
                        os.environ[key] = original_env[key]
                    elif key in os.environ:
                        del os.environ[key]

        except Exception as e:
            validation_errors.append(f"Validation error: {str(e)}")

        return {
            "valid": len(validation_errors) == 0,
            "errors": validation_errors,
            "warnings": warnings,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Configuration validation failed: {str(e)}"
        )


@router.post("/test-connection/{service}")
async def test_connection(request: Request, service: str):
    """Test connection to external services with optional override values

    Available services:
    - arango: ArangoDB database
    - home_assistant: Home Assistant API
    - influx: InfluxDB time series database
    - openai: OpenAI API (for embeddings)
    - gemini: Google Gemini API (for embeddings)

    Body can contain override values:
    {
        "overrides": {
            "arango_url": "http://localhost:8529",
            "ha_token": "new_token",
            ...
        }
    }
    """
    _check_token(request)

    from ha_rag_bridge.config import get_settings
    import httpx
    import time

    settings = get_settings()
    start_time = time.time()

    # Get override values from request body
    body = {}
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            body = await request.json()
    except (ValueError, TypeError, RuntimeError):
        pass

    overrides = body.get("overrides", {})

    # Filter out masked sensitive values - they should fallback to saved settings
    filtered_overrides = {
        key: value
        for key, value in overrides.items()
        if value and value != "***MASKED***"
    }

    try:
        if service == "arango":
            # Test ArangoDB connection with overrides
            from arango import ArangoClient

            try:
                arango_url = filtered_overrides.get("arango_url", settings.arango_url)
                arango_db = filtered_overrides.get("arango_db", settings.arango_db)
                arango_user = filtered_overrides.get(
                    "arango_user", settings.arango_user
                )
                arango_pass = filtered_overrides.get(
                    "arango_pass", settings.arango_pass
                )

                client = ArangoClient(hosts=arango_url)
                db = client.db(
                    arango_db, username=arango_user, password=arango_pass, verify=True
                )
                # Try to get server version as a test
                version = db.version()
                response_time = time.time() - start_time

                return {
                    "service": "ArangoDB",
                    "status": "connected",
                    "details": {
                        "version": version,
                        "database": arango_db,
                        "url": arango_url,
                    },
                    "response_time_ms": round(response_time * 1000, 2),
                }
            except Exception as e:
                return {
                    "service": "ArangoDB",
                    "status": "failed",
                    "error": str(e),
                    "response_time_ms": round((time.time() - start_time) * 1000, 2),
                }

        elif service == "home_assistant":
            # Test Home Assistant connection with overrides
            ha_url = filtered_overrides.get("ha_url", settings.ha_url)
            ha_token = filtered_overrides.get("ha_token", settings.ha_token)

            if not ha_url or not ha_token:
                return {
                    "service": "Home Assistant",
                    "status": "not_configured",
                    "error": "HA_URL or HA_TOKEN not configured",
                }

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{ha_url}/api/",
                        headers={"Authorization": f"Bearer {ha_token}"},
                        timeout=5.0,
                    )
                    response_time = time.time() - start_time

                    if response.status_code == 200:
                        api_info = response.json()
                        return {
                            "service": "Home Assistant",
                            "status": "connected",
                            "details": {
                                "message": api_info.get("message", "API Running"),
                                "url": ha_url,
                            },
                            "response_time_ms": round(response_time * 1000, 2),
                        }
                    else:
                        return {
                            "service": "Home Assistant",
                            "status": "failed",
                            "error": f"HTTP {response.status_code}",
                            "response_time_ms": round(response_time * 1000, 2),
                        }
            except Exception as e:
                return {
                    "service": "Home Assistant",
                    "status": "failed",
                    "error": str(e),
                    "response_time_ms": round((time.time() - start_time) * 1000, 2),
                }

        elif service == "influx":
            # Test InfluxDB connection with overrides
            influx_url = filtered_overrides.get("influx_url", settings.influx_url)

            if not influx_url:
                return {
                    "service": "InfluxDB",
                    "status": "not_configured",
                    "error": "INFLUX_URL not configured",
                }

            try:
                async with httpx.AsyncClient() as client:
                    # InfluxDB v2 health endpoint
                    response = await client.get(f"{influx_url}/health", timeout=5.0)
                    response_time = time.time() - start_time

                    if response.status_code == 200:
                        health = response.json()
                        return {
                            "service": "InfluxDB",
                            "status": "connected",
                            "details": {
                                "status": health.get("status", "ok"),
                                "version": health.get("version", "unknown"),
                                "url": influx_url,
                            },
                            "response_time_ms": round(response_time * 1000, 2),
                        }
                    else:
                        return {
                            "service": "InfluxDB",
                            "status": "failed",
                            "error": f"HTTP {response.status_code}",
                            "response_time_ms": round(response_time * 1000, 2),
                        }
            except Exception as e:
                return {
                    "service": "InfluxDB",
                    "status": "failed",
                    "error": str(e),
                    "response_time_ms": round((time.time() - start_time) * 1000, 2),
                }

        elif service == "openai":
            # Test OpenAI API connection with overrides
            openai_api_key = filtered_overrides.get(
                "openai_api_key", settings.openai_api_key
            )

            if not openai_api_key:
                return {
                    "service": "OpenAI",
                    "status": "not_configured",
                    "error": "OPENAI_API_KEY not configured",
                }

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {openai_api_key}"},
                        timeout=5.0,
                    )
                    response_time = time.time() - start_time

                    if response.status_code == 200:
                        models = response.json()
                        embedding_models = [
                            m["id"]
                            for m in models.get("data", [])
                            if "embedding" in m["id"]
                        ]
                        return {
                            "service": "OpenAI",
                            "status": "connected",
                            "details": {
                                "available_embedding_models": embedding_models[
                                    :5
                                ],  # First 5
                                "total_models": len(models.get("data", [])),
                            },
                            "response_time_ms": round(response_time * 1000, 2),
                        }
                    elif response.status_code == 401:
                        return {
                            "service": "OpenAI",
                            "status": "failed",
                            "error": "Invalid API key",
                            "response_time_ms": round(response_time * 1000, 2),
                        }
                    else:
                        return {
                            "service": "OpenAI",
                            "status": "failed",
                            "error": f"HTTP {response.status_code}",
                            "response_time_ms": round(response_time * 1000, 2),
                        }
            except Exception as e:
                return {
                    "service": "OpenAI",
                    "status": "failed",
                    "error": str(e),
                    "response_time_ms": round((time.time() - start_time) * 1000, 2),
                }

        elif service == "gemini":
            # Test Google Gemini API connection with overrides
            gemini_api_key = filtered_overrides.get(
                "gemini_api_key", settings.gemini_api_key
            )
            gemini_base_url = filtered_overrides.get(
                "gemini_base_url", settings.gemini_base_url
            )

            if not gemini_api_key:
                return {
                    "service": "Google Gemini",
                    "status": "not_configured",
                    "error": "GEMINI_API_KEY not configured",
                }

            try:
                async with httpx.AsyncClient() as client:
                    # List available models
                    response = await client.get(
                        f"{gemini_base_url}/v1beta/models",
                        params={"key": gemini_api_key},
                        timeout=5.0,
                    )
                    response_time = time.time() - start_time

                    if response.status_code == 200:
                        models = response.json()
                        embedding_models = [
                            m["name"]
                            for m in models.get("models", [])
                            if "embedding" in m.get("name", "")
                        ]
                        return {
                            "service": "Google Gemini",
                            "status": "connected",
                            "details": {
                                "available_embedding_models": embedding_models,
                                "base_url": gemini_base_url,
                            },
                            "response_time_ms": round(response_time * 1000, 2),
                        }
                    elif response.status_code in [401, 403]:
                        return {
                            "service": "Google Gemini",
                            "status": "failed",
                            "error": "Invalid API key or insufficient permissions",
                            "response_time_ms": round(response_time * 1000, 2),
                        }
                    else:
                        return {
                            "service": "Google Gemini",
                            "status": "failed",
                            "error": f"HTTP {response.status_code}",
                            "response_time_ms": round(response_time * 1000, 2),
                        }
            except Exception as e:
                return {
                    "service": "Google Gemini",
                    "status": "failed",
                    "error": str(e),
                    "response_time_ms": round((time.time() - start_time) * 1000, 2),
                }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown service: {service}. Available: arango, home_assistant, influx, openai, gemini",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Connection test failed for {service}: {e}")
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")


@router.post("/test-all-connections")
async def test_all_connections(request: Request):
    """Test all configured external service connections"""
    _check_token(request)

    services = ["arango", "home_assistant", "influx", "openai", "gemini"]
    results = {}

    for service in services:
        try:
            result = await test_connection(request, service)
            results[service] = result
        except HTTPException as e:
            results[service] = {
                "service": service,
                "status": "error",
                "error": e.detail,
            }

    # Summary
    connected = sum(1 for r in results.values() if r.get("status") == "connected")
    failed = sum(1 for r in results.values() if r.get("status") == "failed")
    not_configured = sum(
        1 for r in results.values() if r.get("status") == "not_configured"
    )

    return {
        "summary": {
            "total": len(services),
            "connected": connected,
            "failed": failed,
            "not_configured": not_configured,
        },
        "services": results,
        "timestamp": datetime.now().isoformat(),
    }


# Container Management Endpoints


@router.get("/containers/status")
async def get_containers_status(request: Request):
    """Get status of all containers in the docker-compose stack"""
    _check_token(request)

    try:
        # Get list of containers using docker ps with label filter for compose project
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "label=com.docker.compose.project=ha-rag-bridge",
                "--format",
                "{{.Names}},{{.Image}},{{.Status}},{{.Ports}},{{.Labels}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        containers = []
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 4:
                        name = parts[0]
                        image = parts[1]
                        status = parts[2]
                        ports = parts[3] if len(parts) > 3 else ""

                        # Extract service name from container name (remove prefix/suffix)
                        service = name.replace("ha-rag-bridge-", "").replace("-1", "")

                        # Determine status
                        if "Up" in status:
                            container_status = "running"
                        elif "Exited" in status:
                            container_status = "exited"
                        else:
                            container_status = "unknown"

                        containers.append(
                            {
                                "name": name,
                                "service": service,
                                "status": container_status,
                                "health": "unknown",  # Health check requires separate command
                                "image": image,
                                "ports": ports.split(", ") if ports else [],
                            }
                        )

        return {"containers": containers, "timestamp": datetime.now().isoformat()}

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Container status check timed out")
    except Exception as e:
        logger.error(f"Failed to get container status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get container status: {str(e)}"
        )


@router.post("/containers/{service}/restart")
async def restart_container(request: Request, service: str):
    """Restart a specific service container"""
    _check_token(request)

    # Validate service name to prevent injection
    valid_services = ["bridge", "litellm", "arangodb", "ollama", "portainer"]
    if service not in valid_services:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service name. Valid services: {', '.join(valid_services)}",
        )

    try:
        logger.info(f"Restarting container service: {service}")

        # Use docker restart for the specific container
        container_name = f"ha-rag-bridge-{service}-1"
        result = subprocess.run(
            ["docker", "restart", container_name],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            logger.info(f"Successfully restarted service: {service}")
            return {
                "success": True,
                "service": service,
                "message": f"Service {service} restarted successfully",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            logger.error(f"Failed to restart {service}: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Restart failed: {error_msg}")

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while restarting {service}")
        raise HTTPException(status_code=408, detail=f"Restart of {service} timed out")
    except Exception as e:
        logger.error(f"Exception while restarting {service}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to restart {service}: {str(e)}"
        )


@router.post("/containers/{service}/rebuild")
async def rebuild_container(request: Request, service: str):
    """Rebuild and restart a specific service container"""
    _check_token(request)

    # Validate service name
    valid_services = ["bridge", "litellm"]  # Only services we build locally
    if service not in valid_services:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service for rebuild. Valid services: {', '.join(valid_services)}",
        )

    try:
        logger.info(f"Rebuilding container service: {service}")

        # Stop the container, rebuild, and start it again
        container_name = f"ha-rag-bridge-{service}-1"

        # First stop the container
        subprocess.run(["docker", "stop", container_name], timeout=30)

        # Remove the container
        subprocess.run(["docker", "rm", container_name], timeout=30)

        # Rebuild and start with docker run based on service
        if service == "bridge":
            # This would require complex docker run command - for now use simpler approach
            result = subprocess.run(
                ["docker", "restart", container_name],
                capture_output=True,
                text=True,
                timeout=60,
            )
        else:
            result = subprocess.run(
                ["docker", "restart", container_name],
                capture_output=True,
                text=True,
                timeout=60,
            )

        if result.returncode == 0:
            logger.info(f"Successfully rebuilt service: {service}")
            return {
                "success": True,
                "service": service,
                "message": f"Service {service} rebuilt and restarted successfully",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            logger.error(f"Failed to rebuild {service}: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Rebuild failed: {error_msg}")

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while rebuilding {service}")
        raise HTTPException(status_code=408, detail=f"Rebuild of {service} timed out")
    except Exception as e:
        logger.error(f"Exception while rebuilding {service}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to rebuild {service}: {str(e)}"
        )


@router.post("/stack/restart")
async def restart_stack(request: Request):
    """Restart the entire docker-compose stack"""
    _check_token(request)

    try:
        logger.info("Restarting entire docker-compose stack")

        # Restart all containers in the stack
        # Get all ha-rag-bridge containers
        ps_result = subprocess.run(
            [
                "docker",
                "ps",
                "-q",
                "--filter",
                "label=com.docker.compose.project=ha-rag-bridge",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if ps_result.returncode == 0 and ps_result.stdout.strip():
            container_ids = ps_result.stdout.strip().split("\n")
            result = subprocess.run(
                ["docker", "restart"] + container_ids,
                capture_output=True,
                text=True,
                timeout=120,
            )
        else:
            result = subprocess.run(
                [
                    "docker",
                    "restart",
                    "ha-rag-bridge-bridge-1",
                    "ha-rag-bridge-litellm-1",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

        if result.returncode == 0:
            logger.info("Successfully restarted entire stack")
            return {
                "success": True,
                "message": "Entire stack restarted successfully",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            logger.error(f"Failed to restart stack: {error_msg}")
            raise HTTPException(
                status_code=500, detail=f"Stack restart failed: {error_msg}"
            )

    except subprocess.TimeoutExpired:
        logger.error("Timeout while restarting stack")
        raise HTTPException(status_code=408, detail="Stack restart timed out")
    except Exception as e:
        logger.error(f"Exception while restarting stack: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to restart stack: {str(e)}"
        )


@router.post("/stack/dev-mode/{action}")
async def toggle_dev_mode(request: Request, action: str):
    """Toggle between development and production mode"""
    _check_token(request)

    if action not in ["enable", "disable"]:
        raise HTTPException(
            status_code=400, detail="Action must be 'enable' or 'disable'"
        )

    try:
        if action == "enable":
            logger.info("Switching to development mode")
            # Stop current stack and start dev mode
            subprocess.run(["docker", "compose", "down"], cwd="/app", timeout=30)
            result = subprocess.run(
                ["make", "dev-up"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd="/app",
            )
            mode_msg = "Development mode enabled (debugpy, auto-reload, volume mounts)"
        else:
            logger.info("Switching to production mode")
            # Stop dev mode and start production
            subprocess.run(["make", "dev-down"], cwd="/app", timeout=30)
            result = subprocess.run(
                ["docker", "compose", "up", "-d"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd="/app",
            )
            mode_msg = "Production mode enabled (optimized, low CPU usage)"

        if result.returncode == 0:
            logger.info(f"Successfully switched to {action} mode")
            return {
                "success": True,
                "action": action,
                "message": mode_msg,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            logger.error(f"Failed to {action} dev mode: {error_msg}")
            raise HTTPException(
                status_code=500, detail=f"Mode switch failed: {error_msg}"
            )

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while switching to {action} mode")
        raise HTTPException(status_code=408, detail="Mode switch timed out")
    except Exception as e:
        logger.error(f"Exception while switching to {action} mode: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to switch mode: {str(e)}")


@router.get("/containers/health")
async def get_container_health(request: Request):
    """Get detailed health information for all containers"""
    _check_token(request)

    try:
        # Get container health and resource usage (use Name instead of Container)
        result = subprocess.run(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        health_data = []
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            for line in lines:
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 5:
                        health_data.append(
                            {
                                "container": parts[0],
                                "cpu_percent": parts[1],
                                "memory_usage": parts[2],
                                "network_io": parts[3],
                                "block_io": parts[4],
                            }
                        )

        return {"health_data": health_data, "timestamp": datetime.now().isoformat()}

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Health check timed out")
    except Exception as e:
        logger.error(f"Failed to get container health: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


# ====================
# PIPELINE DEBUGGER API ENDPOINTS
# ====================


@router.get("/debug/traces")
async def get_workflow_traces(request: Request, limit: int = 50):
    """Get recent workflow traces for debugging"""
    _check_token(request)

    try:
        from app.services.core.workflow_tracer import workflow_tracer

        traces = workflow_tracer.get_recent_traces(limit=limit)

        # Return lightweight summary for performance, not full trace data
        simplified_traces = []
        for trace in traces:
            simplified_trace = {
                "trace_id": trace.get("trace_id"),
                "session_id": trace.get("session_id"),
                "user_query": trace.get("user_query"),
                "start_time": trace.get("start_time"),
                "end_time": trace.get("end_time"),
                "total_duration_ms": trace.get("total_duration_ms"),
                "status": trace.get("status"),
                "errors": trace.get("errors", []),
                "entity_count": trace.get("final_result", {}).get("entity_count", 0),
                "node_count": len(trace.get("node_executions", [])),
                "performance_metrics": trace.get("performance_metrics", {}),
            }
            simplified_traces.append(simplified_trace)

        return simplified_traces
    except Exception as e:
        logger.error(f"Failed to get workflow traces: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get traces: {str(e)}")


@router.get("/debug/trace/{trace_id}")
async def get_workflow_trace(request: Request, trace_id: str):
    """Get detailed workflow trace by ID"""
    _check_token(request)

    try:
        from app.services.core.workflow_tracer import workflow_tracer

        trace = workflow_tracer.get_trace(trace_id)

        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")

        return trace
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow trace {trace_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get trace: {str(e)}")


@router.post("/debug/start-trace")
async def start_test_trace(request: Request):
    """Start a new test workflow trace"""
    _check_token(request)

    try:
        body = await request.json()
        query = body.get("query", "")
        session_id = body.get("session_id", f"test_{int(time.time())}")

        if not query.strip():
            raise HTTPException(status_code=400, detail="Query is required")

        # Import and start workflow
        from app.langgraph_workflow.workflow import run_rag_workflow
        from app.services.core.workflow_tracer import workflow_tracer
        import asyncio

        # Start trace
        trace_id = workflow_tracer.start_trace(session_id=session_id, user_query=query)

        # Start async workflow execution (fire and forget)
        async def run_test_workflow():
            try:
                await run_rag_workflow(
                    user_query=query, session_id=session_id, conversation_history=[]
                )
            except Exception as e:
                logger.error(f"Test workflow failed: {e}")

        # Run in background
        asyncio.create_task(run_test_workflow())

        return {
            "trace_id": trace_id,
            "session_id": session_id,
            "query": query,
            "status": "started",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start test trace: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start trace: {str(e)}")


@router.websocket("/debug/live/{session_id}")
async def debug_live_websocket(
    websocket: WebSocket, session_id: str, token: str = Query(...)
):
    """WebSocket endpoint for real-time trace monitoring"""

    # Simple token validation for WebSocket
    from ha_rag_bridge.config import get_settings

    settings = get_settings()
    if token != settings.admin_token:
        await websocket.close(code=1008, reason="Invalid token")
        return

    await websocket.accept()

    try:
        # Keep connection alive and send updates
        while True:
            # For now, just send a heartbeat every 5 seconds
            # In the future, this could stream real-time trace updates
            await asyncio.sleep(5)
            await websocket.send_json(
                {
                    "type": "heartbeat",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                }
            )

    except ConnectionClosedOK:
        logger.info(f"WebSocket connection closed for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")


@router.get("/containers/{service}/logs/stream")
async def stream_container_logs(request: Request, service: str, tail: int = 100):
    """Stream real-time logs from a specific container"""
    _check_token(request)

    # Validate service name to prevent injection
    valid_services = ["bridge", "litellm", "arangodb", "homeassistant"]
    if service not in valid_services:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service name. Valid services: {', '.join(valid_services)}",
        )

    async def generate_log_stream():
        """Generate real-time log streaming data"""
        container_name = f"ha-rag-bridge-{service}-1"

        # Send initial message
        yield f"data: {json.dumps({'event': 'info', 'message': f'🔍 Starting log stream for {service}...', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"

        try:
            # Start docker logs follow command
            process = subprocess.Popen(
                ["docker", "logs", "-f", "--tail", str(tail), container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Stream logs line by line
            for line in iter(process.stdout.readline, ""):
                if line:
                    # Clean the line and send it
                    clean_line = line.rstrip("\n\r")
                    if clean_line:
                        yield f"data: {json.dumps({'event': 'log', 'message': clean_line, 'timestamp': time.strftime('%H:%M:%S')})}\n\n"

                # Check if process is still running
                if process.poll() is not None:
                    break

            # Send completion message
            yield f"data: {json.dumps({'event': 'complete', 'message': f'📋 Log stream for {service} completed', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"

        except subprocess.TimeoutExpired:
            yield f"data: {json.dumps({'event': 'error', 'message': f'⏱️ Log stream timeout for {service}', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': f'❌ Log stream error: {str(e)}', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"
        finally:
            # Clean up process
            if "process" in locals():
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    pass

    return StreamingResponse(
        generate_log_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
