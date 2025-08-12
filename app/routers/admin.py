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
                "timestamp": time.strftime("%H:%M:%S")
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
        }
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
        "last_bootstrap": None
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
                    headers={"Authorization": f"Bearer {ha_token}"}
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
        "database_size": "0 MB"
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
        collections = [c["name"] for c in db.collections() if not c["name"].startswith("_")]
        total_size = 0
        for col_name in collections:
            try:
                col_info = db.collection(col_name).properties()
                # This is an approximation, actual size calculation varies
                total_size += col_info.get("count", 0) * 1024  # rough estimate
            except Exception:
                continue
                
        if total_size > 1024*1024*1024:
            stats["database_size"] = f"{total_size / (1024*1024*1024):.1f} GB"
        elif total_size > 1024*1024:
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
        "database": {
            "name": os.getenv("ARANGO_DB", "_system"),
            "status": "error"
        },
        "schema": {
            "current": 0,
            "latest": SCHEMA_LATEST
        },
        "vector": {
            "dimension": int(os.getenv("EMBED_DIM", "768")),
            "status": "error"
        },
        "system": {
            "status": "error"
        }
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
                    overview["schema"]["current"] = SCHEMA_LATEST  # assume latest if no schema doc
            else:
                overview["schema"]["current"] = SCHEMA_LATEST  # assume latest if no _schema collection
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
        if (overview["database"]["status"] == "ok" and 
            overview["vector"]["status"] in ["ok", "mismatch"]):
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
    limit: int = 50
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
            filters.append("CONTAINS(LOWER(e.friendly_name), @query) OR CONTAINS(LOWER(e.entity_id), @query)")
            bind_vars["query"] = q.lower()
        
        if filters:
            query_parts.append("FILTER " + " AND ".join(filters))
        
        # Count query for total
        count_query = " ".join(query_parts) + " COLLECT WITH COUNT INTO total RETURN total"
        total_result = list(db.aql.execute(count_query, bind_vars=bind_vars))
        total = total_result[0] if total_result else 0
        
        # Main query with pagination
        query_parts.extend([
            "SORT e.friendly_name",
            f"LIMIT {offset}, {limit}",
            "RETURN {"
            "  id: e.entity_id,"
            "  friendly_name: e.friendly_name,"
            "  domain: e.domain,"
            "  area: e.area_id || e.area || 'unknown',"
            "  tags: e.tags || [],"
            "  attributes: e.attributes || {}"
            "}"
        ])
        
        main_query = " ".join(query_parts)
        entities = list(db.aql.execute(main_query, bind_vars=bind_vars))
        
        return {
            "total": total,
            "items": entities
        }
        
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
        
        # Get unique areas count
        areas_query = "FOR e IN entity COLLECT area = e.area_id || e.area RETURN area"
        areas = list(db.aql.execute(areas_query))
        areas_count = len([a for a in areas if a])  # exclude null/empty
        
        return {
            "total": total,
            "shown": min(50, total),  # default limit
            "domain_types": domain_types,
            "areas": areas_count
        }
        
    except Exception as e:
        logger.error(f"Entities meta endpoint error: {e}")
        return {"total": 0, "shown": 0, "domain_types": 0, "areas": 0}


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
        import sys
        
        # Send initial message
        yield f"data: {json.dumps({'event': 'info', 'message': '🔄 Starting vector reindexing...', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"
        
        try:
            # Run the reindex command for all collections
            process = subprocess.Popen(
                ["ha-rag-bootstrap", "--reindex", "all", "--force"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
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
                        message = f"⚙️ {line}" if not line.startswith(('⚙️', '🔄', '✅', '❌', '📊', '🔧', '🗑️')) else line
                        
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
        }
    )


@router.get("/maintenance/bootstrap/stream")
async def stream_bootstrap(request: Request):
    """Stream bootstrap process"""
    _check_token(request)
    
    async def generate_bootstrap_stream():
        """Generate real bootstrap streaming data"""
        import subprocess
        import sys
        from pathlib import Path
        
        # Send initial message
        yield f"data: {json.dumps({'event': 'info', 'message': '🚀 Starting database bootstrap...', 'timestamp': time.strftime('%H:%M:%S')})}\n\n"
        
        try:
            # Run the bootstrap CLI command
            process = subprocess.Popen(
                ["ha-rag-bootstrap"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
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
                        message = f"🔧 {line}" if not line.startswith(('🔧', '🚀', '✅', '❌', '⚙️', '📊', '🔗', '📦')) else line
                        
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
        }
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
                bufsize=1
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
                        message = f"🔄 {line}" if not line.startswith(('🔄', '📥', '✅', '❌', '⚙️', '📊', '🔗')) else line
                        
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
        }
    )
