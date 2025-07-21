from arango.database import StandardDatabase
from arango.exceptions import ArangoServerError

from ha_rag_bridge.logging import get_logger


class BridgeDB(StandardDatabase):
    """Thin wrapper adding helpers compatible with arangosh prose."""

    def get_col(self, name: str):
        """Return collection handle if exists else None."""
        return self.collection(name) if self.has_collection(name) else None

    def ensure_col(self, name: str, *, edge: bool = False):
        try:
            if self.has_collection(name):
                return self.collection(name)
            return self.create_collection(name, edge=edge)
        except ArangoServerError as exc:  # pragma: no cover - connection errors
            logger = get_logger(__name__)
            logger.error(
                "create collection failed",
                error_code=exc.error_code,
                error_message=exc.error_message,
            )
            raise SystemExit(4)
        except ValueError as exc:  # invalid name
            raise SystemExit(2) from exc
