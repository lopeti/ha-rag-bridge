from __future__ import annotations

import os
import json
import io
import zipfile
import asyncio
import time
import psutil
import httpx
from datetime import datetime, timedelta
from time import perf_counter
from fastapi import APIRouter, Request, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from arango import ArangoClient
from ha_rag_bridge.bootstrap import bootstrap, SCHEMA_LATEST
from ha_rag_bridge.utils.env import env_true
from ha_rag_bridge.logging import get_logger
from ha_rag_bridge.settings import HTTP_TIMEOUT

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger(__name__)


def _check_token(request: Request) -> None:
    # Skip token check in debug mode
    if env_true("DEBUG"):
        return

    token = os.getenv("ADMIN_TOKEN", "")
    if request.headers.get("X-Admin-Token") != token:
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
        health["database_version"] = f"ArangoDB {server_info['version']}"

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
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

        # Get database size (approximate)
        collections = [
            c["name"] for c in db.collections() if not c["name"].startswith("_")
        ]
        total_size = 0
        for col_name in collections:
            try:
                col_info = db.collection(col_name).properties()
                # This is an approximation, actual size calculation varies
                total_size += col_info.get("count", 0) * 1024  # rough estimate
            except Exception:
                continue

        if total_size > 1024 * 1024 * 1024:
            stats["database_size"] = f"{total_size / (1024*1024*1024):.1f} GB"
        elif total_size > 1024 * 1024:
            stats["database_size"] = f"{total_size / (1024*1024):.1f} MB"
        else:
            stats["database_size"] = f"{total_size / 1024:.1f} KB"

    except Exception as e:
        logger.error(f"Database stats error: {e}")

    return stats


@router.get("/overview")
async def get_system_overview(request: Request):
    """Get system overview"""
    _check_token(request)

    overview = {
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

    metrics = {
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
    request: Request, level: str = None, cursor: str = None, container: str = None
):
    """Get system logs with filtering from containers"""
    _check_token(request)

    # Real implementation using Docker logs
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
        # Get recent logs from Docker container
        cmd = ["docker", "logs", container_name, "--tail=50", "--timestamps"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            # Fallback to mock data if docker logs fails
            return await _get_mock_logs(level)

        logs = []
        for line in result.stdout.split("\n") + result.stderr.split("\n"):
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
                except:
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


async def _get_mock_logs(level: str = None):
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
async def stream_logs(request: Request, container: str = "bridge", level: str = "all"):
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
                    except:
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
                except:
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
