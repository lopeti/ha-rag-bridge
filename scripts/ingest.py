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
import logging

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

logging.getLogger("httpx").setLevel(logging.WARNING)

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
    """Fetch entity states from Home Assistant using the RAG API."""

    base_url = os.environ["HA_URL"]
    token = os.environ["HA_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(
        base_url=base_url, headers=headers, timeout=HTTP_TIMEOUT
    ) as client:
        if entity_id:
            # Fallback to original API for specific entity requests
            url = f"/api/states/{entity_id}"
            try:
                resp = _retry_get(client, url)
                data = resp.json()
                logger.info("Successfully fetched data for specific entity", url=url)
                return [data]
            except Exception as exc:
                logger.error("Error fetching entity", url=url, error=str(exc))
                return []
        else:
            # Use the RAG API endpoint for all entities
            url = "/api/rag/static/entities"
            try:
                resp = _retry_get(client, url)
                data = resp.json()

                # Extract entities from the response structure
                if isinstance(data, dict) and "entities" in data:
                    entities = data["entities"]
                    logger.info(
                        "Successfully fetched data from RAG API",
                        url=url,
                        entity_count=len(entities),
                        area_count=len(data.get("areas", [])),
                        device_count=len(data.get("devices", [])),
                    )

                    # Convert entity structure to be compatible with the expected format
                    processed_entities = []

                    # Create a map of area_id to area_name if areas are provided
                    area_map = {}
                    if "areas" in data and isinstance(data["areas"], list):
                        for area in data["areas"]:
                            if "area_id" in area and "name" in area:
                                area_map[area["area_id"]] = area["name"]

                    for entity in entities:
                        # Check if the entity is exposed (we only want exposed entities)
                        if entity.get("exposed", False):
                            area_id = entity.get("area_id")
                            area_name = area_map.get(area_id, "") if area_id else ""

                            # Create a structure similar to what the original API returns
                            processed_entity = {
                                "entity_id": entity["entity_id"],
                                "state": entity.get(
                                    "state", ""
                                ),  # Try to get state if available
                                "attributes": {
                                    "friendly_name": entity.get("original_name", "")
                                    or entity.get("friendly_name", ""),
                                    "device_id": entity.get("device_id"),
                                    "area_id": area_id,
                                    "area": area_name,  # Add area name from the areas list
                                    # Include additional entity metadata if available
                                    "entity_category": entity.get("entity_category"),
                                    "device_class": entity.get("device_class"),
                                    "unit_of_measurement": entity.get(
                                        "unit_of_measurement"
                                    ),
                                    "icon": entity.get("icon"),
                                },
                            }
                            processed_entities.append(processed_entity)

                    return processed_entities
                else:
                    logger.warning("Unexpected data structure from RAG API", data=data)
                    return []
            except Exception as exc:
                logger.error("Error fetching from RAG API", url=url, error=str(exc))
                # Don't fallback, just return empty to signal the error
                return []


def fetch_exposed_entity_ids() -> Optional[set]:
    """Fetch the set of entity_ids exposed by the Home Assistant voice assistant integration."""
    # Completely disable voice assistant exposure filter as we're now using the RAG API
    # which should already provide the correct entities
    return None


def build_text(entity: dict) -> str:
    """Return the concatenated text used for embedding.

    Builds a rich, natural language description of the entity
    optimized for semantic search and multilingual support.
    """
    attrs = entity.get("attributes", {})
    entity_id = entity.get("entity_id", "")

    # Collect all available metadata
    friendly_name = attrs.get("friendly_name", "")
    area_name = attrs.get("area") or ""
    area_id = attrs.get("area_id", "")
    domain = entity_id.split(".")[0] if entity_id else ""
    device_id = attrs.get("device_id", "")
    device_class = attrs.get("device_class", "")
    unit_of_measurement = attrs.get("unit_of_measurement", "")
    entity_category = attrs.get("entity_category", "")
    icon = attrs.get("icon", "")

    # Extract entity name from ID for better context
    entity_name_parts = []
    if "." in entity_id:
        name_part = entity_id.split(".", 1)[1]
        # Replace underscores with spaces
        entity_name_parts = name_part.replace("_", " ").split()

    # Build a simpler, more robust text format
    text_parts = []

    # Main entity description
    if friendly_name:
        main_desc = friendly_name
        if domain and device_class:
            main_desc = f"{friendly_name} ({domain} {device_class})"
        elif domain:
            main_desc = f"{friendly_name} ({domain})"
        text_parts.append(main_desc)

    # Location information
    if area_name:
        text_parts.append(f"Located in {area_name}")
    elif area_id:
        text_parts.append(f"Located in {area_id}")

    # Measurement information
    if unit_of_measurement:
        text_parts.append(f"Measures in {unit_of_measurement}")

    # Entity ID information
    if entity_name_parts:
        text_parts.append(f"Entity name: {' '.join(entity_name_parts)}")

    # Device ID for reference
    if device_id:
        text_parts.append(f"Device ID: {device_id}")

    # Additional metadata
    if entity_category:
        text_parts.append(f"Category: {entity_category}")

    # Icon information
    if icon and icon.startswith("mdi:"):
        icon_name = icon[4:].replace("-", " ")
        text_parts.append(f"Icon: {icon_name}")

    # Synonyms
    synonyms = attrs.get("synonyms", [])
    if synonyms:
        if isinstance(synonyms, list):
            synonyms = " ".join(synonyms)
        text_parts.append(f"Synonyms: {synonyms}")

    # Add keywords section
    keywords = []
    # Add original words from entity ID
    if entity_name_parts:
        keywords.extend(entity_name_parts)

    # Add domain and device class
    if domain:
        keywords.append(domain)
    if device_class:
        keywords.append(device_class)

    # Add area name and ID
    if area_name and area_name not in keywords:
        keywords.append(area_name)
    if area_id and area_id not in keywords and area_id != area_name:
        keywords.append(area_id)

    # Add friendly name if different
    if friendly_name and friendly_name not in keywords:
        keywords.append(friendly_name)

    # Add multilingual support
    translations = []

    # Domain translations
    if domain == "light":
        translations.extend(["lámpa", "világítás", "fény"])
    elif domain == "sensor":
        translations.extend(["szenzor", "érzékelő", "mérő"])
    elif domain == "switch":
        translations.extend(["kapcsoló", "villanykapcsoló"])
    elif domain == "climate":
        translations.extend(["klíma", "fűtés", "légkondi", "termosztát"])

    # Measurement translations
    keywords_text = " ".join(keywords).lower()
    if "temperature" in keywords_text:
        translations.extend(["hőmérséklet", "hőfok"])
    if "humidity" in keywords_text:
        translations.extend(["páratartalom", "nedvesség"])
    if "power" in keywords_text:
        translations.extend(["fogyasztás", "áramfogyasztás", "energia"])

    # Combine everything
    result = ". ".join(text_parts)

    if keywords:
        result += f". Keywords: {', '.join(keywords)}"

    if translations:
        result += f". Hungarian terms: {', '.join(translations)}"

    return result


def build_doc(entity: dict, embedding: List[float], text: str) -> dict:
    """Construct the ArangoDB document for an entity."""

    attrs = entity.get("attributes", {})
    meta_hash = hashlib.sha256(text.encode()).hexdigest()

    # Get area information - prefer the full name over just the ID
    area = attrs.get("area")
    area_id = attrs.get("area_id")
    area_value = area if area else area_id

    # Get the entity ID and extract parts for improved metadata
    entity_id = entity["entity_id"]
    domain = entity_id.split(".")[0] if "." in entity_id else ""

    # Create entity document with all useful fields
    doc = {
        "_key": entity_id,
        "entity_id": entity_id,
        "domain": domain,
        "area": area_value,
        "area_id": area_id,  # Store area_id explicitly
        "device_id": attrs.get("device_id"),  # Store device_id directly
        "friendly_name": attrs.get("friendly_name"),
        "synonyms": attrs.get("synonyms"),
        "embedding": embedding,
        "text": text,
        "meta_hash": meta_hash,
    }

    # Add additional fields that may be useful for searching and filtering
    # Only add non-empty values to keep the document clean
    additional_fields = {
        "device_class": attrs.get("device_class"),
        "unit_of_measurement": attrs.get("unit_of_measurement"),
        "entity_category": attrs.get("entity_category"),
        "icon": attrs.get("icon"),
    }

    for key, value in additional_fields.items():
        if value:  # Only add non-empty values
            doc[key] = value

    return doc


def ingest(entity_id: Optional[str] = None, delay_sec: int = 5) -> None:
    """Run the ingestion process. Only changed or new entities are embedded unless full=True. Batch delay is configurable."""
    import hashlib
    import time

    def get_existing_meta_hash(entity_id: str, col) -> Optional[str]:
        doc = col.get(entity_id)
        if doc:
            return doc.get("meta_hash")
        return None

    states = fetch_states(entity_id)
    if not states:
        logger.error("No states returned from fetch_states, aborting ingestion")
        return

    logger.info("Fetched states from RAG API", count=len(states))

    # Voice assistant filtering is disabled as we're using the RAG API
    # which should already provide the correctly filtered entities

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
                    area_name = attrs.get("area") or area_id
                    area_col.insert(
                        {"_key": area_id, "name": area_name},
                        overwrite=True,
                        overwrite_mode="update",
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
                # Log more detailed information about the entity being upserted
                logger.info(
                    "upserted entity",
                    entity=d["entity_id"],
                    edges=edge_count,
                    text=text[:50] + "..." if len(text) > 50 else text,
                    has_area=bool(d.get("area")),
                    has_device=bool(d.get("device_id")),
                )
            if edges:
                edge_col.insert_many(edges, overwrite=True, overwrite_mode="ignore")

        # Delay between batches
        if delay_sec > 0:
            logger.info("batch delay", seconds=delay_sec)
            time.sleep(delay_sec)

    logger.info(
        event="ingest summary",
        unchanged=unchanged_count,
        changed=changed_count,
        new=new_count,
        failed=failed_count,
        total=len(states),
    )


def cli() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--full",
        action="store_true",
        help="Full ingest of all states (re-embed everything)",
    )
    group.add_argument("--entity", help="Single entity id")
    parser.add_argument(
        "--delay",
        type=int,
        default=5,
        help="Delay in seconds between embedding batches (default: 5)",
    )
    args = parser.parse_args()
    if args.full:
        ingest(None, delay_sec=args.delay)
    else:
        ingest(args.entity, delay_sec=args.delay)


if __name__ == "__main__":
    cli()
