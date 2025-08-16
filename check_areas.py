#!/usr/bin/env python3
"""Check area assignments in database."""

import os
from arango import ArangoClient
from ha_rag_bridge.db import BridgeDB


def check_areas():
    """Check what areas exist in the database."""

    client = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db = client.db(
        os.getenv("ARANGO_DB", "homeassistant"),
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )
    db.__class__ = BridgeDB

    # Check unique areas using the correct field
    query = """
    FOR e IN entity 
    FILTER e.area != null
    COLLECT area = e.area WITH COUNT INTO count
    SORT count DESC
    RETURN {area: area, count: count}
    """

    results = db.aql.execute(query).batch()
    print(f"📍 Areas (using correct field): {len(results)}")
    print("-" * 30)

    for result in results:
        area = result["area"]
        count = result["count"]
        print(f"{area:15} | {count:3} entities")

    # Check temperature sensors specifically
    print("\n🌡️ Temperature sensors by area:")
    temp_query = """
    FOR e IN entity 
    FILTER CONTAINS(LOWER(e.entity_id), "temperature")
    RETURN {
        entity_id: e.entity_id,
        area: e.area,
        area_id: e.area_id,
        friendly_name: e.friendly_name
    }
    """

    temp_results = db.aql.execute(temp_query).batch()
    nappali_temps = []

    for result in temp_results:
        entity_id = result["entity_id"]
        area = result.get("area", "None")
        result.get("area_id", "None")
        friendly_name = result.get("friendly_name", "N/A")

        if area == "nappali":
            nappali_temps.append(entity_id)

        print(f"{entity_id[:35]:35} | {area:10} | {friendly_name[:20]}")

    print(f"\n✅ Temperature sensors in nappali: {len(nappali_temps)}")
    for temp in nappali_temps:
        print(f"  - {temp}")


if __name__ == "__main__":
    check_areas()
