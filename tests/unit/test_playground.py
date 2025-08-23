"""Smoke-test: a Streamlit playground modulja hiba nélkül importálható."""

import importlib

import pytest


pytest.importorskip("streamlit")


def test_streamlit_app_import(monkeypatch):
    """A streamlit modul betöltése ne fusson valódi lekérdezést."""

    # dummy query → ne hívjuk a valódi pipeline-t
    monkeypatch.setattr("ha_rag_bridge.query", lambda *_a, **_kw: {})

    importlib.import_module("ha_rag_bridge.playground.streamlit_app")
