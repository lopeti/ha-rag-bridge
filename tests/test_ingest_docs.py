import os
from unittest.mock import MagicMock

import scripts.ingest_docs as ingest_docs


def setup_env():
    os.environ.update({
        "ARANGO_URL": "http://db",
        "ARANGO_USER": "root",
        "ARANGO_PASS": "pass",
        "EMBEDDING_BACKEND": "local",
    })


def make_page(word: str, n: int = 900) -> str:
    return " ".join([word] * n)


def test_ingest_docs(monkeypatch):
    setup_env()
    pages = [(1, make_page("a")), (2, make_page("b"))]
    monkeypatch.setattr(ingest_docs, "extract_pages_text", lambda f: pages)

    mock_backend = MagicMock()
    mock_backend.embed.return_value = [[0.0] * 1536] * 4
    monkeypatch.setattr(ingest_docs, "LocalBackend", MagicMock(return_value=mock_backend))

    mock_doc_col = MagicMock()
    mock_edge_col = MagicMock()

    def get_collection(name):
        return {"document": mock_doc_col, "edge": mock_edge_col}[name]

    mock_db = MagicMock()
    mock_db.collection.side_effect = get_collection
    mock_arango = MagicMock()
    mock_arango.db.return_value = mock_db
    monkeypatch.setattr(ingest_docs, "ArangoClient", MagicMock(return_value=mock_arango))

    ingest_docs.ingest("dummy.pdf", "dev1")

    args, _ = mock_doc_col.insert_many.call_args
    assert len(args[0]) == 4
    mock_edge_col.insert.assert_called_once()

