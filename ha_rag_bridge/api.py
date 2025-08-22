"""
Home Assistant RAG Bridge API

Ez a modul biztosít egy REST API-t a ha-rag-bridge funkcionalitásához,
ami lehetővé teszi a RAG (Retrieval Augmented Generation) használatát
Home Assistant entitásokkal és a toolok végrehajtását.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Sequence
import os
import json
import httpx
from datetime import datetime
from arango import ArangoClient

from ha_rag_bridge.logging import get_logger
from ha_rag_bridge.settings import HTTP_TIMEOUT
from app.services.integrations.embeddings import (
    BaseEmbeddingBackend as EmbeddingBackend,
    LocalBackend,
    OpenAIBackend,
    get_backend,
)

# Konfiguráljuk a loggert
logger = get_logger(__name__)

# Létrehozzuk a FastAPI alkalmazást
app = FastAPI(
    title="HA-RAG Bridge API",
    description="Home Assistant RAG Bridge API a LiteLLM integráció számára",
    version="0.1.0",
)

# CORS beállítása
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Éles környezetben ezt korlátozni kell
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Modellek és séma definíciók
class QueryRequest(BaseModel):
    """RAG query kérés"""

    question: str
    top_k: int = 5


class EntityInfo(BaseModel):
    """Entitás információk"""

    entity_id: str
    name: str
    state: Optional[str] = "unknown"
    aliases: List[str] = []
    domain: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    """RAG query válasz"""

    relevant_entities: List[EntityInfo]
    formatted_content: Optional[str] = None
    raw_results: Optional[List[Dict[str, Any]]] = None


class ToolFunctionCall(BaseModel):
    """Tool függvény hívás"""

    name: str
    arguments: str


class ToolCall(BaseModel):
    """Tool hívás"""

    id: str
    type: str = "function"
    function: ToolFunctionCall


class ToolExecutionRequest(BaseModel):
    """Tool végrehajtási kérés"""

    tool_calls: List[ToolCall]
    context: Optional[Dict[str, Any]] = None


class ToolExecutionResult(BaseModel):
    """Tool végrehajtás eredménye"""

    id: str
    status: str
    result: Optional[str] = None
    error: Optional[str] = None


# Segéd függvények
def get_embedding_backend() -> EmbeddingBackend:
    """Visszaadja a megfelelő embedding backend-et"""
    backend_name = os.getenv("EMBEDDING_BACKEND", "local").lower()
    if backend_name == "openai":
        return OpenAIBackend()
    elif backend_name == "local":
        return LocalBackend()
    else:
        return get_backend(backend_name)


def get_arango_db():
    """Létrehoz egy kapcsolatot az ArangoDB-vel"""
    arango_url = os.environ.get("ARANGO_URL", "http://localhost:8529")
    db_name = os.getenv("ARANGO_DB", "_system")

    try:
        arango = ArangoClient(hosts=arango_url)
        db = arango.db(
            db_name,
            username=os.environ.get("ARANGO_USER", "root"),
            password=os.environ.get("ARANGO_PASS", ""),
        )
        return db
    except Exception as e:
        logger.error(f"Hiba az ArangoDB kapcsolat létrehozásakor: {e}")
        raise HTTPException(
            status_code=500, detail=f"Adatbázis kapcsolódási hiba: {str(e)}"
        )


def retrieve_entities_from_db(
    db, query_vector: Sequence[float], question: str, top_k: int = 5
) -> List[Dict[str, Any]]:
    """Lekéri a releváns entitásokat az ArangoDB-ből"""
    from app.main import retrieve_entities

    try:
        results = retrieve_entities(
            db, query_vector, question, k_list=(top_k, top_k * 2)
        )
        return results
    except Exception as e:
        logger.error(f"Hiba az entitások lekérésekor: {e}")
        raise HTTPException(
            status_code=500, detail=f"Entitás lekérdezési hiba: {str(e)}"
        )


def format_entities_for_prompt(entities: List[EntityInfo]) -> str:
    """Formázza az entitásokat a prompt számára"""
    if not entities:
        return "No relevant entities found."

    result = "Available Devices (relevant to your query):\n```csv\nentity_id,name,state,aliases\n"
    for entity in entities:
        aliases = "/".join(entity.aliases)
        result += f"{entity.entity_id},{entity.name},{entity.state},{aliases}\n"
    result += "```"
    return result


# API végpontok
@app.get("/")
async def root():
    """Alap végpont"""
    return {"message": "HA-RAG Bridge API", "status": "active"}


@app.get("/health")
async def health_check():
    """Egészség ellenőrzés"""
    try:
        # Ellenőrizzük az adatbázis kapcsolatot
        _ = get_arango_db()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"

    try:
        # Ellenőrizzük az embedding backendet
        _ = get_embedding_backend()
        embedding_status = "ok"
    except Exception as e:
        embedding_status = f"error: {str(e)}"

    return {
        "status": (
            "healthy" if db_status == "ok" and embedding_status == "ok" else "unhealthy"
        ),
        "timestamp": datetime.now().isoformat(),
        "components": {"database": db_status, "embedding_backend": embedding_status},
    }


@app.post("/api/query", response_model=QueryResponse)
async def query_relevant_entities(request: QueryRequest):
    """
    RAG lekérdezés végrehajtása, releváns entitások visszaadása.

    Ez a végpont fogadja a felhasználó kérdését, és visszaadja a releváns entitásokat.
    """
    logger.info(f"RAG lekérdezés: {request.question}")

    # Embedding backend létrehozása
    try:
        embedding_backend = get_embedding_backend()
    except Exception as e:
        logger.error(f"Embedding backend hiba: {e}")
        raise HTTPException(status_code=500, detail=f"Embedding backend hiba: {str(e)}")

    # Kérdés beágyazás készítése
    try:
        query_vector = embedding_backend.embed([request.question])[0]
    except Exception as e:
        logger.error(f"Embedding készítési hiba: {e}")
        raise HTTPException(
            status_code=500, detail=f"Embedding készítési hiba: {str(e)}"
        )

    # ArangoDB kapcsolat létrehozása
    db = get_arango_db()

    # Releváns entitások lekérése
    raw_results = retrieve_entities_from_db(
        db, query_vector, request.question, request.top_k
    )

    # Entitások formázása
    relevant_entities = []
    for doc in raw_results[: request.top_k]:
        entity_id = doc.get("entity_id", "")
        if entity_id:
            entity_data = EntityInfo(
                entity_id=entity_id,
                name=doc.get("name", entity_id),
                state=doc.get("state", "unknown"),
                aliases=doc.get("aliases", []),
                domain=doc.get("domain", None),
                attributes=doc.get("attributes", {}),
            )
            relevant_entities.append(entity_data)

    # Formázott tartalom készítése
    formatted_content = format_entities_for_prompt(relevant_entities)

    return QueryResponse(
        relevant_entities=relevant_entities,
        formatted_content=formatted_content,
        raw_results=raw_results[: request.top_k],
    )


@app.post("/api/execute_tool", response_model=Dict[str, List[ToolExecutionResult]])
async def execute_tool(request: ToolExecutionRequest):
    """
    Home Assistant tool hívások végrehajtása.

    Ez a végpont fogadja a tool hívásokat és végrehajtja őket a Home Assistant-ban.
    """
    logger.info(f"Tool végrehajtás kérés: {len(request.tool_calls)} tool")

    ha_url = os.environ.get("HA_URL")
    ha_token = os.environ.get("HA_TOKEN")

    if not ha_url or not ha_token:
        raise HTTPException(
            status_code=500, detail="Home Assistant URL vagy token nincs konfigurálva"
        )

    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json",
    }

    results = []

    async with httpx.AsyncClient(
        base_url=ha_url, headers=headers, timeout=HTTP_TIMEOUT
    ) as client:
        for tool_call in request.tool_calls:
            result = ToolExecutionResult(
                id=tool_call.id, status="error", error="Ismeretlen hiba"
            )

            try:
                function = tool_call.function
                name = function.name

                try:
                    arguments = json.loads(function.arguments)
                except json.JSONDecodeError:
                    result.error = (
                        f"Érvénytelen JSON argumentumok: {function.arguments}"
                    )
                    results.append(result)
                    continue

                if "." in name:
                    domain, service = name.split(".", 1)

                    logger.info(
                        f"Home Assistant szolgáltatás hívás: {domain}.{service} argumentumokkal: {arguments}"
                    )

                    # Home Assistant szolgáltatás hívás
                    try:
                        response = await client.post(
                            f"/api/services/{domain}/{service}",
                            json=arguments,
                            timeout=10.0,
                        )

                        response.raise_for_status()
                        result.status = "success"
                        result.result = json.dumps(
                            response.json() if response.text else {}
                        )
                        result.error = None

                        logger.info(f"Sikeres szolgáltatás hívás: {domain}.{service}")
                    except httpx.HTTPError as e:
                        error_msg = f"HTTP hiba a szolgáltatás hívásakor: {str(e)}"
                        logger.error(error_msg)
                        result.error = error_msg
                else:
                    error_msg = f"Érvénytelen szolgáltatás név: {name}"
                    logger.error(error_msg)
                    result.error = error_msg
            except Exception as e:
                error_msg = f"Hiba a tool végrehajtásakor: {str(e)}"
                logger.error(error_msg)
                result.error = error_msg

            results.append(result)

    return {"tool_execution_results": results}
