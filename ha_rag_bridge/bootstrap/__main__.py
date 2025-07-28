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
        db_name = os.getenv("ARANGO_DB", "ha_graph")
        logger.info("Connecting to ArangoDB", url=arango_url, database=db_name)
        db = ArangoClient(hosts=arango_url).db(
            db_name,
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        # Ellenőrizzük és létrehozzuk a szükséges kollekciókat
        collections = {
            "entity": False,  # nem edge
            "area": False,  # nem edge
            "device": False,  # nem edge
            "edge": True,  # edge kollekció
        }

        for coll_name, is_edge in collections.items():
            try:
                if not db.has_collection(coll_name):
                    logger.info("Creating collection", name=coll_name, is_edge=is_edge)
                    db.create_collection(coll_name, edge=is_edge)
                else:
                    logger.info("Collection exists", name=coll_name)
            except Exception as exc:
                logger.error(
                    "Failed to create/check collection",
                    name=coll_name,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )

        graph_name = "ha_entity_graph"
        # Check if graph already exists
        try:
            # Közvetlenül ellenőrizzük, hogy létezik-e a gráf
            if db.has_graph(graph_name):
                logger.info("ArangoDB graph already exists", graph=graph_name)
                return

            # Ha nem létezik, akkor listázzuk az összes gráfot a loghoz
            graphs = db.graphs()
            existing_graphs = [g.get("_key", "") for g in graphs]
            logger.info("Existing graphs", graphs=existing_graphs)
        except GraphListError as exc:
            logger.warning(
                "Could not list graphs", error_type=type(exc).__name__, error=str(exc)
            )

        # Try to create the graph
        try:
            logger.info(
                "Creating graph definition",
                graph=graph_name,
                edge_collection="edge",
                from_cols=["area", "device"],
                to_cols=["entity"],
            )

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
                "Failed to create ArangoDB graph",
                graph=graph_name,
                error_code=getattr(exc, "error_code", None),
                error_message=getattr(exc, "error_message", None),
                error=str(exc),
            )
            # Próbáljuk meg lekérni a gráfot - talán létezik, csak valami más hiba történt
            try:
                if db.has_graph(graph_name):
                    logger.info("Graph exists despite error", graph=graph_name)
            except Exception:
                pass
        except Exception as exc:
            logger.error(
                "Unexpected error during graph creation",
                error_type=type(exc).__name__,
                error=str(exc),
            )
    except Exception as exc:
        logger.error(
            "Error in ensure_arango_graph",
            error_type=type(exc).__name__,
            error=str(exc),
        )


ensure_arango_graph()

if __name__ == "__main__":
    main()
