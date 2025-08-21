#!/usr/bin/env python3
"""Test script to compare old and new embedding text formats."""


def old_build_text(entity: dict) -> str:
    """The original build_text function."""
    attrs = entity.get("attributes", {})
    text = []
    if "friendly_name" in attrs:
        text.append(attrs["friendly_name"])
    if "entity_id" in entity:
        text.append(entity["entity_id"])
    if "area_id" in attrs:
        text.append(attrs["area_id"])
    if "area" in attrs:
        text.append(attrs["area"])
    for attr in (
        "device_class",
        "unit_of_measurement",
    ):
        if attr in attrs:
            text.append(attrs[attr])
    if "synonyms" in attrs and attrs["synonyms"]:
        if isinstance(attrs["synonyms"], list):
            text.append(" ".join(attrs["synonyms"]))
        else:
            text.append(attrs["synonyms"])
    # extract words from entity_id
    if "entity_id" in entity and "." in entity["entity_id"]:
        name_part = entity["entity_id"].split(".", 1)[1]
        name_parts = name_part.replace("_", " ").split()
        text.extend(name_parts)
    return " ".join(text)


def new_build_text(entity: dict) -> str:
    """The new build_text function."""
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
]


def main():
    print("=== EMBEDDING TEXT FORMAT COMPARISON ===")
    print()

    for entity in test_entities:
        print(f"--- {entity['entity_id']} ---")

        old_text = old_build_text(entity)
        new_text = new_build_text(entity)

        print("\nOld Format:")
        print(old_text)
        print("\nNew Format:")
        print(new_text)

        # Calculate size difference and additional information
        old_size = len(old_text)
        new_size = len(new_text)
        size_diff = new_size - old_size
        percent_change = (size_diff / old_size) * 100 if old_size > 0 else 0

        print("\nSize Comparison:")
        print(f"Old: {old_size} characters")
        print(f"New: {new_size} characters")
        print(f"Difference: {size_diff:+d} characters ({percent_change:+.1f}%)")

        # Analyze the additional information in the new format
        old_tokens = set(old_text.lower().split())
        new_sections = new_text.split(". ")

        print("\nAdditional Context in New Format:")
        for section in new_sections:
            if section and not any(token in section.lower() for token in old_tokens):
                print(f"- {section}")

        print("\n" + "=" * 50 + "\n")


if __name__ == "__main__":
    main()
