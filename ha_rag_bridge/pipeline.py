from __future__ import annotations

import os
from typing import Dict, Any
from arango import ArangoClient

from scripts.embedding_backends import (
    BaseEmbeddingBackend as EmbeddingBackend,
    LocalBackend,
    OpenAIBackend,
    get_backend,
)

from app.main import retrieve_entities


def query(question: str, top_k: int = 3) -> Dict[str, Any]:
    """Query the RAG pipeline to retrieve relevant entities for a question.

    Args:
        question: The user's question
        top_k: Maximum number of relevant entities to return

    Returns:
        A dictionary with question, top_k, results (list of retrieved documents),
        and a prompt for the LLM
    """
    # Determine embedding backend
    backend_name = os.getenv("EMBEDDING_BACKEND", "local").lower()
    if backend_name == "openai":
        emb_backend: EmbeddingBackend = OpenAIBackend()
    elif backend_name == "local":
        emb_backend = LocalBackend()
    else:
        emb_backend = get_backend(backend_name)

    # Create embedding for the question
    query_vector = emb_backend.embed([question])[0]

    # Connect to ArangoDB
    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db_name = os.getenv("ARANGO_DB", "_system")
    db = arango.db(
        db_name,
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )

    # Retrieve relevant entities
    results = retrieve_entities(db, query_vector, question, k_list=(top_k, top_k * 3))

    # Format entities for the prompt template
    relevant_entities = []
    for doc in results[:top_k]:
        entity_id = doc.get("entity_id", "")
        if entity_id:
            entity_data = {
                "entity_id": entity_id,
                "name": doc.get("name", entity_id),
                "state": doc.get("state", "unknown"),
                "aliases": doc.get("aliases", []),
            }
            relevant_entities.append(entity_data)

    # Generate prompt
    prompt = "Te egy Home Assistant asszisztens vagy. "
    prompt += f"Válaszolj a következő kérdésre a dokumentumok alapján: {question}"

    return {
        "question": question,
        "top_k": top_k,
        "results": results,
        "relevant_entities": relevant_entities,
        "prompt": prompt,
    }
