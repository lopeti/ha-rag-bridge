#!/usr/bin/env python3
"""Test script to demonstrate the new embedding text format."""

from scripts.ingestion.ingest import build_text

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
        print("Entity data:", entity)
        text = build_text(entity)
        print("\nGenerated embedding text:")
        print(text)
        print("\n" + "=" * 50 + "\n")


if __name__ == "__main__":
    main()
