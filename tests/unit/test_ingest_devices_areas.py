import os
from unittest.mock import MagicMock

import scripts.ingestion.ingest as ingest


def test_ingest_devices_areas(monkeypatch):
    os.environ.update(
        {
            "HA_URL": "http://ha",
            "HA_TOKEN": "token",
            "OPENAI_API_KEY": "sk",
            "EMBEDDING_BACKEND": "openai",
            "ARANGO_URL": "http://db",
            "ARANGO_USER": "root",
            "ARANGO_PASS": "pass",
        }
    )

    payload = {
        "areas": [{"id": "kitchen", "name": "Kitchen"}],
        "devices": [
            {
                "id": "dev1",
                "name": "Fridge",
                "model": "F1",
                "manufacturer": "Acme",
                "area_id": "kitchen",
            }
        ],
        "entities": [
            {
                "entity_id": "sensor.temp1",
                "original_name": "Temp1",
                "device_id": "dev1",
                "exposed": True,
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status.return_value = None
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    mock_client.__enter__.return_value = mock_client
    monkeypatch.setattr(ingest.httpx, "Client", MagicMock(return_value=mock_client))

    mock_backend = MagicMock()
    mock_backend.embed.return_value = [[0.0] * 1536]
    monkeypatch.setattr(ingest, "OpenAIBackend", MagicMock(return_value=mock_backend))

    mock_entity_col = MagicMock()
    mock_area_edge_col = MagicMock()
    mock_device_edge_col = MagicMock()
    mock_area_col = MagicMock()
    mock_device_col = MagicMock()

    def get_collection(name):
        return {
            "entity": mock_entity_col,
            "area_contains": mock_area_edge_col,
            "device_of": mock_device_edge_col,
            "area": mock_area_col,
            "device": mock_device_col,
        }[name]

    mock_db = MagicMock()
    mock_db.collection.side_effect = get_collection
    mock_arango = MagicMock()
    mock_arango.db.return_value = mock_db
    monkeypatch.setattr(ingest, "ArangoClient", MagicMock(return_value=mock_arango))

    ingest.ingest()

    # all areas and devices inserted via bulk call
    mock_area_col.insert_many.assert_called_once()
    assert len(mock_area_col.insert_many.call_args[0][0]) == len(payload["areas"])

    mock_device_col.insert_many.assert_called_once()
    device_docs = mock_device_col.insert_many.call_args[0][0]
    assert len(device_docs) == len(payload["devices"])
    assert device_docs[0]["name"] == "Fridge"
    assert device_docs[0]["model"] == "F1"
    assert device_docs[0]["manufacturer"] == "Acme"

    area_edges = mock_area_edge_col.insert_many.call_args[0][0]
    assert any(
        e["label"] == "area_contains"
        and e["_from"] == "area/kitchen"
        and e["_to"] == "entity/sensor.temp1"
        for e in area_edges
    )
