import os
from arango import ArangoClient
from arango.exceptions import GraphCreateError, GraphListError
from ha_rag_bridge.logging import get_logger
from .cli import main


def ensure_arango_graph():
    """Ensure the required ArangoDB graph exists, create if missing."""
    logger = get_logger(__name__)
    try:
        arango_url = os.environ["ARANGO_URL"]
        db_name = os.getenv("ARANGO_DB", "_system")
        db = ArangoClient(hosts=arango_url).db(
            db_name,
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )
        graph_name = "ha_entity_graph"
        # Check if graph already exists
        try:
            graphs = db.graphs()
            if any(g["_key"] == graph_name for g in graphs):
                logger.info("ArangoDB graph already exists", graph=graph_name)
                return
        except GraphListError as exc:
            logger.warning("Could not list graphs", error=str(exc))
        # Try to create the graph
        try:
            db.create_graph(
                graph_name,
                edge_definitions=[
                    {
                        "edge_collection": "edge",
                        "from_vertex_collections": ["area", "device"],
                        "to_vertex_collections": ["entity"],
                    }
                ],
                orphan_collections=[],
            )
            logger.info("Created ArangoDB graph", graph=graph_name)
        except GraphCreateError as exc:
            logger.error(
                "Failed to create ArangoDB graph", graph=graph_name, error=str(exc)
            )
        except Exception as exc:
            logger.error("Unexpected error during graph creation", error=str(exc))
    except Exception as exc:
        logger.error("Error in ensure_arango_graph", error=str(exc))


ensure_arango_graph()

if __name__ == "__main__":
    main()
