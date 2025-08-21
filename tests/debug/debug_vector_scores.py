#!/usr/bin/env python3
"""Debug why vector scores are 0.000 in workflow but 0.45+ in direct test."""

import os
import asyncio
from arango import ArangoClient
from ha_rag_bridge.db import BridgeDB
from scripts.embedding_backends import get_backend
from app.main import query_arango


async def debug_vector_scores():
    """Compare direct AQL vs workflow query_arango function."""

    # Generate query embedding
    backend = get_backend("local")
    query_text = "hány fok van a nappaliban temperature"
    query_vector = backend.embed([query_text])[0]

    print(f"🔍 Debugging vector scores for: {query_text}")
    print(f"Query vector dimensions: {len(query_vector)}")
    print()

    # Connect to database
    client = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db = client.db(
        os.getenv("ARANGO_DB", "homeassistant"),
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )
    db.__class__ = BridgeDB

    # Test 1: Direct AQL query (like our successful test)
    print("🧪 Test 1: Direct AQL query")
    print("-" * 40)

    direct_aql = """
    FOR e IN entity 
    FILTER LENGTH(e.embedding) > 0 
    LET score = COSINE_SIMILARITY(e.embedding, @qv) 
    SORT score DESC 
    LIMIT 5 
    RETURN {
        entity_id: e.entity_id,
        area: e.area,
        score: score
    }
    """

    direct_results = db.aql.execute(direct_aql, bind_vars={"qv": query_vector}).batch()

    for result in direct_results:
        entity_id = result["entity_id"]
        area = result.get("area", "None")
        score = result["score"]

        is_temp = "temperature" in entity_id.lower()
        marker = "🌡️" if is_temp else "📍"

        area_str = str(area) if area is not None else "None"
        print(f"{marker} {entity_id[:35]:35} | {area_str:10} | {score:.6f}")

    # Test 2: Workflow's query_arango function
    print("\n🔬 Test 2: Workflow query_arango function")
    print("-" * 50)

    try:
        workflow_results = query_arango(db, query_vector, query_text, k=5)

        print(f"Found {len(workflow_results)} entities:")
        for i, entity in enumerate(workflow_results, 1):
            entity_id = entity.get("entity_id", "unknown")
            area = entity.get("area", "None")

            # Check for score fields
            score_fields = {}
            for field in ["_score", "score", "similarity"]:
                if field in entity:
                    score_fields[field] = entity[field]

            is_temp = "temperature" in entity_id.lower()
            marker = "🌡️" if is_temp else "📍"

            area_str = str(area) if area is not None else "None"
            print(f"{i}. {marker} {entity_id[:35]:35} | {area_str:10}")
            if score_fields:
                for field, value in score_fields.items():
                    print(f"       {field}: {value:.6f}")
            else:
                print("       ❌ No score fields found")
                # Show all fields for debugging
                keys = [
                    k
                    for k in entity.keys()
                    if not k.startswith("text") and not k.startswith("embedding")
                ]
                print(f"       Available fields: {keys[:5]}...")

    except Exception as e:
        print(f"❌ workflow query_arango error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_vector_scores())
