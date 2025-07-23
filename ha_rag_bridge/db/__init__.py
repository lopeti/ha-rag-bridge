from arango.database import StandardDatabase
from arango.exceptions import ArangoServerError, DocumentParseError
try:  # python-arango >=8.2
    from arango.exceptions import ViewNotFoundError
except ImportError:  # pragma: no cover - older versions
    from arango.exceptions import ViewGetError as ViewNotFoundError

from ha_rag_bridge.logging import get_logger


class BridgeDB(StandardDatabase):
    """
    A thin wrapper around StandardDatabase that provides utility methods for 
    working with collections in a simplified manner.

    This class adds helper methods to streamline common operations, such as 
    retrieving or ensuring the existence of collections. These methods are 
    designed to be compatible with workflows inspired by ArangoDB's arangosh 
    (ArangoDB shell) but are adapted for Python usage.

    Helper methods:
        - get_col(name): Returns a collection handle if it exists, otherwise None.
        - ensure_col(name, edge=False): Ensures a collection exists, creating it 
          if necessary. Supports both document and edge collections.
    """
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

    def has_view(self, name: str) -> bool:
        """Return True if the view exists."""
        try:
            self.view(name)
            return True
        except ViewNotFoundError:
            return False
        except DocumentParseError:  # pragma: no cover - malformed response
            return False

    def create_arangosearch_view(self, name: str, properties: dict = None):
        """
        Return an existing ArangoSearch view or create one.
        Signature and behavior now matches python-arango driver for compatibility.
        """
        if self.has_view(name):
            return self.view(name)
        try:
            return self.create_view(
                name,
                view_type="arangosearch",
                properties=properties or {},
            )
        except ArangoServerError as exc:  # pragma: no cover - connection errors
            logger = get_logger(__name__)
            logger.error(
                "create view failed",
                error_code=exc.error_code,
                error_message=exc.error_message,
            )
            raise SystemExit(4)
        except ValueError as exc:  # invalid name
            raise SystemExit(2) from exc

