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
from .friendly_name_generator import FriendlyNameGenerator

logging.getLogger("httpx").setLevel(logging.WARNING)

logger = get_logger(__name__)


def _infer_area_from_names(
    attrs: dict, entity_id: str, area_map: dict
) -> Optional[str]:
    """
    Intelligently infer area from entity names, device names, and friendly names.

    Args:
        attrs: Entity attributes including names and device info
        entity_id: Full entity ID
        area_map: Mapping of area_id to area_name

    Returns:
        Inferred area_id if found, None otherwise
    """
    # Collect all text sources for analysis
    text_sources = []

    # Add entity friendly name
    if attrs.get("friendly_name"):
        text_sources.append(attrs["friendly_name"].lower())

    # Add original name
    if attrs.get("original_name"):
        text_sources.append(attrs["original_name"].lower())

    # Add device name if available
    if attrs.get("device_name"):
        text_sources.append(attrs["device_name"].lower())

    # Add entity_id parts (remove domain prefix)
    entity_name = entity_id.split(".", 1)[-1] if "." in entity_id else entity_id
    text_sources.append(entity_name.lower().replace("_", " "))

    # Hungarian room name patterns with English equivalents
    room_patterns = {
        "nappali": ["nappali", "living", "room", "livingroom"],
        "konyha": ["konyha", "kitchen", "konyhába", "konyhában"],
        "hálószoba": ["hálószoba", "bedroom", "hálóban", "hálóba", "sleeping"],
        "fürdőszoba": ["fürdőszoba", "fürdő", "bathroom", "bath", "wc", "klotyó"],
        "dolgozó": ["dolgozó", "office", "study", "munka", "iroda"],
        "gyerekszoba": ["gyerek", "gyermek", "child", "kids", "baba"],
        "előtér": ["előtér", "hall", "hallway", "bejárat", "entrance"],
        "kert": ["kert", "garden", "outdoor", "outside", "kint", "kültér"],
        "garázs": ["garázs", "garage", "car"],
        "pince": ["pince", "basement", "cellar"],
        "padlás": ["padlás", "attic", "loft"],
    }

    # Check each area pattern against all text sources
    for area_candidate, patterns in room_patterns.items():
        for text_source in text_sources:
            for pattern in patterns:
                if pattern in text_source:
                    # Check if this area exists in area_map
                    matching_area_id = None

                    # Direct match with area_id
                    if area_candidate in area_map:
                        matching_area_id = area_candidate
                    else:
                        # Search in area names (case insensitive)
                        for area_id, area_name in area_map.items():
                            if (
                                area_name
                                and area_candidate.lower() in area_name.lower()
                            ) or (
                                area_id and area_candidate.lower() in area_id.lower()
                            ):
                                matching_area_id = area_id
                                break

                    if matching_area_id:
                        logger.debug(
                            f"Area pattern '{pattern}' in '{text_source}' matched to '{matching_area_id}'"
                        )
                        return matching_area_id

    # Fallback: direct area name matching
    for text_source in text_sources:
        for area_id, area_name in area_map.items():
            if area_name and area_name.lower() in text_source:
                logger.debug(f"Direct area name '{area_name}' found in '{text_source}'")
                return area_id
            if area_id and area_id.lower() in text_source:
                logger.debug(f"Direct area ID '{area_id}' found in '{text_source}'")
                return area_id

    return None


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


def fetch_states(entity_id: Optional[str] = None) -> dict:
    """Fetch entity states from Home Assistant using the RAG API.

    Returns a dictionary with ``entities``, ``areas`` and ``devices`` lists. The
    entity objects are normalized to match the structure expected by the rest of
    the ingest pipeline.
    """

    base_url = os.environ["HA_URL"]
    token = os.environ["HA_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(
        base_url=base_url, headers=headers, timeout=HTTP_TIMEOUT
    ) as client:
        if entity_id:
            # For specific entity requests, we still need areas and devices for inference
            # First get the RAG endpoint for full context
            rag_url = "/api/rag/static/entities"
            entity_url = f"/api/states/{entity_id}"

            try:
                # Get areas and devices from RAG endpoint for inference
                rag_resp = _retry_get(client, rag_url)
                rag_data = rag_resp.json()
                areas = rag_data.get("areas", [])
                devices = rag_data.get("devices", [])

                # Get specific entity data
                entity_resp = _retry_get(client, entity_url)
                entity_data = entity_resp.json()

                logger.info(
                    "Successfully fetched data for specific entity with context",
                    entity_url=entity_url,
                    areas_count=len(areas),
                    devices_count=len(devices),
                )
                return {"entities": [entity_data], "areas": areas, "devices": devices}
            except Exception as exc:
                logger.error(
                    "Error fetching entity", entity_url=entity_url, error=str(exc)
                )
                return {"entities": [], "areas": [], "devices": []}
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
                            area_id = area.get("area_id") or area.get("id")
                            if area_id and "name" in area:
                                area_map[area_id] = area["name"]

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

                    return {
                        "entities": processed_entities,
                        "areas": data.get("areas", []),
                        "devices": data.get("devices", []),
                    }
                else:
                    logger.warning("Unexpected data structure from RAG API", data=data)
                    return {"entities": [], "areas": [], "devices": []}
            except Exception as exc:
                logger.error("Error fetching from RAG API", url=url, error=str(exc))
                # Don't fallback, just return empty to signal the error
                return {"entities": [], "areas": [], "devices": []}


def fetch_exposed_entity_ids() -> Optional[set]:
    """Fetch the set of entity_ids exposed by the Home Assistant voice assistant integration."""
    # Completely disable voice assistant exposure filter as we're now using the RAG API
    # which should already provide the correct entities
    return None


def build_text(
    entity: dict, friendly_name_generator: Optional[FriendlyNameGenerator] = None
) -> str:
    """Return the concatenated text optimized for multilingual embeddings.

    Builds a hybrid text combining Hungarian base with English keywords
    for optimal multilingual semantic matching with single embedding.

    Args:
        entity: Entity data dictionary
        friendly_name_generator: Optional generator to create friendly names for entities that lack them
    """
    attrs = entity.get("attributes", {})
    entity_id = entity.get("entity_id", "")

    # Collect all available metadata
    # Check both RAG API structure and states API structure for friendly_name
    friendly_name = entity.get("friendly_name", "") or attrs.get("friendly_name", "")

    # Generate friendly name if missing and generator provided
    if not friendly_name and friendly_name_generator and entity_id:
        suggestion = friendly_name_generator.generate_suggestion(entity)
        if suggestion.confidence >= 0.7:  # Only use high-confidence suggestions
            friendly_name = suggestion.suggested_name
            logger.debug(
                f"Generated friendly name for {entity_id}: '{friendly_name}' (confidence: {suggestion.confidence:.2f})"
            )
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
        if domain and device_class and domain != device_class:
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

    # Hungarian translation support for semantic richness
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

    # Measurement translations based on context
    entity_text = " ".join(text_parts).lower()
    if "temperature" in entity_text or "°c" in entity_text:
        translations.extend(["hőmérséklet", "hőfok"])
    if "humidity" in entity_text or "%" in entity_text:
        translations.extend(["páratartalom", "nedvesség"])
    if "power" in entity_text or "watt" in entity_text:
        translations.extend(["fogyasztás", "áramfogyasztás", "energia"])

    # Build hybrid text: Hungarian base + English keywords for multilingual embedding
    result = ". ".join(text_parts)

    # Add English keywords for cross-language matching (avoiding duplicates)
    english_keywords = []

    # Extract English area names
    if area_name:
        english_area = _translate_area_name_to_english(area_name)
        if english_area != area_name and english_area not in english_keywords:
            english_keywords.append(english_area)

    # Add domain (only if different from device_class to avoid duplication)
    if domain and domain not in english_keywords:
        if not device_class or domain != device_class:
            english_keywords.append(domain)
    if device_class and device_class not in english_keywords:
        english_keywords.append(device_class)

    # Add entity name parts translated to English
    if entity_name_parts:
        for part in entity_name_parts:
            english_term = _translate_term_to_english(part)
            if english_term != part and english_term not in english_keywords:
                english_keywords.append(english_term)

    # Add measurement units (usually already in English)
    if unit_of_measurement and unit_of_measurement not in english_keywords:
        english_keywords.append(unit_of_measurement)

    # Add semantic English terms
    english_domain_terms = _get_english_domain_terms(domain, unit_of_measurement)
    for term in english_domain_terms:
        if term not in english_keywords:
            english_keywords.append(term)

    # Combine Hungarian text with English keywords for optimal multilingual matching
    if english_keywords:
        # Remove duplicates while preserving order
        unique_keywords = list(
            dict.fromkeys([k for k in english_keywords if k and k.strip()])
        )
        if unique_keywords:
            # More natural integration without explicit "English:" label
            result += f". Keywords: {' '.join(unique_keywords)}"

    # Keep original translations for Hungarian semantic richness
    if translations:
        result += f". Hungarian: {', '.join(translations)}"

    aliases = attrs.get("area_aliases") or []
    if aliases:
        result += f". Aliases: {' '.join(aliases)}"

    return result


def build_system_text(entity: dict) -> str:
    """Return the concatenated text for system language (English).

    Builds a clean, English-only description optimized for
    vector embeddings and semantic search consistency.
    """
    attrs = entity.get("attributes", {})
    entity_id = entity.get("entity_id", "")

    # Collect all available metadata
    # Check both RAG API structure and states API structure for friendly_name
    friendly_name = entity.get("friendly_name", "") or attrs.get("friendly_name", "")
    area_name = attrs.get("area") or ""
    area_id = attrs.get("area_id", "")
    domain = entity_id.split(".")[0] if entity_id else ""
    device_class = attrs.get("device_class", "")
    unit_of_measurement = attrs.get("unit_of_measurement", "")
    entity_category = attrs.get("entity_category", "")
    icon = attrs.get("icon", "")

    # Extract entity name from ID
    entity_name_parts = []
    if "." in entity_id:
        name_part = entity_id.split(".", 1)[1]
        entity_name_parts = name_part.replace("_", " ").split()

    # Build English-only text parts
    text_parts = []

    # Main entity description in English
    if friendly_name:
        # Translate Hungarian area names to English
        english_area_name = _translate_area_name_to_english(area_name)

        # Use English area name in friendly name if it contains Hungarian
        english_friendly_name = friendly_name
        if area_name and area_name in friendly_name and english_area_name != area_name:
            english_friendly_name = friendly_name.replace(area_name, english_area_name)

        main_desc = english_friendly_name
        if domain and device_class:
            main_desc = f"{english_friendly_name} ({domain} {device_class})"
        elif domain:
            main_desc = f"{english_friendly_name} ({domain})"
        text_parts.append(main_desc)

    # Location information in English
    if area_name:
        english_area = _translate_area_name_to_english(area_name)
        text_parts.append(f"Located in {english_area}")
    elif area_id:
        english_area_id = _translate_area_name_to_english(area_id)
        text_parts.append(f"Located in {english_area_id}")

    # Measurement information
    if unit_of_measurement:
        text_parts.append(f"Measures in {unit_of_measurement}")

    # Entity name in English
    if entity_name_parts:
        english_entity_parts = [
            _translate_term_to_english(part) for part in entity_name_parts
        ]
        text_parts.append(f"Entity name: {' '.join(english_entity_parts)}")

    # Category and device info
    if entity_category:
        text_parts.append(f"Category: {entity_category}")

    # Icon information
    if icon and icon.startswith("mdi:"):
        icon_name = icon[4:].replace("-", " ")
        text_parts.append(f"Icon: {icon_name}")

    # English keywords only
    keywords = []
    if entity_name_parts:
        english_parts = [_translate_term_to_english(part) for part in entity_name_parts]
        keywords.extend(english_parts)

    if domain:
        keywords.append(domain)
    if device_class:
        keywords.append(device_class)

    # English area terms
    if area_name:
        english_area = _translate_area_name_to_english(area_name)
        if english_area not in keywords:
            keywords.append(english_area)

    # English domain terms
    english_domain_terms = _get_english_domain_terms(domain, unit_of_measurement)
    keywords.extend(english_domain_terms)

    # Combine everything
    result = ". ".join(text_parts)

    if keywords:
        # Remove duplicates and empty strings
        unique_keywords = list(dict.fromkeys([k for k in keywords if k]))
        result += f". Keywords: {', '.join(unique_keywords)}"

    return result


def _translate_area_name_to_english(hungarian_area: str) -> str:
    """Translate Hungarian area names to English."""
    area_translations = {
        "nappali": "living room",
        "konyha": "kitchen",
        "hálószoba": "bedroom",
        "háló": "bedroom",
        "fürdőszoba": "bathroom",
        "fürdő": "bathroom",
        "dolgozószoba": "office",
        "iroda": "office",
        "előszoba": "hallway",
        "pince": "basement",
        "padlás": "attic",
        "terasz": "terrace",
        "erkély": "balcony",
        "garázs": "garage",
        "kert": "garden",
        "kerti": "garden",
        "ház": "house",
        "otthon": "home",
    }
    return area_translations.get(hungarian_area.lower(), hungarian_area)


def _translate_term_to_english(hungarian_term: str) -> str:
    """Translate common Hungarian terms to English."""
    term_translations = {
        "lámpa": "light",
        "világítás": "lighting",
        "fény": "light",
        "szenzor": "sensor",
        "érzékelő": "sensor",
        "mérő": "meter",
        "kapcsoló": "switch",
        "klíma": "climate",
        "fűtés": "heating",
        "termosztát": "thermostat",
        "hőmérséklet": "temperature",
        "páratartalom": "humidity",
        "nedvesség": "humidity",
        "fogyasztás": "consumption",
        "energia": "energy",
        "áram": "power",
    }
    return term_translations.get(hungarian_term.lower(), hungarian_term)


def _get_english_domain_terms(domain: str, unit_of_measurement: str = "") -> list:
    """Get English terms for domain and measurement context."""
    terms = []

    # Domain-specific English terms
    domain_terms = {
        "light": ["light", "lighting", "lamp", "illumination"],
        "sensor": ["sensor", "detector", "measurement"],
        "switch": ["switch", "toggle", "control"],
        "climate": ["climate", "temperature", "hvac", "thermostat"],
    }

    if domain in domain_terms:
        terms.extend(domain_terms[domain])

    # Unit-based terms
    if unit_of_measurement:
        unit_lower = unit_of_measurement.lower()
        if "°c" in unit_lower or "celsius" in unit_lower:
            terms.extend(["temperature", "degrees"])
        elif "%" in unit_lower and any(
            word in unit_lower for word in ["humidity", "moisture"]
        ):
            terms.extend(["humidity", "moisture"])
        elif "w" in unit_lower or "watt" in unit_lower:
            terms.extend(["power", "consumption", "energy"])

    return terms


def build_doc(entity: dict, embedding: List[float], text: str) -> dict:
    """Construct the ArangoDB document for an entity with multilingual text."""

    attrs = entity.get("attributes", {})
    # Hash hybrid text for change detection (text_system is same as text now)
    meta_hash = hashlib.sha256(text.encode()).hexdigest()

    # Get area information - prefer the full name over just the ID
    area = attrs.get("area")
    area_id = attrs.get("area_id")
    area_value = area if area else area_id

    # Get the entity ID and extract parts for improved metadata
    entity_id = entity["entity_id"]
    domain = entity_id.split(".")[0] if "." in entity_id else ""

    # Create entity document with bilingual text support
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
        "text": text,  # Multilingual text (Hungarian + English keywords)
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


def ingest(
    entity_id: Optional[str] = None, delay_sec: int = 5, *, full: bool = False
) -> None:
    """Run the ingestion process. Only changed or new entities are embedded unless full=True. Batch delay is configurable."""
    # ...existing code...

    def get_existing_meta_hash(entity_id: str, col) -> Optional[str]:
        doc = col.get(entity_id)
        if doc:
            return doc.get("meta_hash")
        return None

    data = fetch_states(entity_id)
    states = data.get("entities", [])
    if not states:
        logger.error("No states returned from fetch_states, aborting ingestion")
        return

    areas = data.get("areas", [])
    devices = data.get("devices", [])

    logger.info(
        "Fetched states from RAG API",
        entity_count=len(states),
        area_count=len(areas),
        device_count=len(devices),
    )

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
    if full:
        for name in ["entity", "area", "device"]:
            if db.has_collection(name):
                db.collection(name).truncate()
            else:
                db.create_collection(name)
        for name in ["area_contains", "device_of"]:
            if db.has_collection(name):
                db.collection(name).truncate()
            else:
                db.create_collection(name, edge=True)
        # Use official Database.delete_graph() instead of StandardGraph.delete()
        if db.has_graph("ha_entity_graph"):
            db.delete_graph(
                "ha_entity_graph",
                drop_collections=False,  # vertex/edge collections remain
                ignore_missing=True,
            )
        db.create_graph(
            "ha_entity_graph",
            edge_definitions=[
                {
                    "edge_collection": "area_contains",
                    "from_vertex_collections": ["area"],
                    "to_vertex_collections": ["entity"],
                },
                {
                    "edge_collection": "device_of",
                    "from_vertex_collections": ["device"],
                    "to_vertex_collections": ["entity"],
                },
            ],
        )
    col = db.collection("entity")
    edge_area = db.collection("area_contains")
    edge_device = db.collection("device_of")
    area_col = db.collection("area")
    device_col = db.collection("device")

    # Upsert all areas and devices first
    area_map = {}
    alias_map = {}
    area_docs: List[dict] = []
    for area in areas:
        aid = area.get("area_id") or area.get("id")
        name = area.get("name")
        if aid and name:
            area_map[aid] = name
            aliases = area.get("aliases") or []
            alias_map[aid] = aliases
            doc = {"_key": aid, "name": name}
            if aliases:
                doc["aliases"] = aliases
            area_docs.append(doc)
    if area_docs:
        area_col.insert_many(area_docs, overwrite=True, overwrite_mode="update")

    device_map = {}
    device_docs: List[dict] = []
    for dev in devices:
        did = dev.get("id") or dev.get("device_id")
        if not did:
            continue
        device_map[did] = dev
        doc = {"_key": did}
        if dev.get("name"):
            doc["name"] = dev.get("name")
        if dev.get("model"):
            doc["model"] = dev.get("model")
        if dev.get("manufacturer"):
            doc["manufacturer"] = dev.get("manufacturer")
        device_docs.append(doc)
    if device_docs:
        device_col.insert_many(device_docs, overwrite=True, overwrite_mode="update")

    # Fill missing area information on entities using the device map
    for ent in states:
        attrs = ent.get("attributes", {})
        eid = ent.get("entity_id", "")

        # First try: inherit from device
        if not attrs.get("area_id") and attrs.get("device_id"):
            dev = device_map.get(attrs["device_id"])
            if dev:
                inferred = dev.get("area_id")
                if inferred:
                    attrs["area_id"] = inferred
                    attrs.setdefault("area", area_map.get(inferred, ""))
                    logger.info(f"Inherited area '{inferred}' from device for {eid}")

        # Second try: smart area inference from names (including device name)
        if not attrs.get("area_id"):
            # Get device name for additional context
            device_name = None
            if attrs.get("device_id"):
                dev = device_map.get(attrs["device_id"])
                if dev and dev.get("name"):
                    device_name = dev["name"]
                    attrs["device_name"] = device_name  # Add for inference

            inferred_area = _infer_area_from_names(attrs, eid, area_map)
            if inferred_area:
                attrs["area_id"] = inferred_area
                attrs.setdefault("area", area_map.get(inferred_area, inferred_area))
                logger.info(f"Inferred area '{inferred_area}' from names for {eid}")

        aid = attrs.get("area_id")
        if aid:
            attrs["area_aliases"] = alias_map.get(aid, [])

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

    # Initialize friendly name generator for ingestion-time name generation
    friendly_name_generator = FriendlyNameGenerator()
    logger.info("Initialized friendly name generator for ingestion-time enhancement")

    batch_size = 100
    unchanged_count = 0
    changed_count = 0
    new_count = 0
    failed_count = 0
    total_processed = 0
    generated_names_count = 0
    for i in range(0, len(states), batch_size):
        batch = states[i : i + batch_size]
        # Generate hybrid texts optimized for multilingual embedding with friendly name enhancement
        hybrid_texts = []
        for e in batch:
            # Count entities without friendly names for statistics
            has_friendly_name = bool(
                e.get("friendly_name", "")
                or e.get("attributes", {}).get("friendly_name", "")
            )
            if not has_friendly_name and friendly_name_generator:
                generated_names_count += 1

            hybrid_text = build_text(e, friendly_name_generator)
            hybrid_texts.append(hybrid_text)

        # Skip unchanged entities unless full ingest (hash hybrid text)
        filtered_batch = []
        filtered_hybrid_texts = []
        for ent, hybrid_text in zip(batch, hybrid_texts):
            # Hash hybrid text for change detection
            meta_hash = hashlib.sha256(hybrid_text.encode()).hexdigest()
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
            filtered_hybrid_texts.append(hybrid_text)
            total_processed += 1

        if not filtered_batch:
            continue

        try:
            # Use hybrid text (Hungarian + English) for embeddings for optimal multilingual matching
            embeddings = emb_backend.embed(filtered_hybrid_texts)
        except Exception as exc:  # pragma: no cover - network errors
            logger.warning("embedding error", error=str(exc))
            continue

        docs = []
        ents_for_docs = []
        for ent, emb, hybrid_text in zip(
            filtered_batch, embeddings, filtered_hybrid_texts
        ):
            if not emb:
                logger.warning("missing embedding", entity=ent.get("entity_id"))
                failed_count += 1
                continue
            docs.append(build_doc(ent, emb, hybrid_text))
            ents_for_docs.append(ent)

        if docs:
            col.insert_many(docs, overwrite=True, overwrite_mode="update")
            area_edges: List[dict] = []
            device_edges: List[dict] = []
            for ent, d in zip(ents_for_docs, docs):
                eid = d["_key"]
                attrs = ent.get("attributes", {})
                device_id = attrs.get("device_id")
                area_id = attrs.get("area_id") or (
                    device_map.get(device_id, {}).get("area_id") if device_id else None
                )
                edge_count = 0
                if area_id:
                    key_raw = f"area_contains:area/{area_id}->entity/{eid}"
                    area_edges.append(
                        {
                            "_key": hashlib.sha1(key_raw.encode()).hexdigest(),
                            "_from": f"area/{area_id}",
                            "_to": f"entity/{eid}",
                            # label field removed, collection name is enough
                            "created_by": "ingest",
                            "ts_created": datetime.utcnow().isoformat(),
                        }
                    )
                    edge_count += 1
                if device_id:
                    key_raw = f"device_of:device/{device_id}->entity/{eid}"
                    device_edges.append(
                        {
                            "_key": hashlib.sha1(key_raw.encode()).hexdigest(),
                            "_from": f"device/{device_id}",
                            "_to": f"entity/{eid}",
                            # label field removed, collection name is enough
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
                    hybrid_text=(
                        d["text"][:50] + "..." if len(d["text"]) > 50 else d["text"]
                    ),
                    has_area=bool(d.get("area")),
                    has_device=bool(d.get("device_id")),
                )
            if area_edges:
                edge_area.insert_many(
                    area_edges, overwrite=True, overwrite_mode="ignore"
                )
            if device_edges:
                edge_device.insert_many(
                    device_edges, overwrite=True, overwrite_mode="ignore"
                )

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
        generated_friendly_names=generated_names_count,
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
        ingest(None, delay_sec=args.delay, full=True)
    else:
        ingest(args.entity, delay_sec=args.delay)


if __name__ == "__main__":
    cli()
