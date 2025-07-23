"""Metadata ingestion script.


Exports entity metadata from Home Assistant, creates text embeddings using
either the local or OpenAI backend and
upserts the result into ArangoDB. Only static metadata is stored, runtime
state information is ignored.

"""

from __future__ import annotations

import os
import argparse
import time
from datetime import datetime
from typing import List, Optional
import hashlib

import httpx
from arango import ArangoClient

from ha_rag_bridge.logging import get_logger
from ha_rag_bridge.settings import HTTP_TIMEOUT

from .embedding_backends import (
    BaseEmbeddingBackend as EmbeddingBackend,
    LocalBackend,  # noqa: F401 - used in tests
    OpenAIBackend,  # noqa: F401 - used in tests
    get_backend,
)


logger = get_logger(__name__)


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
            logger.warning("http retry", url=url, wait_s=wait, error=str(exc))
            time.sleep(wait)


def fetch_states(entity_id: Optional[str] = None) -> List[dict]:
    """Fetch entity states from Home Assistant."""

    base_url = os.environ["HA_URL"]
    token = os.environ["HA_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(base_url=base_url, headers=headers, timeout=HTTP_TIMEOUT) as client:
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
    """Run the ingestion process. Only changed or new entities are embedded unless full=True."""

    import hashlib

    def get_existing_meta_hash(entity_id: str, col) -> Optional[str]:
        doc = col.get(entity_id)
        if doc:
            return doc.get("meta_hash")
        return None

    states = fetch_states(entity_id)
    if not states:
        return

    backend_name = os.getenv("EMBEDDING_BACKEND", "local").lower()
    logger.info("embedding backend", backend=backend_name)
    if backend_name == "openai":
        emb_backend: EmbeddingBackend = OpenAIBackend()
    elif backend_name == "local":
        emb_backend = LocalBackend()
    else:
        emb_backend = get_backend(backend_name)

    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db_name = os.getenv("ARANGO_DB", "_system")
    db = arango.db(
        db_name,
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )
    col = db.collection("entity")
    edge_col = db.collection("edge")
    area_col = db.collection("area")
    device_col = db.collection("device")

    # Determine if full ingest is requested
    import inspect
    frame = inspect.currentframe()
    full = False
    if frame is not None:
        outer = inspect.getouterframes(frame)
        for record in outer:
            if "full=True" in str(record.code_context):
                full = True
                break

    batch_size = 100
    unchanged_count = 0
    changed_count = 0
    new_count = 0
    failed_count = 0
    total_processed = 0
    for i in range(0, len(states), batch_size):
        batch = states[i : i + batch_size]
        texts = [build_text(e) for e in batch]

        # Skip unchanged entities unless full ingest
        filtered_batch = []
        filtered_texts = []
        for ent, text in zip(batch, texts):
            meta_hash = hashlib.sha256(text.encode()).hexdigest()
            existing_hash = get_existing_meta_hash(ent["entity_id"], col)
            if not full:
                if existing_hash == meta_hash:
                    unchanged_count += 1
                    logger.info("skip unchanged entity", entity=ent["entity_id"])
                    continue
            if existing_hash is None:
                new_count += 1
            else:
                changed_count += 1
            filtered_batch.append(ent)
            filtered_texts.append(text)
            total_processed += 1

        if not filtered_batch:
            continue

        try:
            embeddings = emb_backend.embed(filtered_texts)
        except Exception as exc:  # pragma: no cover - network errors
            logger.warning("embedding error", error=str(exc))
            continue

        docs = []
        ents_for_docs = []
        for ent, emb, text in zip(filtered_batch, embeddings, filtered_texts):
            if not emb:
                logger.warning("missing embedding", entity=ent.get("entity_id"))
                failed_count += 1
                continue
            docs.append(build_doc(ent, emb, text))
            ents_for_docs.append(ent)

        if docs:
            col.insert_many(docs, overwrite=True, overwrite_mode="update")
            edges: List[dict] = []
            for ent, d in zip(ents_for_docs, docs):
                eid = d["_key"]
                attrs = ent.get("attributes", {})
                area_id = attrs.get("area") or attrs.get("area_id")
                device_id = attrs.get("device_id")
                edge_count = 0
                if area_id:
                    area_col.insert(
                        {"_key": area_id, "name": area_id},
                        overwrite=True,
                        overwrite_mode="update",
    logger.info(
        event="ingest summary",
        unchanged=unchanged_count,
        changed=changed_count,
        new=new_count,
        failed=failed_count,
        total=len(states)
    )
                    )
                    key_raw = f"area_contains:area/{area_id}->entity/{eid}"
                    edges.append(
                        {
                            "_key": hashlib.sha1(key_raw.encode()).hexdigest(),
                            "_from": f"area/{area_id}",
                            "_to": f"entity/{eid}",
                            "label": "area_contains",
                            "created_by": "ingest",
                            "ts_created": datetime.utcnow().isoformat(),
                        }
                    )
                    edge_count += 1
                if device_id:
                    device_col.insert(
                        {"_key": device_id, "name": device_id},
                        overwrite=True,
                        overwrite_mode="update",
                    )
                    key_raw = f"device_hosts:device/{device_id}->entity/{eid}"
                    edges.append(
                        {
                            "_key": hashlib.sha1(key_raw.encode()).hexdigest(),
                            "_from": f"device/{device_id}",
                            "_to": f"entity/{eid}",
                            "label": "device_hosts",
                            "created_by": "ingest",
                            "ts_created": datetime.utcnow().isoformat(),
                        }
                    )
                    edge_count += 1
                logger.info("upserted entity", entity=d["entity_id"], edges=edge_count)
            if edges:
                edge_col.insert_many(edges, overwrite=True, overwrite_mode="ignore")


def cli() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--full", action="store_true", help="Full ingest of all states (re-embed everything)")
    group.add_argument("--entity", help="Single entity id")
    args = parser.parse_args()
    if args.full:
        ingest(None)
    else:
        ingest(args.entity)


if __name__ == "__main__":
    cli()
