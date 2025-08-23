import os
from unittest.mock import MagicMock
import pytest

from ha_rag_bridge.bootstrap import cli, naming
from ha_rag_bridge.bootstrap.plan_validator import validate_plan
from ha_rag_bridge.bootstrap.plan import Step
import ha_rag_bridge.bootstrap as boot


def test_plan_validate():
    plan = [Step(name="_bad")]
    with pytest.raises(ValueError):
        validate_plan(plan)


def setup_env():
    os.environ["ARANGO_URL"] = "http://db"
    os.environ["ARANGO_USER"] = "root"
    os.environ["ARANGO_PASS"] = "pass"
    os.environ["AUTO_BOOTSTRAP"] = "1"


def test_rename_invalid_suffix(monkeypatch):
    setup_env()
    created = []

    def fake_create(db, name, *, edge=False, force=False):
        created.append(name)
        return MagicMock()

    monkeypatch.setattr(boot.naming, "safe_create_collection", fake_create)

    def fake_impl(*, force=False, skip_invalid=False, rename_invalid=False):
        existing = {"bad"}
        name = "_bad"
        if not naming.is_valid(name):
            if rename_invalid:
                name = naming.to_valid_name(name, existing)
                fake_create(None, name)
            elif skip_invalid:
                return
            else:
                raise ValueError(f"illegal collection name '{name}'")

    monkeypatch.setattr(boot, "_bootstrap_impl", fake_impl)

    with pytest.raises(SystemExit) as exc:
        cli.main(["--rename-invalid"])
    assert exc.value.code == 0
    assert created == ["bad__1"]
