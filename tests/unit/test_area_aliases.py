import os
from unittest.mock import MagicMock

import scripts.ingestion.ingest as ingest


def test_area_aliases(monkeypatch):
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
        "areas": [{"id": "living", "name": "Living", "aliases": ["living room"]}],
        "devices": [],
        "entities": [
            {
                "entity_id": "light.test",
                "original_name": "Test Light",
                "device_id": None,
                "area_id": "living",
                "exposed": True,
                "domain": "light",
                "friendly_name": "Test",
            }
        ],
    }
    payload["entities"][0]["area"] = "Living"

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
    mock_area_edge = MagicMock()
    mock_device_edge = MagicMock()
    mock_area_col = MagicMock()
    mock_device_col = MagicMock()

    def get_collection(name):
        return {
            "entity": mock_entity_col,
            "area_contains": mock_area_edge,
            "device_of": mock_device_edge,
            "area": mock_area_col,
            "device": mock_device_col,
        }[name]

    mock_db = MagicMock()
    mock_db.collection.side_effect = get_collection
    mock_arango = MagicMock()
    mock_arango.db.return_value = mock_db
    monkeypatch.setattr(ingest, "ArangoClient", MagicMock(return_value=mock_arango))

    ingest.ingest()

    area_doc = mock_area_col.insert_many.call_args[0][0][0]
    assert area_doc["aliases"] == ["living room"]

    entity_doc = mock_entity_col.insert_many.call_args[0][0][0]
    assert "living room" in entity_doc["text"]
