import os
import pytest

from ha_rag_bridge.bootstrap import cli


@pytest.mark.parametrize(
    "argv,exp",
    [
        (
            ["--dry-run"],
            {
                "dry_run": True,
                "force": False,
                "reindex": None,
                "skip_invalid": False,
                "rename_invalid": False,
            },
        ),
        (
            ["--force", "--reindex", "embeddings"],
            {
                "dry_run": False,
                "force": True,
                "reindex": "embeddings",
                "skip_invalid": False,
                "rename_invalid": False,
            },
        ),
        (
            ["--skip-invalid"],
            {
                "dry_run": False,
                "force": False,
                "reindex": None,
                "skip_invalid": True,
                "rename_invalid": False,
            },
        ),
        (
            ["--rename-invalid"],
            {
                "dry_run": False,
                "force": False,
                "reindex": None,
                "skip_invalid": False,
                "rename_invalid": True,
            },
        ),
    ],
)
def test_cli_parsing(monkeypatch, argv, exp):
    called = {}

    def fake_run(
        plan, *, dry_run=False, force=False, skip_invalid=False, rename_invalid=False
    ):
        called["run"] = {
            "dry_run": dry_run,
            "force": force,
            "skip_invalid": skip_invalid,
            "rename_invalid": rename_invalid,
        }
        return 0

    def fake_reindex(collection=None, *, force=False, dry_run=False):
        called["reindex"] = {
            "collection": collection,
            "force": force,
            "dry_run": dry_run,
        }
        return 0

    monkeypatch.setattr(cli, "bootstrap_run", fake_run)
    monkeypatch.setattr(cli, "_reindex", fake_reindex)
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 0
    if exp["reindex"] is None:
        assert called["run"] == {
            "dry_run": exp["dry_run"],
            "force": exp["force"],
            "skip_invalid": exp.get("skip_invalid", False),
            "rename_invalid": exp.get("rename_invalid", False),
        }
    else:
        assert called["reindex"] == {
            "collection": exp["reindex"],
            "force": exp["force"],
            "dry_run": exp["dry_run"],
        }


def test_cli_quiet(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.setattr(cli, "bootstrap_run", lambda *a, **k: 0)
    with pytest.raises(SystemExit):
        cli.main(["--quiet"])
    assert os.environ["LOG_LEVEL"] == "WARNING"
