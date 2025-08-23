from typer.testing import CliRunner

from ha_rag_bridge.cli import app

runner = CliRunner()

dataset = "tests/fixtures/qa_pairs.json"


def test_eval_success(monkeypatch):
    mapping = {
        "Mi a neved?": "ChatGPT vagyok.",
        "Hány lába van egy lónak?": "Egy lónak négy lába van.",
    }

    def _query(question: str, top_k: int = 3):
        return {"answer": mapping[question]}

    monkeypatch.setattr("ha_rag_bridge.pipeline.query", _query)

    result = runner.invoke(app, ["eval", dataset, "--threshold", "0.9"])
    assert result.exit_code == 0


def test_eval_failure(monkeypatch):
    def _query(question: str, top_k: int = 3):
        return {"answer": "irrelevant"}

    monkeypatch.setattr("ha_rag_bridge.pipeline.query", _query)

    result = runner.invoke(app, ["eval", dataset, "--threshold", "0.9"])
    assert result.exit_code != 0
