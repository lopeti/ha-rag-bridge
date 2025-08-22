"""Cluster management service for semantic entity clustering."""

from typing import List, Dict, Any, Optional, cast
from datetime import datetime, timezone
from arango import ArangoClient
from arango.database import StandardDatabase
import os

from ha_rag_bridge.logging import get_logger
from app.services.integrations.embeddings import get_backend

logger = get_logger(__name__)


class ClusterManager:
    """Manages semantic entity clusters for improved RAG retrieval."""

    def __init__(self, db: Optional[StandardDatabase] = None):
        """Initialize cluster manager with database connection."""
        if db is None:
            arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
            db_name = os.getenv("ARANGO_DB", "_system")
            self.db = arango.db(
                db_name,
                username=os.environ["ARANGO_USER"],
                password=os.environ["ARANGO_PASS"],
            )
        else:
            self.db = db

        backend_name = os.getenv("EMBEDDING_BACKEND", "local").lower()
        self.embedding_backend = get_backend(backend_name)
        self.cluster_collection = self.db.collection("cluster")
        self.cluster_entity_collection = self.db.collection("cluster_entity")

    def create_cluster(
        self,
        key: str,
        name: str,
        cluster_type: str,
        description: str,
        query_patterns: List[str],
        areas: Optional[List[str]] = None,
        domains: Optional[List[str]] = None,
        scope: str = "specific",
    ) -> Dict[str, Any]:
        """Create a new semantic cluster.

        Args:
            key: Unique cluster key
            name: Display name for the cluster
            cluster_type: micro_cluster, macro_cluster, or overview_cluster
            description: Natural language description of the cluster
            query_patterns: List of query patterns this cluster should match
            areas: Associated Home Assistant areas
            domains: Associated Home Assistant domains
            scope: Query scope (specific, area_wide, global)

        Returns:
            Created cluster document
        """
        # Generate cluster embedding from description and query patterns
        text_for_embedding = f"{description}. Patterns: {' '.join(query_patterns)}"
        try:
            embedding = self.embedding_backend.embed([text_for_embedding])[0]
        except Exception as exc:
            logger.warning(f"Failed to generate embedding for cluster {key}: {exc}")
            embedding = []

        cluster_doc = {
            "_key": key,
            "name": name,
            "type": cluster_type,
            "scope": scope,
            "description": description,
            "embedding": embedding,
            "query_patterns": query_patterns,
            "areas": areas or [],
            "domains": domains or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            result = self.cluster_collection.insert(cluster_doc)
            logger.info(f"Created cluster: {key} ({cluster_type})")
            return {**cluster_doc, "_id": result["_id"], "_rev": result["_rev"]}
        except Exception as exc:
            logger.error(f"Failed to create cluster {key}: {exc}")
            raise

    def add_entity_to_cluster(
        self,
        cluster_key: str,
        entity_id: str,
        role: str = "primary",
        weight: float = 1.0,
        context_boost: float = 1.0,
    ) -> Dict[str, Any]:
        """Add an entity to a cluster with specified role and weight.

        Args:
            cluster_key: The cluster to add entity to
            entity_id: Home Assistant entity ID
            role: Entity role (primary, related)
            weight: Base relevance weight
            context_boost: Context-specific boost factor

        Returns:
            Created edge document
        """
        edge_doc = {
            "_from": f"cluster/{cluster_key}",
            "_to": f"entity/{entity_id}",  # Assumes entity collection uses entity_id as key
            "label": "contains_entity",
            "role": role,
            "weight": weight,
            "context_boost": context_boost,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            result = self.cluster_entity_collection.insert(edge_doc)
            logger.debug(f"Added entity {entity_id} to cluster {cluster_key} as {role}")
            return {**edge_doc, "_id": result["_id"], "_rev": result["_rev"]}
        except Exception as exc:
            logger.error(
                f"Failed to add entity {entity_id} to cluster {cluster_key}: {exc}"
            )
            raise

    def search_clusters(
        self,
        query_vector: List[float],
        cluster_types: Optional[List[str]] = None,
        k: int = 5,
        threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Search for relevant clusters using vector similarity.

        Args:
            query_vector: Query embedding vector
            cluster_types: Filter by cluster types (micro_cluster, etc.)
            k: Number of clusters to return
            threshold: Minimum similarity threshold

        Returns:
            List of matching clusters with similarity scores
        """
        # Build AQL query for cluster vector search
        aql_parts: List[str] = ["FOR c IN cluster", "FILTER LENGTH(c.embedding) > 0"]
        bind_vars: Dict[str, Any] = {
            "query_vector": query_vector,
            "k": k,
            "threshold": threshold,
        }

        if cluster_types:
            aql_parts.append("FILTER c.type IN @cluster_types")
            bind_vars["cluster_types"] = cluster_types

        aql_parts.extend(
            [
                "LET score = COSINE_SIMILARITY(c.embedding, @query_vector)",
                "FILTER score >= @threshold",
                "SORT score DESC",
                "LIMIT @k",
                "RETURN MERGE(c, {similarity_score: score})",
            ]
        )

        aql = " ".join(aql_parts)

        try:
            cursor = self.db.aql.execute(aql, bind_vars=bind_vars)
            results = list(cursor)
            logger.debug(f"Found {len(results)} matching clusters")
            return results
        except Exception as exc:
            logger.error(f"Cluster search failed: {exc}")
            return []

    def get_cluster_entities(
        self, cluster_keys: List[str], role_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all entities associated with specified clusters.

        Args:
            cluster_keys: List of cluster keys to expand
            role_filter: Optional role filter (primary, related)

        Returns:
            List of entities with cluster context
        """
        aql_parts: List[str] = [
            "FOR cluster_key IN @cluster_keys",
            "FOR entity IN 1..1 OUTBOUND CONCAT('cluster/', cluster_key) cluster_entity",
            "LET edge = (FOR e IN cluster_entity FILTER e._from == CONCAT('cluster/', cluster_key)",
            "AND e._to == entity._id RETURN e)[0]",
        ]
        bind_vars: Dict[str, Any] = {"cluster_keys": cluster_keys}

        if role_filter:
            aql_parts.append("FILTER edge.role == @role_filter")
            bind_vars["role_filter"] = role_filter

        aql_parts.extend(
            [
                "RETURN {",
                "  entity: entity,",
                "  cluster_key: cluster_key,",
                "  role: edge.role,",
                "  weight: edge.weight,",
                "  context_boost: edge.context_boost",
                "}",
            ]
        )

        aql = " ".join(aql_parts)

        try:
            cursor = self.db.aql.execute(aql, bind_vars=bind_vars)
            results = list(cursor)
            logger.debug(
                f"Retrieved {len(results)} entities from {len(cluster_keys)} clusters"
            )
            return results
        except Exception as exc:
            logger.error(f"Failed to get cluster entities: {exc}")
            return []

    def bootstrap_initial_clusters(self) -> None:
        """Create initial set of semantic clusters for common use cases."""
        logger.info("Bootstrapping initial semantic clusters...")

        # Define initial clusters based on our optimization plan
        initial_clusters = [
            {
                "key": "solar_performance",
                "name": "Napelem teljesítmény cluster",
                "cluster_type": "micro_cluster",
                "description": "Napelemes rendszer teljesítmény mutatók és energiatermelés",
                "query_patterns": [
                    "hogy termel a napelem",
                    "solar performance",
                    "mennyi áramot termel",
                    "battery töltöttség",
                    "napelemes teljesítmény",
                    "energia termelés",
                ],
                "areas": ["kert", "garden"],
                "domains": ["sensor"],
                "scope": "specific",
            },
            {
                "key": "climate_control",
                "name": "Klímaberendezés vezérlés cluster",
                "cluster_type": "micro_cluster",
                "description": "Hőmérséklet, páratartalom és klímaberendezés vezérlés",
                "query_patterns": [
                    "hőmérséklet",
                    "temperature",
                    "páratartalom",
                    "humidity",
                    "klíma",
                    "climate",
                    "fűtés",
                    "heating",
                ],
                "domains": ["climate", "sensor"],
                "scope": "area_wide",
            },
            {
                "key": "lighting_control",
                "name": "Világítás vezérlés cluster",
                "cluster_type": "micro_cluster",
                "description": "Fények, kapcsolók és világítás automatizálás",
                "query_patterns": [
                    "kapcsold fel",
                    "kapcsold le",
                    "turn on light",
                    "turn off light",
                    "világítás",
                    "lighting",
                    "lámpa",
                    "fény",
                ],
                "domains": ["light", "switch"],
                "scope": "area_wide",
            },
            {
                "key": "security_sensors",
                "name": "Biztonsági érzékelők cluster",
                "cluster_type": "micro_cluster",
                "description": "Ajtó/ablak érzékelők, mozgásérzékelő és kamerák",
                "query_patterns": [
                    "biztonság",
                    "security",
                    "ajtó",
                    "ablak",
                    "door",
                    "window",
                    "mozgás",
                    "motion",
                    "kamera",
                ],
                "domains": ["binary_sensor", "camera"],
                "scope": "global",
            },
            {
                "key": "house_overview",
                "name": "Ház áttekintés cluster",
                "cluster_type": "overview_cluster",
                "description": "Teljes ház állapot összesítő minden rendszerrel",
                "query_patterns": [
                    "mi újság otthon",
                    "what's happening at home",
                    "ház állapota",
                    "house status",
                    "minden rendszer",
                    "all systems",
                    "otthon helyzet",
                ],
                "scope": "global",
            },
        ]

        created_count = 0
        for cluster_def in initial_clusters:
            try:
                self.create_cluster(
                    key=cast(str, cluster_def["key"]),
                    name=cast(str, cluster_def["name"]),
                    cluster_type=cast(str, cluster_def["cluster_type"]),
                    description=cast(str, cluster_def["description"]),
                    query_patterns=cast(List[str], cluster_def["query_patterns"]),
                    areas=cast(Optional[List[str]], cluster_def.get("areas")),
                    domains=cast(Optional[List[str]], cluster_def.get("domains")),
                    scope=cast(str, cluster_def.get("scope", "specific")),
                )
                created_count += 1
            except Exception as exc:
                # Skip if cluster already exists
                if "unique constraint violated" in str(exc).lower():
                    logger.debug(f"Cluster {cluster_def['key']} already exists")
                else:
                    logger.warning(
                        f"Failed to create cluster {cluster_def['key']}: {exc}"
                    )

        logger.info(f"Bootstrap completed: {created_count} clusters created")


# Global instance for use in main application
cluster_manager = ClusterManager()
