from __future__ import annotations

import json
import os
import sys
import typer
from pathlib import Path

__all__ = ["app", "main"]

app = typer.Typer()


def load_dotenv():
    """Load environment variables from .env file"""
    env_path = Path("/app/.env")
    if env_path.exists():
        print(f"Loading environment variables from {env_path}")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Don't override existing environment variables
                    if key not in os.environ:
                        os.environ[key] = value
                        if key == "HA_TOKEN" and value == "YOUR_HA_TOKEN_HERE":
                            print(
                                "Warning: You need to set your actual Home Assistant token in .env file"
                            )


@app.command()
def ingest(
    entity: str = typer.Option(None, "--entity", help="Single entity id"),
    full: bool = typer.Option(
        False, "--full", help="Full ingest of all states (re-embed everything)"
    ),
    delay: int = typer.Option(
        5, "--delay", help="Delay in seconds between embedding batches"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
) -> None:
    """Run the ingest pipeline for Home Assistant entities."""
    # Load environment variables from .env file
    load_dotenv()

    from scripts.ingest import ingest as run_ingest

    # Set debug logging if requested
    if debug:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    # If no arguments are provided and in debug mode, default to full ingest
    if not full and not entity and debug:
        typer.echo(
            "No entity or full flag specified, defaulting to full ingest in debug mode"
        )
        full = True
    elif not full and not entity:
        typer.echo("Error: Either --full or --entity must be specified")
        raise typer.Exit(code=1)

    try:
        run_ingest(entity, delay_sec=delay, full=full)
    except KeyError as e:
        typer.echo(f"Error: Missing required environment variable: {e}")
        typer.echo("Required environment variables:")
        typer.echo("  HA_URL - Home Assistant URL")
        typer.echo("  HA_TOKEN - Home Assistant access token")
        typer.echo("  ARANGO_URL - ArangoDB URL")
        typer.echo("  ARANGO_USER - ArangoDB username")
        typer.echo("  ARANGO_PASS - ArangoDB password")
        raise typer.Exit(code=1)


@app.command()
def query(question: str, top_k: int = typer.Option(3, "--top-k", "-k")) -> None:
    """Query the RAG pipeline and output JSON."""
    from ha_rag_bridge.pipeline import query as pipeline_query

    result = pipeline_query(question, top_k=top_k)
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")


@app.command()
def eval(
    dataset: str, threshold: float = typer.Option(0.2, "--threshold", "-t")
) -> None:
    """Run the evaluation harness on DATASET."""
    from ha_rag_bridge.eval import run as eval_run

    try:
        score = eval_run(dataset, threshold)
    except SystemExit as exc:
        # A runner már eldöntötte, hogy siker (0) vagy bukás (1-től felfelé),
        # propagáljuk ugyanazzal a kóddal a Typer exit-hez.
        raise typer.Exit(code=exc.code)
    else:
        typer.echo(f"score={score:.3f}")


def main(argv: list[str] | None = None) -> None:
    app(prog_name="ha-rag", args=argv)


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
