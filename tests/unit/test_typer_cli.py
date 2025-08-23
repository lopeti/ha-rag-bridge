"""Smoke-tests for the Typer CLI."""

from typer.testing import CliRunner

from ha_rag_bridge.cli import app


runner = CliRunner()


def test_query_smoke(monkeypatch):
    """`ha-rag query` should call the pipeline and emit JSON."""

    def _stubbed_query(question: str, top_k: int = 3):  # noqa: D401
        # simple deterministic stub so we don't hit the real pipeline
        return {"question": question, "answer": "ok", "top_k": top_k}

    monkeypatch.setattr("ha_rag_bridge.pipeline.query", _stubbed_query)

    result = runner.invoke(app, ["query", "Mi az a RAG?"])

    assert result.exit_code == 0
    assert '"answer": "ok"' in result.stdout


def test_ingest_smoke(monkeypatch, tmp_path):
    """`ha-rag ingest` should invoke the ingest pipeline without error."""

    called = {"flag": False}

    def _stubbed_run(path: str):  # noqa: D401
        called["flag"] = True
        assert path == str(tmp_path)

    monkeypatch.setattr("ha_rag_bridge.ingest.run", _stubbed_run)

    result = runner.invoke(app, ["ingest", str(tmp_path)])

    assert result.exit_code == 0
    assert called["flag"] is True
