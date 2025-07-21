from __future__ import annotations

import argparse
import os
from time import perf_counter

from colorama import Fore, Style, init

from . import run as bootstrap_run
from ha_rag_bridge.db.index import IndexManager


def _reindex(collection: str | None, *, force: bool = False, dry_run: bool = False) -> int:
    """Rebuild vector index for given collection or all."""
    from arango import ArangoClient
    from ha_rag_bridge.logging import get_logger

    logger = get_logger(__name__)
    try:
        arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db = arango.db(
            os.getenv("ARANGO_DB", "_system"),
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )
    except KeyError as exc:
        logger.error("missing config", missing=str(exc))
        return 2

    collections = []
    if collection:
        if not db.has_collection(collection):
            logger.error("collection not found", collection=collection)
            return 2
        collections = [collection]
    else:
        collections = [c["name"] for c in db.collections() if not c["name"].startswith("_")]

    embed_dim = int(os.getenv("EMBED_DIM", "1536"))
    dropped = created = 0
    for name in collections:
        col = db.collection(name)
        idx = next((i for i in col.indexes() if i["type"] == "vector"), None)
        if idx and (force or idx.get("dimensions") != embed_dim):
            if not dry_run:
                col.delete_index(idx["id"])
            logger.warning("vector index recreated", collection=name, force=force)
            dropped += 1
            idx = None
        if not idx:
            if not dry_run:
                IndexManager(col, db).ensure_vector("embedding", dimensions=embed_dim)
            created += 1
    logger.info(
        "reindex finished",
        collection=collection or "all",
        dropped=dropped,
        created=created,
        dimensions=embed_dim,
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ha-rag-bootstrap")
    parser.add_argument("--dry-run", action="store_true", help="plan only, no changes")
    parser.add_argument("--force", action="store_true", help="drop+recreate on dim mismatch")
    parser.add_argument("--reindex", nargs="?", const="all", metavar="collection", help="rebuild HNSW index")
    parser.add_argument("--quiet", action="store_true", help="only WARN and ERROR logs")
    parser.add_argument("--skip-invalid", action="store_true", help="skip invalid collection names")
    parser.add_argument("--rename-invalid", action="store_true", help="auto rename invalid collection names")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    init()

    if args.quiet:
        os.environ["LOG_LEVEL"] = "WARNING"

    start = perf_counter()
    try:
        if args.reindex is not None:
            collection = None if args.reindex == "all" else args.reindex
            code = _reindex(collection, force=args.force, dry_run=args.dry_run)
        else:
            code = bootstrap_run(
                None,
                dry_run=args.dry_run,
                force=args.force,
                skip_invalid=args.skip_invalid,
                rename_invalid=args.rename_invalid,
            )
    except ValueError as e:
        from ha_rag_bridge.logging import get_logger

        logger = get_logger(__name__)
        logger.critical("bootstrap abort", error=str(e))
        raise SystemExit(2)
    took = int((perf_counter() - start) * 1000)
    dim = int(os.getenv("EMBED_DIM", "1536"))

    icon = f"{Fore.GREEN}✓{Style.RESET_ALL}" if code == 0 else f"{Fore.RED}✗{Style.RESET_ALL}"
    print(f"{icon} {dim}d {took}ms")
    raise SystemExit(code)

