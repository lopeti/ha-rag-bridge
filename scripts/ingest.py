"""Metadata ingestion script.

Exports entity metadata from Home Assistant, creates OpenAI embeddings and
upserts the result into ArangoDB. Only static metadata is stored, runtime
state information is ignored.
"""

from __future__ import annotations

import os
import argparse
import logging
import time
from typing import List, Optional
import hashlib

import httpx
import openai
from arango import ArangoClient


logger = logging.getLogger(__name__)


class EmbeddingBackend:
    """Abstract embedding backend interface."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return embeddings for the given texts."""
        raise NotImplementedError


class LocalBackend(EmbeddingBackend):
    """Embed texts locally using SentenceTransformers."""

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

    def embed(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return [e.tolist() for e in embeddings]


class OpenAIBackend(EmbeddingBackend):
    """Embed texts using the OpenAI API."""

    def __init__(self) -> None:
        self.client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def embed(self, texts: List[str]) -> List[List[float]]:
        model = "text-embedding-3-large"
        for attempt in range(3):
            try:
                resp = self.client.embeddings.create(model=model, input=texts)
                return [item.embedding for item in resp.data]  # type: ignore[index]
            except Exception as exc:  # pragma: no cover - network errors
                if "quota" in str(exc).lower() and model != "text-embedding-3-small":
                    logger.warning("Quota exceeded, falling back to small model")
                    model = "text-embedding-3-small"
                    continue

                if attempt == 2:
                    raise
                wait = 2**attempt
                logger.warning("Embedding retry in %ss due to %s", wait, exc)
                time.sleep(wait)

        return [[] for _ in texts]

def _retry_get(client: httpx.Client, url: str) -> httpx.Response:
    """GET with up to three retries and exponential backoff."""

    for attempt in range(3):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp
        except Exception as exc:  # pragma: no cover - network errors
            if attempt == 2:
                raise
            wait = 2**attempt
            logger.warning("Retrying %s in %ss due to %s", url, wait, exc)
            time.sleep(wait)


def fetch_states(entity_id: Optional[str] = None) -> List[dict]:
    """Fetch entity states from Home Assistant."""

    base_url = os.environ["HA_URL"]
    token = os.environ["HA_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(base_url=base_url, headers=headers, timeout=10.0) as client:
        url = f"/api/states/{entity_id}" if entity_id else "/api/states"
        resp = _retry_get(client, url)
        data = resp.json()
        return [data] if entity_id else data


def build_text(entity: dict) -> str:
    """Return the concatenated text used for embedding."""

    attrs = entity.get("attributes", {})
    friendly_name = attrs.get("friendly_name", "")
    area = attrs.get("area") or attrs.get("area_id", "")
    domain = entity.get("entity_id", "").split(".")[0]
    synonyms = " ".join(attrs.get("synonyms", []))

    # Add a couple of manual synonyms to help multilingual search
    extra_synonyms = "living room nappali temperature h\u0151m\u00e9rs\u00e9klet"

    return f"{friendly_name}. {area}. {domain}. {synonyms}. {extra_synonyms}".strip()




def build_doc(entity: dict, embedding: List[float], text: str) -> dict:
    """Construct the ArangoDB document for an entity."""

    attrs = entity.get("attributes", {})
    meta_hash = hashlib.sha256(text.encode()).hexdigest()
    return {
        "_key": entity["entity_id"],
        "entity_id": entity["entity_id"],
        "domain": entity["entity_id"].split(".")[0],
        "area": attrs.get("area") or attrs.get("area_id"),
        "friendly_name": attrs.get("friendly_name"),
        "synonyms": attrs.get("synonyms"),
        "embedding": embedding,
        "text": text,
        "meta_hash": meta_hash,
    }


def ingest(entity_id: Optional[str] = None) -> None:
    """Run the ingestion process."""

    logging.basicConfig(level=logging.INFO)

    states = fetch_states(entity_id)
    if not states:
        return

    backend = os.getenv("EMBEDDING_BACKEND", "local").lower()
    logger.info("Using embedding backend: %s", backend)
    if backend == "openai":
        emb_backend: EmbeddingBackend = OpenAIBackend()
    else:
        emb_backend = LocalBackend()

    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db_name = os.getenv("ARANGO_DB", "_system")
    db = arango.db(db_name, username=os.environ["ARANGO_USER"], password=os.environ["ARANGO_PASS"])
    col = db.collection("entity")

    batch_size = 100
    for i in range(0, len(states), batch_size):
        batch = states[i : i + batch_size]
        texts = [build_text(e) for e in batch]
        try:
            embeddings = emb_backend.embed(texts)
        except Exception as exc:  # pragma: no cover - network errors
            logger.warning("Skipping batch due to embedding error: %s", exc)
            continue

        docs = []
        for ent, emb, text in zip(batch, embeddings, texts):
            if not emb:
                logger.warning("Skipping entity %s", ent.get("entity_id"))
                continue
            docs.append(build_doc(ent, emb, text))

        if docs:
            col.insert_many(docs, overwrite=True, overwrite_mode="update")
            for d in docs:
                logger.info("Upserted %s", d["entity_id"])


def cli() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--full", action="store_true", help="Full ingest of all states")
    group.add_argument("--entity", help="Single entity id")
    args = parser.parse_args()
    ingest(None if args.full else args.entity)


if __name__ == "__main__":
    cli()
