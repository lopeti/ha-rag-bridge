from __future__ import annotations

import json
import sys
import typer

__all__ = ["app", "main"]

app = typer.Typer()


@app.command()
def ingest(path: str) -> None:
    """Run the ingest pipeline for PATH."""
    from ha_rag_bridge.ingest import run

    run(path)


@app.command()
def query(question: str, top_k: int = typer.Option(3, '--top-k', '-k')) -> None:
    """Query the RAG pipeline and output JSON."""
    from ha_rag_bridge.pipeline import query as pipeline_query

    result = pipeline_query(question, top_k=top_k)
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> None:
    app(prog_name="ha-rag", args=argv)


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
