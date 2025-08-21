#!/usr/bin/env python3
from scripts.ingest import build_text

# Plda entitások
entities = [
    {
        "entity_id": "sensor.kert_aqara_szenzor_humidity",
        "attributes": {
            "friendly_name": "Humidity",
            "device_id": "0503d783f1fbceea1aead48ab6a53d4f",
            "area_id": "kert",
            "area": "Előkert",
            "device_class": "humidity",
            "unit_of_measurement": "%",
        },
    },
    {
        "entity_id": "light.etkezo_ablak_falikar",
        "attributes": {
            "friendly_name": "Étkező Ablak Falikar",
            "device_id": "cc64d1b1aadb1056cfb8f167bb948583",
            "area_id": "etkezo",
            "area": "Étkező",
        },
    },
    {
        "entity_id": "sensor.alfogyasztasmer_1_channel_2_power",
        "attributes": {
            "friendly_name": "Power",
            "device_id": "4fa1ab52aad77d50c905e62991ccf812",
            "area_id": "furdoszoba",
            "area": "Fürdőszoba",
            "unit_of_measurement": "W",
        },
    },
    {
        "entity_id": "sensor.lumi_lumi_weather_humidity_kert",
        "attributes": {
            "friendly_name": "Humidity",
            "device_id": "fb2a52c29c0a93d99e8b37f1833ae02a",
            "area_id": "kert",
            "area": "Előkert",
            "device_class": "humidity",
            "unit_of_measurement": "%",
        },
    },
]

print("=== Példa embedding szövegek ===")
for entity in entities:
    print("\nEntity:", entity["entity_id"])
    print("-" * 80)
    text = build_text(entity)
    print(text)
    print("=" * 80)
