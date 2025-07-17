import os
import argparse
import logging
from typing import List, Optional

import httpx
import openai
from arango import ArangoClient


logger = logging.getLogger(__name__)


def fetch_states(entity_id: Optional[str] = None) -> List[dict]:
    base_url = os.environ["HA_URL"]
    token = os.environ["HA_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=base_url, headers=headers, timeout=10.0) as client:
        if entity_id:
            resp = client.get(f"/api/states/{entity_id}")
            resp.raise_for_status()
            return [resp.json()]
        resp = client.get("/api/states")
        resp.raise_for_status()
        return resp.json()


def build_text(entity: dict) -> str:
    attrs = entity.get("attributes", {})
    friendly_name = attrs.get("friendly_name", "")
    area = attrs.get("area", "")
    domain = entity.get("entity_id", "").split(".")[0]
    synonyms = " ".join(attrs.get("synonyms", []))
    return f"{friendly_name}. {area}. {domain}. {synonyms}".strip()


def embed_text(text: str, client: openai.OpenAI) -> Optional[List[float]]:
    try:
        resp = client.embeddings.create(model="text-embedding-3-large", input=text)
        return resp.data[0].embedding  # type: ignore[index]
    except Exception as exc:  # pragma: no cover - network errors
        logger.error("Embedding failed: %s", exc)
        return None


def upsert_entity(entity: dict, embedding: List[float], collection):
    attrs = entity.get("attributes", {})
    doc = {
        "_key": entity["entity_id"],
        "entity_id": entity["entity_id"],
        "friendly_name": attrs.get("friendly_name"),
        "area": attrs.get("area"),
        "domain": entity["entity_id"].split(".")[0],
        "synonyms": attrs.get("synonyms"),
        "text": build_text(entity),
        "embedding": embedding,
    }
    collection.insert(doc, overwrite=True)


def ingest(entity_id: Optional[str] = None) -> None:
    logging.basicConfig(level=logging.INFO)
    states = fetch_states(entity_id)
    oai_client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db_name = os.getenv("ARANGO_DB", "_system")
    db = arango.db(db_name, username=os.environ["ARANGO_USER"], password=os.environ["ARANGO_PASS"])
    col = db.collection("entity")

    for entity in states:
        text = build_text(entity)
        embedding = embed_text(text, oai_client)
        if embedding is None:
            logger.warning("Skipping entity %s", entity.get("entity_id"))
            continue
        upsert_entity(entity, embedding, col)
        logger.info("Upserted %s", entity.get("entity_id"))


def cli() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--full", action="store_true", help="Full ingest of all states")
    group.add_argument("--entity", help="Single entity id")
    args = parser.parse_args()
    ingest(None if args.full else args.entity)


if __name__ == "__main__":
    cli()
