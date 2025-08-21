#!/usr/bin/env python3
"""Test vector search similarity scores directly."""

import os
from arango import ArangoClient
from ha_rag_bridge.db import BridgeDB
from scripts.embedding_backends import get_backend


def test_direct_vector_search():
    """Test vector search with temperature query."""

    # Generate query embedding
    backend = get_backend("local")
    query = "hány fok van a nappaliban temperature"
    query_vector = backend.embed([query])[0]

    print(f"🔍 Testing vector search for: {query}")
    print(f"Query vector dimensions: {len(query_vector)}")
    print(f"Query vector sample: {query_vector[:3]}")
    print()

    # Connect to database
    client = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db = client.db(
        os.getenv("ARANGO_DB", "homeassistant"),
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )
    db.__class__ = BridgeDB

    # Test the exact same AQL query used in the main workflow
    aql_query = """
    LET knn = (
        FOR e IN entity 
        FILTER LENGTH(e.embedding) > 0 
        LET score = COSINE_SIMILARITY(e.embedding, @qv) 
        SORT score DESC 
        LIMIT @k 
        RETURN e
    ) 
    FOR e IN knn 
    LIMIT @k 
    RETURN {
        entity_id: e.entity_id,
        area_name: e.area_name,
        device_class: e.device_class,
        embedding_dim: LENGTH(e.embedding),
        score: COSINE_SIMILARITY(e.embedding, @qv)
    }
    """

    try:
        print("🚀 Running exact workflow AQL query...")
        results = db.aql.execute(
            aql_query, bind_vars={"qv": query_vector, "k": 10}
        ).batch()

        print(f"📊 Found {len(results)} results:")
        print("-" * 80)

        for i, result in enumerate(results, 1):
            entity_id = result["entity_id"]
            score = result["score"]
            area = result.get("area_name", "no_area")
            device_class = result.get("device_class", "unknown")
            embedding_dim = result["embedding_dim"]

            # Highlight temperature sensors
            is_temp = "temperature" in entity_id.lower()
            marker = "🌡️" if is_temp else "📍"

            print(f"{i:2d}. {marker} {entity_id}")
            print(
                f"    Score: {score:.6f} | Area: {area} | Class: {device_class} | Dims: {embedding_dim}"
            )

        # Check specifically for nappali temperature sensors
        print("\n🏠 Filtering for nappali temperature sensors:")
        print("-" * 50)

        nappali_temps = [
            r
            for r in results
            if r.get("area_name") == "nappali"
            and "temperature" in r["entity_id"].lower()
        ]

        if nappali_temps:
            for temp in nappali_temps:
                print(f"✅ {temp['entity_id']}: score={temp['score']:.6f}")
        else:
            # Try broader search
            print("❌ No nappali temperature sensors found in top 10")
            print("📝 Trying broader search...")

            broader_query = """
            FOR e IN entity 
            FILTER LENGTH(e.embedding) > 0 AND e.area_name == @area
            LET score = COSINE_SIMILARITY(e.embedding, @qv) 
            SORT score DESC 
            LIMIT 5 
            RETURN {
                entity_id: e.entity_id,
                score: score,
                device_class: e.device_class
            }
            """

            broader_results = db.aql.execute(
                broader_query, bind_vars={"qv": query_vector, "area": "nappali"}
            ).batch()

            print("🔎 Nappali entities (top 5 by similarity):")
            for result in broader_results:
                print(
                    f"  {result['entity_id']}: {result['score']:.6f} ({result.get('device_class', 'unknown')})"
                )

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_direct_vector_search()
