import os
from unittest.mock import MagicMock

import scripts.ingest as ingest


def test_ingest_upserts(monkeypatch):
    os.environ.update({
        "HA_URL": "http://ha",
        "HA_TOKEN": "token",
        "OPENAI_API_KEY": "sk",
        "EMBEDDING_BACKEND": "openai",
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

    mock_backend = MagicMock()
    mock_backend.embed.return_value = [[0.0] * 1536]
    monkeypatch.setattr(ingest, "OpenAIBackend", MagicMock(return_value=mock_backend))

    mock_entity_col = MagicMock()
    mock_edge_col = MagicMock()
    mock_area_col = MagicMock()
    mock_device_col = MagicMock()

    def get_collection(name):
        return {
            "entity": mock_entity_col,
            "edge": mock_edge_col,
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
    expected_text = (
        "Test. Kitchen. sensor. foo. living room nappali temperature h\u0151m\u00e9rs\u00e9klet"
    )

    mock_edge_col.insert_many.assert_called()
    edge_docs = mock_edge_col.insert_many.call_args[0][0]
    assert len(edge_docs) >= 1
    assert any(e["label"] == "area_contains" for e in edge_docs)
    assert all(e["created_by"] == "ingest" for e in edge_docs)
    assert doc["text"] == expected_text
    import hashlib

    assert (
        doc["meta_hash"]
        == hashlib.sha256(expected_text.encode()).hexdigest()
    )
