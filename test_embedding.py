#!/usr/bin/env python3


def build_text(entity: dict) -> str:
    """Return the concatenated text used for embedding."""
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
        translations.extend(["hőmrséklet", "hőfok"])
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


# Néhány példa entits a kapott JSON-ból
entity1 = {
    "entity_id": "sensor.kert_aqara_szenzor_humidity",
    "attributes": {
        "friendly_name": "Humidity",
        "device_id": "0503d783f1fbceea1aead48ab6a53d4f",
        "area_id": "kert",
        "area": "Előkert",
        "device_class": "humidity",
        "unit_of_measurement": "%",
    },
}

entity2 = {
    "entity_id": "light.etkezo_ablak_falikar",
    "attributes": {
        "friendly_name": "Étkező Ablak Falikar",
        "device_id": "cc64d1b1aadb1056cfb8f167bb948583",
        "area_id": "etkezo",
        "area": "Étkező",
    },
}

entity3 = {
    "entity_id": "sensor.alfogyasztasmer_1_channel_2_power",
    "attributes": {
        "friendly_name": "Power",
        "device_id": "4fa1ab52aad77d50c905e62991ccf812",
        "area_id": "furdoszoba",
        "area": "Fürdőszoba",
        "unit_of_measurement": "W",
    },
}

entity4 = {
    "entity_id": "sensor.lumi_lumi_weather_temperature_kert",
    "attributes": {
        "friendly_name": "Temperature",
        "device_id": "fb2a52c29c0a93d99e8b37f1833ae02a",
        "area_id": "kert",
        "area": "Előkert",
        "device_class": "temperature",
        "unit_of_measurement": "°C",
    },
}

print("=== PÉLDA 1 ===")
print(build_text(entity1))
print("\n=== PÉLDA 2 ===")
print(build_text(entity2))
print("\n=== PÉLDA 3 ===")
print(build_text(entity3))
print("\n=== PÉLDA 4 ===")
print(build_text(entity4))
