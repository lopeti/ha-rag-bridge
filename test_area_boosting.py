#!/usr/bin/env python3
"""Test area boosting logic directly."""

import asyncio
from app.services.entity_reranker import entity_reranker

async def test_area_boosting():
    """Test area boosting with a simple garden temperature query."""
    
    # Mock entities - garden sensor should get boosted
    test_entities = [
        {
            "entity_id": "sensor.mosokonyha_mi_szenzor_temperature",
            "area": "mosokonyha",
            "domain": "sensor", 
            "_score": 0.8,  # High base score from memory
        },
        {
            "entity_id": "sensor.kert_aqara_szenzor_temperature", 
            "area": "kert",
            "domain": "sensor",
            "_score": 0.3,  # Low base score
        },
        {
            "entity_id": "sensor.nappali_temperature",
            "area": "nappali", 
            "domain": "sensor",
            "_score": 0.5,
        }
    ]
    
    query = "Hány fok van a kertben?"
    print(f"🧪 Testing area boosting for: {query}")
    print()
    
    # Mock conversation history  
    conversation_history = []
    
    # Call the entity reranker
    try:
        ranked_entities = entity_reranker.rank_entities(
            entities=test_entities,
            query=query,
            conversation_history=conversation_history,
            conversation_id="test_session",
            k=10
        )
        
        print("📊 Results after entity reranking:")
        print("-" * 50)
        
        for i, es in enumerate(ranked_entities, 1):
            entity_id = es.entity.get("entity_id")
            area = es.entity.get("area", "no_area")
            base_score = es.base_score
            context_boost = es.context_boost
            final_score = es.final_score
            
            boost_indicator = "🚀" if context_boost > 0 else "📍"
            
            print(f"{i}. {boost_indicator} {entity_id}")
            print(f"    Area: {area}")
            print(f"    Base: {base_score:.3f} | Boost: {context_boost:+.3f} | Final: {final_score:.3f}")
            print(f"    Factors: {es.ranking_factors}")
            print()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_area_boosting())