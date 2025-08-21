#!/usr/bin/env python3
"""Test script to demonstrate the new embedding text format."""


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


# Example entities of different types
test_entities = [
    # Light entity
    {
        "entity_id": "light.living_room_lamp",
        "state": "on",
        "attributes": {
            "friendly_name": "Living Room Main Light",
            "device_id": "device_12345",
            "area_id": "living_room",
            "area": "Living Room",
            "device_class": "light",
            "icon": "mdi:ceiling-light",
        },
    },
    # Temperature sensor
    {
        "entity_id": "sensor.bedroom_temperature",
        "state": "22.5",
        "attributes": {
            "friendly_name": "Bedroom Temperature",
            "device_id": "device_67890",
            "area_id": "bedroom",
            "area": "Bedroom",
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "icon": "mdi:thermometer",
        },
    },
    # Switch with minimal information
    {
        "entity_id": "switch.garden_irrigation",
        "state": "off",
        "attributes": {
            "friendly_name": "Garden Irrigation",
            "device_id": "device_abcde",
            "entity_category": "config",
        },
    },
    # Entity with missing area information
    {
        "entity_id": "binary_sensor.front_door",
        "state": "off",
        "attributes": {
            "friendly_name": "Front Door Sensor",
            "device_id": "device_fghij",
            "device_class": "door",
        },
    },
    # Entity with multilingual support test
    {
        "entity_id": "climate.living_room_ac",
        "state": "heat",
        "attributes": {
            "friendly_name": "Living Room Air Conditioner",
            "device_id": "device_klmno",
            "area_id": "living_room",
            "area": "Living Room",
            "device_class": "climate",
        },
    },
]


def main():
    print("=== EMBEDDING TEXT FORMAT EXAMPLES ===")
    print()

    for entity in test_entities:
        print(f"--- {entity['entity_id']} ---")
        text = build_text(entity)
        print("\nGenerated embedding text:")
        print(text)
        print("\n" + "=" * 50 + "\n")


if __name__ == "__main__":
    main()
