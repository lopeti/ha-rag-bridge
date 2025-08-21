#!/usr/bin/env python3
"""Debug script to test conversation memory service directly."""

import asyncio
from app.services.conversation_memory import ConversationMemoryService


async def test_memory_service():
    """Test conversation memory service directly."""

    print("🔍 Testing ConversationMemoryService directly")
    print("=" * 50)

    memory_service = ConversationMemoryService()
    session_id = "debug_test"

    # Clean up any existing memory
    await memory_service._cleanup_expired_memory(session_id)

    # Test 1: Store some entities
    print("\n1. Storing entities in memory...")
    test_entities = [
        {
            "entity_id": "light.nappali_lamp",
            "rerank_score": 0.85,
            "area_name": "nappali",
            "domain": "light",
        },
        {
            "entity_id": "sensor.nappali_temperature",
            "rerank_score": 0.75,
            "area_name": "nappali",
            "domain": "sensor",
        },
    ]

    success = await memory_service.store_conversation_memory(
        conversation_id=session_id,
        entities=test_entities,
        areas_mentioned={"nappali"},
        domains_mentioned={"light", "sensor"},
        query_context="Test query about living room",
    )

    print(f"   Storage success: {success}")

    # Test 2: Check if memory exists
    print("\n2. Checking stored memory...")
    memory = await memory_service.get_conversation_memory(session_id)

    if memory:
        print(f"   Found memory: {len(memory.entities)} entities")
        print(f"   Areas: {list(memory.areas_mentioned)}")
        print(f"   Domains: {list(memory.domains_mentioned)}")
        for entity in memory.entities:
            print(f"     - {entity.entity_id}: boost={entity.boost_weight:.2f}")
    else:
        print("   ❌ No memory found")

    # Test 3: Query for relevant entities
    print("\n3. Testing relevance queries...")
    test_queries = [
        "és a hőmérséklet?",
        "kapcsold fel a lámpákat",
        "mi van a nappaliban?",
        "hány fok van?",
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        relevant = await memory_service.get_relevant_entities(
            conversation_id=session_id, current_query=query, max_entities=5
        )

        print(f"   Relevant entities: {len(relevant)}")
        for entity in relevant:
            entity_id = entity["entity_id"][:25]
            mem_rel = entity.get("memory_relevance", 0)
            boost = entity.get("boost_weight", 1.0)
            print(f"     - {entity_id}: mem_rel={mem_rel:.2f}, boost={boost:.2f}")

    # Test 4: Check stats
    print("\n4. Memory stats:")
    stats = await memory_service.get_conversation_stats(session_id)
    if stats:
        print(f"   Entities: {stats['entity_count']}")
        print(f"   TTL remaining: {stats['minutes_remaining']:.1f} minutes")
        print(f"   Average boost: {stats['average_boost_weight']:.2f}")
    else:
        print("   ❌ No stats available")


if __name__ == "__main__":
    asyncio.run(test_memory_service())
