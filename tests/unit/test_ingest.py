import os
from unittest.mock import MagicMock

import scripts.ingest as ingest


def test_ingest_upserts(monkeypatch):
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
        "devices": [],
        "entities": [
            {
                "entity_id": "sensor.test",
                "original_name": "Test",
                "device_id": None,
                "area_id": "kitchen",
                "exposed": True,
                "domain": "sensor",
                "friendly_name": "Test",
                "synonyms": ["foo"],
            }
        ],
    }

    payload["entities"][0]["area"] = "Kitchen"

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

    mock_entity_col.insert_many.assert_called_once()
    args, kwargs = mock_entity_col.insert_many.call_args
    assert kwargs.get("overwrite") is True
    docs = args[0]
    doc = docs[0]
    assert doc["embedding"]

    mock_area_edge_col.insert_many.assert_called()
    mock_device_edge_col.insert_many.assert_not_called()
    area_edges = mock_area_edge_col.insert_many.call_args[0][0]
    assert len(area_edges) >= 1
    assert all(e["label"] == "area_contains" for e in area_edges)
    assert all(e["created_by"] == "ingest" for e in area_edges)
    assert doc["text"].startswith("Test")
    import hashlib

    assert doc["meta_hash"] == hashlib.sha256(doc["text"].encode()).hexdigest()
