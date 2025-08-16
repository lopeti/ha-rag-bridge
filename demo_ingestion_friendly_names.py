#!/usr/bin/env python3
"""Demonstration of ingestion-time friendly name generation.

Shows how the enhanced ingestion process automatically generates
contextual Hungarian friendly names for entities that lack them,
improving embedding quality without modifying HA configuration.
"""

from scripts.friendly_name_generator import FriendlyNameGenerator


def simulate_build_text_enhanced(entity, generator=None):
    """Simplified version of build_text with friendly name enhancement."""
    attrs = entity.get("attributes", {})
    entity_id = entity.get("entity_id", "")
    friendly_name = entity.get("friendly_name", "") or attrs.get("friendly_name", "")

    # Generate friendly name if missing and generator provided
    if not friendly_name and generator and entity_id:
        suggestion = generator.generate_suggestion(entity)
        if suggestion.confidence >= 0.7:
            friendly_name = suggestion.suggested_name
            print(
                f"   🧠 Generated: '{friendly_name}' (confidence: {suggestion.confidence:.2f})"
            )

    area_name = attrs.get("area") or ""
    domain = entity_id.split(".")[0] if entity_id else ""

    text_parts = []
    if friendly_name:
        main_desc = f"{friendly_name} ({domain})" if domain else friendly_name
        text_parts.append(main_desc)
    else:
        # Fallback to entity name parsing
        if "." in entity_id:
            name_part = entity_id.split(".", 1)[1]
            clean_name = name_part.replace("_", " ").title()
            text_parts.append(f"{clean_name} ({domain})" if domain else clean_name)

    if area_name:
        text_parts.append(f"Located in {area_name}")

    unit = attrs.get("unit_of_measurement", "")
    if unit:
        text_parts.append(f"Measures in {unit}")

    return ". ".join(text_parts)


def main():
    print("🏠 INGESTION-TIME FRIENDLY NAME GENERATION DEMO")
    print("=" * 60)
    print()

    # Initialize the generator
    generator = FriendlyNameGenerator()

    # Test entities that typically lack friendly names
    test_entities = [
        {"entity_id": "light.etkezo_ablak_falikar", "attributes": {"area": "étkező"}},
        {
            "entity_id": "sensor.weatherapi_otthon_pm_2_5",
            "attributes": {"unit_of_measurement": "μg/m³"},
        },
        {
            "entity_id": "binary_sensor.konyha_mozgaserzekelo_occupancy",
            "attributes": {"area": "konyha", "device_class": "occupancy"},
        },
        {
            "entity_id": "sensor.energy_production_today",
            "attributes": {"unit_of_measurement": "kWh", "device_class": "energy"},
        },
        {"entity_id": "cover.bubi_redony", "attributes": {"area": "Bubi szoba"}},
    ]

    total_generated = 0

    for i, entity in enumerate(test_entities, 1):
        entity_id = entity["entity_id"]
        print(f"{i}. Entity: {entity_id}")

        # Show current state (without friendly name)
        current_text = simulate_build_text_enhanced(entity)
        print(f'   ❌ Current embedding text: "{current_text}"')

        # Show enhanced state (with generated friendly name)
        enhanced_text = simulate_build_text_enhanced(entity, generator)
        print(f'   ✅ Enhanced embedding text: "{enhanced_text}"')

        # Check if a name was generated
        suggestion = generator.generate_suggestion(entity)
        if suggestion.confidence >= 0.7:
            total_generated += 1

        print()

    print("📊 STATISTICS:")
    print(f"   • Total entities processed: {len(test_entities)}")
    print(f"   • Friendly names generated: {total_generated}")
    print(f"   • Enhancement rate: {(total_generated/len(test_entities)*100):.0f}%")
    print()

    print("🎯 KEY BENEFITS:")
    print("   ✓ HA entity registry remains untouched")
    print("   ✓ Better Hungarian semantic search quality")
    print("   ✓ Automatic contextual name generation")
    print("   ✓ No user intervention required")
    print("   ✓ Improved embedding text for vector search")
    print()

    print("🚀 NEXT STEPS:")
    print("   Run ingestion to see automatic friendly name enhancement:")
    print("   $ poetry run python scripts/ingest.py --full")
    print("   Look for 'generated_friendly_names' in the ingestion summary!")


if __name__ == "__main__":
    main()
