import os
from unittest.mock import MagicMock

import scripts.ingest as ingest


def test_ingest_upserts(monkeypatch):
    os.environ.update({
        "HA_URL": "http://ha",
        "HA_TOKEN": "token",
        "OPENAI_API_KEY": "sk",
        "ARANGO_URL": "http://db",
        "ARANGO_USER": "root",
        "ARANGO_PASS": "pass",
    })

    states = [
        {
            "entity_id": "sensor.test",
            "attributes": {"friendly_name": "Test", "area": "Kitchen", "synonyms": ["foo"]},
        }
    ]

    mock_resp = MagicMock()
    mock_resp.json.return_value = states
    mock_resp.raise_for_status.return_value = None
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    mock_client.__enter__.return_value = mock_client
    monkeypatch.setattr(ingest.httpx, "Client", MagicMock(return_value=mock_client))

    embed_resp = MagicMock()
    embed_resp.data = [MagicMock(embedding=[0.0] * 1536)]
    mock_oai = MagicMock()
    mock_oai.embeddings.create.return_value = embed_resp
    monkeypatch.setattr(ingest.openai, "OpenAI", MagicMock(return_value=mock_oai))

    mock_collection = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value = mock_collection
    mock_arango = MagicMock()
    mock_arango.db.return_value = mock_db
    monkeypatch.setattr(ingest, "ArangoClient", MagicMock(return_value=mock_arango))

    ingest.ingest()

    mock_collection.insert.assert_called_once()
