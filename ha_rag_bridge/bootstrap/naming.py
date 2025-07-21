import re
from typing import Iterable

RESERVED_PREFIXES = {"_"}
INVALID_CHARS = r"[^a-zA-Z0-9_-]"

VALID_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,254}$")


def is_valid(name: str) -> bool:
    """Return True if collection name is valid."""
    if not name:
        return False
    if name[0] in RESERVED_PREFIXES:
        return False
    if re.search(INVALID_CHARS, name):
        return False
    return bool(VALID_RE.match(name)) and not name.lower().startswith("arango")


def to_valid_name(name: str, existing: Iterable[str] | None = None) -> str:
    """Return a valid name derived from *name*.

    Invalid prefix ``arango`` is stripped and apostrophes removed. If the
    result already exists in *existing* or is still invalid, a numerical suffix
    ``__N`` is appended until a valid unique name is found.
    """
    base = name
    if base.lower().startswith("arango"):
        base = base[6:]
    base = base.replace("'", "")
    # ensure starts with letter
    base = re.sub(r"^[^a-zA-Z]+", "", base)
    if not base:
        base = "c"
    if existing is None:
        existing = set()
    candidate = base
    i = 1
    while (candidate in existing) or not is_valid(candidate):
        candidate = f"{base}__{i}"
        i += 1
    return candidate


def safe_create_collection(db, name: str, *, edge: bool = False, force: bool = False):
    from ha_rag_bridge.logging import get_logger
    import structlog

    logger = get_logger(__name__)
    req_id = structlog.contextvars.get_contextvars().get("req_id")

    logger.debug("ensure collection", name=name, edge=edge, force=force, req_id=req_id)

    if not is_valid(name):
        raise ValueError(f"illegal collection name '{name}'")

    if db.has_collection(name):
        return db.collection(name)

    try:
        return db.create_collection(name, edge=edge)
    except getattr(db, "error_dup_name", Exception):
        return db.collection(name)
    except Exception as exc:
        logger.error("create collection failed", name=name, edge=edge, error=str(exc))
        raise


def safe_rename(col, new_name: str) -> None:
    if col.name != new_name and not col.database.has_collection(new_name):
        col.rename(new_name)
