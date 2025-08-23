from __future__ import annotations

__version__ = "0.14.0"


def run_ingest(path: str) -> None:
    """Wrapper to run the ingest pipeline."""
    from scripts.ingestion.ingest import ingest

    ingest(path)


def query(question: str, top_k: int = 3):
    """Proxy to the pipeline query API."""
    from .pipeline import query as pipeline_query

    return pipeline_query(question, top_k=top_k)
