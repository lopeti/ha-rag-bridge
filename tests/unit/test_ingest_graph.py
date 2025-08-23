import os
from unittest.mock import MagicMock

import scripts.ingestion.ingest as ingest


def test_ingest_full_creates_graph(monkeypatch):
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
        "areas": [],
        "devices": [],
        "entities": [
            {
                "entity_id": "sensor.t",
                "original_name": "T",
                "device_id": None,
                "area_id": None,
                "exposed": True,
                "domain": "sensor",
                "friendly_name": "T",
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
    mock_area_col = MagicMock()
    mock_device_col = MagicMock()
    mock_area_edge = MagicMock()
    mock_device_edge = MagicMock()

    def get_collection(name):
        return {
            "entity": mock_entity_col,
            "area": mock_area_col,
            "device": mock_device_col,
            "area_contains": mock_area_edge,
            "device_of": mock_device_edge,
        }[name]

    mock_graph = MagicMock()

    mock_db = MagicMock()
    mock_db.collection.side_effect = get_collection
    mock_db.has_collection.return_value = True
    mock_db.has_graph.return_value = False
    mock_db.graph.return_value = mock_graph
    mock_arango = MagicMock()
    mock_arango.db.return_value = mock_db
    monkeypatch.setattr(ingest, "ArangoClient", MagicMock(return_value=mock_arango))

    ingest.ingest(full=True)

    assert mock_db.create_graph.called
    defs = mock_db.create_graph.call_args[1]["edge_definitions"]
    assert {
        "edge_collection": "area_contains",
        "from_vertex_collections": ["area"],
        "to_vertex_collections": ["entity"],
    } in defs
    assert {
        "edge_collection": "device_of",
        "from_vertex_collections": ["device"],
        "to_vertex_collections": ["entity"],
    } in defs
