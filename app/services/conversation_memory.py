"""Conversation memory service for multi-turn RAG optimization."""

import math
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from arango import ArangoClient

from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ConversationEntity:
    """Entity stored in conversation memory."""

    entity_id: str
    relevance_score: float
    mentioned_at: datetime
    context: str
    area: Optional[str] = None
    domain: Optional[str] = None
    boost_weight: float = 1.0
    context_type: str = "primary"  # "primary", "secondary", "historical"


@dataclass
class ConversationMemory:
    """Complete conversation memory state with topic tracking."""

    conversation_id: str
    entities: List[ConversationEntity]
    areas_mentioned: Set[str]
    domains_mentioned: Set[str]
    last_updated: datetime
    ttl: datetime
    query_count: int = 1

    # NEW: Topic tracking fields
    topic_summary: Optional[str] = None
    current_focus: Optional[str] = None
    intent_pattern: Optional[str] = None
    topic_domains: Set[str] = field(default_factory=set)
    focus_history: List[str] = field(default_factory=list)
    conversation_summary: Optional[Dict[str, Any]] = None


class ConversationMemoryService:
    """Service for managing conversation memory with TTL."""

    def __init__(self, ttl_minutes: int = 15):
        self.ttl_minutes = ttl_minutes
        self._client = None
        self._db = None

    async def _ensure_connection(self):
        """Ensure database connection is established."""
        if self._db is None:
            self._client = ArangoClient(hosts=os.environ["ARANGO_URL"])
            db_name = os.getenv("ARANGO_DB", "_system")
            self._db = self._client.db(
                db_name,
                username=os.environ["ARANGO_USER"],
                password=os.environ["ARANGO_PASS"],
            )

    def _generate_ttl(self) -> datetime:
        """Generate TTL timestamp for conversation memory."""
        return datetime.utcnow() + timedelta(minutes=self.ttl_minutes)

    async def get_conversation_memory(
        self, conversation_id: str
    ) -> Optional[ConversationMemory]:
        """Retrieve conversation memory if it exists and hasn't expired."""
        await self._ensure_connection()

        try:
            collection = self._db.collection("conversation_memory")
            doc_key = f"conv_{conversation_id}_memory"

            # Try to get the document
            if collection.has(doc_key):
                doc = collection.get(doc_key)

                # Check if TTL has expired
                ttl = datetime.fromisoformat(doc["ttl"].replace("Z", ""))
                if ttl <= datetime.utcnow():
                    logger.debug(f"Conversation memory expired for {conversation_id}")
                    await self._cleanup_expired_memory(conversation_id)
                    return None

                # Convert to ConversationMemory object
                entities = [
                    ConversationEntity(
                        entity_id=e["entity_id"],
                        relevance_score=e["relevance_score"],
                        mentioned_at=datetime.fromisoformat(
                            e["mentioned_at"].replace("Z", "")
                        ),
                        context=e["context"],
                        area=e.get("area"),
                        domain=e.get("domain"),
                        boost_weight=e.get("boost_weight", 1.0),
                        context_type=e.get("context_type", "primary"),
                    )
                    for e in doc["entities"]
                ]

                return ConversationMemory(
                    conversation_id=doc["conversation_id"],
                    entities=entities,
                    areas_mentioned=set(doc["areas_mentioned"]),
                    domains_mentioned=set(doc["domains_mentioned"]),
                    last_updated=datetime.fromisoformat(
                        doc["last_updated"].replace("Z", "")
                    ),
                    ttl=ttl,
                    query_count=doc.get("query_count", 1),
                    # NEW: Topic tracking fields
                    topic_summary=doc.get("topic_summary"),
                    current_focus=doc.get("current_focus"),
                    intent_pattern=doc.get("intent_pattern"),
                    topic_domains=set(doc.get("topic_domains", [])),
                    focus_history=doc.get("focus_history", []),
                    conversation_summary=doc.get("conversation_summary"),
                )

        except Exception as e:
            logger.error(
                f"Error retrieving conversation memory for {conversation_id}: {e}"
            )

        return None

    async def store_conversation_memory(
        self,
        conversation_id: str,
        entities: List[Dict[str, Any]],
        areas_mentioned: Set[str],
        domains_mentioned: Set[str],
        query_context: str = "",
        conversation_summary: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store or update conversation memory with entities and context."""
        await self._ensure_connection()

        try:
            current_time = datetime.utcnow()
            ttl = self._generate_ttl()

            # Get existing memory to merge with
            existing_memory = await self.get_conversation_memory(conversation_id)

            # Convert entities to ConversationEntity objects
            new_entities = []
            for i, entity in enumerate(entities):
                # Determine context type based on relevance and position
                relevance = entity.get("rerank_score", entity.get("similarity", 0.0))
                context_type = self._determine_context_type(
                    entity, relevance, i, query_context
                )

                conv_entity = ConversationEntity(
                    entity_id=entity["entity_id"],
                    relevance_score=relevance,
                    mentioned_at=current_time,
                    context=query_context,
                    area=entity.get("area_name"),
                    domain=entity.get("domain"),
                    boost_weight=self._calculate_boost_weight(entity),
                    context_type=context_type,
                )
                new_entities.append(conv_entity)

            # Merge with existing entities
            if existing_memory:
                # Keep existing entities that are still relevant
                merged_entities = []
                existing_entity_ids = {e.entity_id for e in new_entities}

                for existing_entity in existing_memory.entities:
                    if existing_entity.entity_id not in existing_entity_ids:
                        # Decay boost weight for older entities
                        time_diff = current_time - existing_entity.mentioned_at
                        decay_factor = max(
                            0.5, 1.0 - (time_diff.total_seconds() / (10 * 60))
                        )  # 10 min decay
                        existing_entity.boost_weight *= decay_factor
                        merged_entities.append(existing_entity)

                merged_entities.extend(new_entities)
                all_entities = merged_entities
                merged_areas = existing_memory.areas_mentioned | areas_mentioned
                merged_domains = existing_memory.domains_mentioned | domains_mentioned
                query_count = existing_memory.query_count + 1
            else:
                all_entities = new_entities
                merged_areas = areas_mentioned
                merged_domains = domains_mentioned
                query_count = 1

            # Limit to most relevant entities (max 20)
            all_entities.sort(
                key=lambda e: e.relevance_score * e.boost_weight, reverse=True
            )
            all_entities = all_entities[:20]

            # Extract topic information from conversation summary
            topic_summary = None
            current_focus = None
            intent_pattern = None
            topic_domains = set()
            focus_history = []

            if existing_memory:
                # Preserve existing topic information
                topic_summary = existing_memory.topic_summary
                current_focus = existing_memory.current_focus
                intent_pattern = existing_memory.intent_pattern
                topic_domains = existing_memory.topic_domains.copy()
                focus_history = existing_memory.focus_history.copy()

            if conversation_summary:
                # Update with new summary information
                topic_summary = conversation_summary.get("topic", topic_summary)
                new_focus = conversation_summary.get("current_focus", "")
                if new_focus and new_focus != current_focus:
                    if current_focus:
                        focus_history.append(current_focus)
                    current_focus = new_focus
                    # Keep last 10 focuses
                    focus_history = focus_history[-9:]

                intent_pattern = conversation_summary.get(
                    "intent_pattern", intent_pattern
                )
                if "topic_domains" in conversation_summary:
                    topic_domains.update(conversation_summary["topic_domains"])

            # Create memory document
            memory = ConversationMemory(
                conversation_id=conversation_id,
                entities=all_entities,
                areas_mentioned=merged_areas,
                domains_mentioned=merged_domains,
                last_updated=current_time,
                ttl=ttl,
                query_count=query_count,
                # NEW: Topic tracking fields
                topic_summary=topic_summary,
                current_focus=current_focus,
                intent_pattern=intent_pattern,
                topic_domains=topic_domains,
                focus_history=focus_history,
                conversation_summary=conversation_summary,
            )

            # Convert to ArangoDB document
            doc = {
                "_key": f"conv_{conversation_id}_memory",
                "conversation_id": conversation_id,
                "entities": [
                    {
                        "entity_id": e.entity_id,
                        "relevance_score": e.relevance_score,
                        "mentioned_at": e.mentioned_at.isoformat(),
                        "context": e.context,
                        "area": e.area,
                        "domain": e.domain,
                        "boost_weight": e.boost_weight,
                        "context_type": e.context_type,
                    }
                    for e in memory.entities
                ],
                "areas_mentioned": list(memory.areas_mentioned),
                "domains_mentioned": list(memory.domains_mentioned),
                "last_updated": memory.last_updated.isoformat(),
                "ttl": memory.ttl.isoformat(),
                "query_count": memory.query_count,
                # NEW: Topic tracking fields in storage
                "topic_summary": memory.topic_summary,
                "current_focus": memory.current_focus,
                "intent_pattern": memory.intent_pattern,
                "topic_domains": list(memory.topic_domains),
                "focus_history": memory.focus_history,
                "conversation_summary": memory.conversation_summary,
            }

            # Store/update in database
            collection = self._db.collection("conversation_memory")
            collection.insert(doc, overwrite=True)

            logger.info(
                f"Stored conversation memory for {conversation_id}: "
                f"{len(memory.entities)} entities, {len(memory.areas_mentioned)} areas, "
                f"expires at {memory.ttl.isoformat()}"
            )

            return True

        except Exception as e:
            logger.error(
                f"Error storing conversation memory for {conversation_id}: {e}"
            )
            return False

    def _determine_context_type(
        self,
        entity: Dict[str, Any],
        relevance: float,
        position: int,
        query_context: str,
    ) -> str:
        """Determine context type (primary/secondary/historical) for an entity."""
        # Primary: High relevance entities that directly answer the query
        if relevance > 0.7 or position < 3:
            return "primary"

        # Secondary: Medium relevance entities that provide context
        elif relevance > 0.4 or position < 8:
            return "secondary"

        # Historical: Lower relevance entities for background context
        else:
            return "historical"

    def _calculate_boost_weight(self, entity: Dict[str, Any]) -> float:
        """Calculate initial boost weight for an entity based on its characteristics."""
        base_weight = 1.0

        # Boost primary entities
        if entity.get("is_primary", False):
            base_weight *= 1.5

        # Boost entities with high similarity scores
        similarity = entity.get("similarity", 0.0)
        if similarity > 0.8:
            base_weight *= 1.3
        elif similarity > 0.6:
            base_weight *= 1.1

        # Boost sensor entities (they provide context)
        if entity.get("domain") == "sensor":
            base_weight *= 1.2

        return base_weight

    def _calculate_topic_aware_boost(
        self, entity: Dict[str, Any], memory: Optional[ConversationMemory] = None
    ) -> float:
        """Calculate boost weight with topic awareness and time decay."""
        from ha_rag_bridge.config import get_settings

        settings = get_settings()

        # Start with base boost calculation
        base_weight = self._calculate_boost_weight(entity)

        if not memory or not settings.memory_topic_boost_enabled:
            return base_weight

        # Topic domain matching boost
        entity_domain = entity.get("domain", "")
        if entity_domain and entity_domain in memory.topic_domains:
            base_weight *= 1.3  # 30% boost for topic-relevant domains
            logger.debug(
                f"Topic domain boost for {entity['entity_id']}: {entity_domain}"
            )

        # Current focus area matching boost (strongest boost)
        if memory.current_focus:
            entity_area = entity.get("area_name", "").lower()
            focus_lower = memory.current_focus.lower()

            if entity_area == focus_lower:
                base_weight *= 2.0  # 100% boost for current focus area
                logger.debug(
                    f"Focus area boost for {entity['entity_id']}: {entity_area}"
                )
            elif focus_lower in entity.get("entity_id", "").lower():
                base_weight *= 1.5  # 50% boost for entity ID containing focus
            elif entity_area in memory.focus_history:
                base_weight *= 1.2  # 20% boost for previous focuses

        # Intent pattern matching boost
        if memory.intent_pattern:
            if memory.intent_pattern == "device_control" and entity_domain in [
                "switch",
                "light",
                "climate",
            ]:
                base_weight *= 1.2  # 20% boost for controllable entities
            elif memory.intent_pattern == "status_check" and entity_domain == "sensor":
                base_weight *= 1.2  # 20% boost for sensors during status checks
            elif memory.intent_pattern == "sequential_rooms" and entity_area:
                base_weight *= (
                    1.4  # 40% boost for area-specific entities in room sequences
                )

        # Time decay for conversation memory entities
        if hasattr(entity, "mentioned_at") and entity.get("mentioned_at"):
            try:
                mentioned_at = entity["mentioned_at"]
                if isinstance(mentioned_at, str):
                    mentioned_at = datetime.fromisoformat(mentioned_at.replace("Z", ""))
                elif not isinstance(mentioned_at, datetime):
                    mentioned_at = datetime.now()  # Fallback

                time_since = (datetime.now() - mentioned_at).total_seconds()
                decay_constant = (
                    settings.memory_decay_constant
                )  # From config (default 300s)
                decay_factor = math.exp(-time_since / decay_constant)
                base_weight *= decay_factor

                logger.debug(
                    f"Time decay applied to {entity['entity_id']}: {decay_factor:.2f}"
                )

            except Exception as e:
                logger.warning(
                    f"Failed to apply time decay to {entity.get('entity_id', 'unknown')}: {e}"
                )

        # Cap the boost to prevent extreme values
        return min(base_weight, 3.0)

    async def get_relevant_entities(
        self, conversation_id: str, current_query: str, max_entities: int = 10
    ) -> List[Dict[str, Any]]:
        """Get entities from conversation memory that are relevant to current query."""
        memory = await self.get_conversation_memory(conversation_id)

        if not memory:
            return []

        logger.debug(
            f"Checking {len(memory.entities)} entities from memory for relevance to: {current_query}"
        )

        # Enhanced relevance scoring
        relevant_entities = []
        query_lower = current_query.lower()
        query_words = set(word for word in query_lower.split() if len(word) > 2)

        for entity in memory.entities:
            relevance_score = 0.0
            entity_id_lower = entity.entity_id.lower()
            entity_words = set(
                word
                for word in entity_id_lower.replace(".", " ").replace("_", " ").split()
            )

            # 1. Direct entity ID matching (highest priority)
            if any(word in entity_id_lower for word in query_words):
                relevance_score += 2.0
                logger.debug(
                    f"Direct match: {entity.entity_id} - query contains entity words"
                )

            # 2. Area-based relevance
            if entity.area:
                area_lower = entity.area.lower()
                if area_lower in query_lower:
                    relevance_score += 1.5
                    logger.debug(
                        f"Area match: {entity.entity_id} - area '{entity.area}' in query"
                    )
                # Check area aliases
                area_aliases = {
                    "nappali": ["living", "room"],
                    "konyha": ["kitchen"],
                    "kert": ["garden", "outside", "kint", "kültér"],
                    "fürdőszoba": ["bathroom", "fürdő"],
                }
                for area, aliases in area_aliases.items():
                    if entity.area.lower() == area and any(
                        alias in query_lower for alias in aliases
                    ):
                        relevance_score += 1.3
                        logger.debug(
                            f"Area alias match: {entity.entity_id} - {entity.area} matches alias"
                        )

            # 3. Domain-based relevance
            if entity.domain:
                domain_patterns = {
                    "light": ["lámpa", "light", "világítás", "fény", "kapcsol"],
                    "sensor": [
                        "hőmérséklet",
                        "temperature",
                        "páratartalom",
                        "humidity",
                        "fok",
                        "sensor",
                    ],
                    "switch": ["kapcsoló", "switch", "kapcsol"],
                    "climate": ["klíma", "climate", "fűtés", "heating"],
                    "cover": ["redőny", "blind", "shutter", "cover"],
                }
                for domain, patterns in domain_patterns.items():
                    if entity.domain == domain and any(
                        pattern in query_lower for pattern in patterns
                    ):
                        relevance_score += 1.2
                        logger.debug(
                            f"Domain match: {entity.entity_id} - domain '{entity.domain}' matches pattern"
                        )

            # 4. Semantic word overlap
            word_overlap = len(query_words.intersection(entity_words))
            if word_overlap > 0:
                relevance_score += word_overlap * 0.5
                logger.debug(
                    f"Word overlap: {entity.entity_id} - {word_overlap} words match"
                )

            # 5. Recency boost (newer mentions are more relevant)
            time_diff = datetime.utcnow() - entity.mentioned_at
            if time_diff.total_seconds() < 300:  # 5 minutes
                relevance_score += 0.8
            elif time_diff.total_seconds() < 900:  # 15 minutes
                relevance_score += 0.4

            # 6. High boost weight entities (previously important)
            if entity.boost_weight > 1.5:
                relevance_score += 0.6

            # 7. Follow-up query patterns
            followup_indicators = ["és", "and", "még", "also", "is", "szintén"]
            if any(indicator in query_lower for indicator in followup_indicators):
                # Boost all recent entities for follow-up queries
                relevance_score += 0.5
                logger.debug(f"Follow-up boost: {entity.entity_id}")

            # Include entity if it has any relevance
            if relevance_score > 0.3:
                relevant_entities.append(
                    {
                        "entity_id": entity.entity_id,
                        "relevance_score": entity.relevance_score,
                        "boost_weight": entity.boost_weight,
                        "area": entity.area,
                        "domain": entity.domain,
                        "context": entity.context,
                        "mentioned_at": entity.mentioned_at.isoformat(),
                        "memory_relevance": relevance_score,
                        "is_from_memory": True,
                        "context_type": entity.context_type,
                    }
                )
                logger.debug(
                    f"Added relevant entity: {entity.entity_id} (memory_relevance={relevance_score:.2f})"
                )

        # Sort by memory relevance combined with boost weight
        relevant_entities.sort(
            key=lambda e: e["memory_relevance"] * e["boost_weight"], reverse=True
        )

        logger.info(
            f"Found {len(relevant_entities)} relevant entities from memory for query: {current_query}"
        )

        return relevant_entities[:max_entities]

    async def update_entity_boost(
        self, conversation_id: str, entity_id: str, boost_multiplier: float
    ) -> bool:
        """Update boost weight for a specific entity in conversation memory."""
        memory = await self.get_conversation_memory(conversation_id)

        if not memory:
            return False

        # Find and update the entity
        updated = False
        for entity in memory.entities:
            if entity.entity_id == entity_id:
                entity.boost_weight *= boost_multiplier
                entity.boost_weight = max(
                    0.1, min(3.0, entity.boost_weight)
                )  # Clamp between 0.1-3.0
                updated = True
                break

        if updated:
            # Re-store the updated memory
            await self.store_conversation_memory(
                conversation_id=conversation_id,
                entities=[
                    {
                        "entity_id": e.entity_id,
                        "rerank_score": e.relevance_score,
                        "area_name": e.area,
                        "domain": e.domain,
                    }
                    for e in memory.entities
                ],
                areas_mentioned=memory.areas_mentioned,
                domains_mentioned=memory.domains_mentioned,
                query_context="boost_update",
            )

        return updated

    async def _cleanup_expired_memory(self, conversation_id: str) -> bool:
        """Clean up expired conversation memory."""
        await self._ensure_connection()

        try:
            collection = self._db.collection("conversation_memory")
            doc_key = f"conv_{conversation_id}_memory"

            if collection.has(doc_key):
                collection.delete(doc_key)
                logger.debug(f"Cleaned up expired memory for {conversation_id}")
                return True

        except Exception as e:
            logger.error(f"Error cleaning up expired memory for {conversation_id}: {e}")

        return False

    async def cleanup_all_expired(self) -> int:
        """Clean up all expired conversation memories. Returns count of cleaned up records."""
        await self._ensure_connection()

        try:
            current_time = datetime.utcnow().isoformat()

            # AQL query to find and delete expired documents
            query = """
            FOR doc IN conversation_memory
                FILTER doc.ttl < @current_time
                REMOVE doc IN conversation_memory
                RETURN OLD
            """

            if self._db is None:
                raise RuntimeError("Database connection not initialized")
            cursor = self._db.aql.execute(
                query, bind_vars={"current_time": current_time}
            )
            deleted_docs = list(cursor)
            count = len(deleted_docs)

            if count > 0:
                logger.info(f"Cleaned up {count} expired conversation memories")

            return count

        except Exception as e:
            logger.error(f"Error during batch cleanup of expired memories: {e}")
            return 0

    async def get_conversation_stats(
        self, conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get statistics about a conversation's memory usage."""
        memory = await self.get_conversation_memory(conversation_id)

        if not memory:
            return None

        return {
            "conversation_id": conversation_id,
            "entity_count": len(memory.entities),
            "areas_count": len(memory.areas_mentioned),
            "domains_count": len(memory.domains_mentioned),
            "query_count": memory.query_count,
            "last_updated": memory.last_updated.isoformat(),
            "ttl": memory.ttl.isoformat(),
            "minutes_remaining": max(
                0, (memory.ttl - datetime.utcnow()).total_seconds() / 60
            ),
            "average_boost_weight": sum(e.boost_weight for e in memory.entities)
            / len(memory.entities),
            "top_areas": list(memory.areas_mentioned),
            "top_domains": list(memory.domains_mentioned),
        }

    async def store_conversation_summary(
        self, session_id: str, summary_data: Dict[str, Any], ttl_minutes: int = 15
    ) -> bool:
        """
        Store conversation summary in memory with TTL

        Args:
            session_id: Session ID for the conversation
            summary_data: Summary data dictionary
            ttl_minutes: TTL in minutes

        Returns:
            True if stored successfully
        """
        await self._ensure_connection()

        try:
            ttl = datetime.utcnow() + timedelta(minutes=ttl_minutes)

            doc = {
                "_key": f"summary_{session_id}",
                "session_id": session_id,
                "summary_data": summary_data,
                "created_at": datetime.utcnow().isoformat(),
                "ttl": ttl.isoformat(),
                "type": "conversation_summary",
            }

            collection = self._db.collection("conversation_memory")
            collection.insert(doc, overwrite=True)

            logger.debug(f"Stored conversation summary for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store conversation summary: {e}")
            return False

    async def get_conversation_summary(
        self, session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached conversation summary if available and not expired

        Args:
            session_id: Session ID for the conversation

        Returns:
            Summary data if available and valid, None otherwise
        """
        await self._ensure_connection()

        try:
            collection = self._db.collection("conversation_memory")
            doc_key = f"summary_{session_id}"

            if collection.has(doc_key):
                doc = collection.get(doc_key)

                # Check TTL
                ttl = datetime.fromisoformat(doc["ttl"].replace("Z", ""))
                if ttl <= datetime.utcnow():
                    # Expired, clean up
                    collection.delete(doc_key)
                    logger.debug(f"Conversation summary expired for {session_id}")
                    return None

                return doc["summary_data"]

            return None

        except Exception as e:
            logger.error(f"Failed to get conversation summary: {e}")
            return None


@dataclass
class EntityContextTracker:
    """Tracks entity importance and patterns across conversation turns"""

    entity_importance: Dict[str, float] = field(default_factory=dict)
    entity_last_accessed: Dict[str, datetime] = field(default_factory=dict)
    entity_mentions: Dict[str, int] = field(default_factory=dict)
    area_patterns: Dict[str, Set[str]] = field(default_factory=dict)
    domain_patterns: Dict[str, Set[str]] = field(default_factory=dict)

    def update_entity(
        self,
        entity_id: str,
        relevance: float,
        area: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> None:
        """Update entity tracking information"""
        current_time = datetime.utcnow()

        # Update importance with exponential moving average
        if entity_id in self.entity_importance:
            self.entity_importance[entity_id] = (
                0.7 * self.entity_importance[entity_id] + 0.3 * relevance
            )
        else:
            self.entity_importance[entity_id] = relevance

        self.entity_last_accessed[entity_id] = current_time
        self.entity_mentions[entity_id] = self.entity_mentions.get(entity_id, 0) + 1

        # Track area patterns
        if area:
            if area not in self.area_patterns:
                self.area_patterns[area] = set()
            self.area_patterns[area].add(entity_id)

        # Track domain patterns
        if domain:
            if domain not in self.domain_patterns:
                self.domain_patterns[domain] = set()
            self.domain_patterns[domain].add(entity_id)

    def get_entity_boost(self, entity_id: str) -> float:
        """Calculate boost factor for entity based on tracking history"""
        if entity_id not in self.entity_importance:
            return 1.0

        # Base importance
        importance = self.entity_importance[entity_id]

        # Frequency boost
        mentions = self.entity_mentions.get(entity_id, 1)
        frequency_boost = min(1.5, 1.0 + (mentions - 1) * 0.2)

        # Recency boost
        last_accessed = self.entity_last_accessed.get(entity_id, datetime.utcnow())
        time_diff = (datetime.utcnow() - last_accessed).total_seconds()
        recency_boost = max(0.5, 1.0 - time_diff / 900)  # 15 minute decay

        return importance * frequency_boost * recency_boost


@dataclass
class QueryExpansionMemory:
    """Learns successful query patterns for better retrieval"""

    successful_patterns: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    query_entity_associations: Dict[str, Set[str]] = field(default_factory=dict)
    expansion_templates: Dict[str, List[str]] = field(default_factory=dict)

    def learn_successful_pattern(
        self, query: str, retrieved_entities: List[str], success_score: float
    ) -> None:
        """Learn from successful retrieval patterns"""
        query_normalized = self._normalize_query(query)

        if query_normalized not in self.successful_patterns:
            self.successful_patterns[query_normalized] = {
                "expanded_terms": set(),
                "boost_entities": set(),
                "success_rate": 0.0,
                "sample_count": 0,
            }

        pattern = self.successful_patterns[query_normalized]

        # Update success rate with moving average
        pattern["sample_count"] += 1
        pattern["success_rate"] = (
            pattern["success_rate"] * (pattern["sample_count"] - 1) + success_score
        ) / pattern["sample_count"]

        # Track successful entities
        pattern["boost_entities"].update(retrieved_entities)

        # Track query-entity associations
        if query_normalized not in self.query_entity_associations:
            self.query_entity_associations[query_normalized] = set()
        self.query_entity_associations[query_normalized].update(retrieved_entities)

    def get_expansion_suggestions(self, query: str) -> Dict[str, Any]:
        """Get expansion suggestions based on learned patterns"""
        query_normalized = self._normalize_query(query)

        suggestions = {"expanded_terms": [], "boost_entities": [], "confidence": 0.0}

        # Look for similar patterns
        for pattern_query, pattern_data in self.successful_patterns.items():
            if self._query_similarity(query_normalized, pattern_query) > 0.6:
                suggestions["expanded_terms"].extend(pattern_data["expanded_terms"])
                suggestions["boost_entities"].extend(pattern_data["boost_entities"])
                suggestions["confidence"] = max(
                    suggestions["confidence"], pattern_data["success_rate"]
                )

        return suggestions

    def _normalize_query(self, query: str) -> str:
        """Normalize query for pattern matching"""
        return query.lower().strip()

    def _query_similarity(self, query1: str, query2: str) -> float:
        """Calculate simple similarity between queries"""
        words1 = set(query1.split())
        words2 = set(query2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)


class AsyncConversationMemory:
    """
    Hybrid conversation memory system with async background processing

    Combines Entity Context Tracking + Query Expansion Memory patterns
    for RAG optimization with fire-and-forget architecture.
    """

    def __init__(self, memory_service: ConversationMemoryService):
        self.memory_service = memory_service

        # Entity tracking (ChatGPT-style)
        self.entity_context = EntityContextTracker()

        # Query learning (RAG-specific pattern)
        self.query_patterns = QueryExpansionMemory()

        # Background processing
        self.background_tasks: Dict[str, asyncio.Task] = {}

        # Cache for quick access
        self._summary_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

    async def process_turn(
        self,
        session_id: str,
        query: str,
        retrieved_entities: List[Dict[str, Any]],
        success_feedback: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Process conversation turn with immediate context updates

        Args:
            session_id: Conversation session ID
            query: User query
            retrieved_entities: Retrieved entities from search
            success_feedback: Success score for learning (0.0-1.0)

        Returns:
            Enhanced context for next turn
        """
        # 1. Update entity context tracking (immediate)
        for entity in retrieved_entities:
            self.entity_context.update_entity(
                entity_id=entity.get("entity_id", ""),
                relevance=entity.get("rerank_score", entity.get("similarity", 0.0)),
                area=entity.get("area_name"),
                domain=entity.get("domain"),
            )

        # 2. Learn query patterns (immediate)
        entity_ids = [e.get("entity_id", "") for e in retrieved_entities]
        self.query_patterns.learn_successful_pattern(
            query=query, retrieved_entities=entity_ids, success_score=success_feedback
        )

        # 3. Store in persistent memory (immediate)
        areas_mentioned = {
            e.get("area_name") for e in retrieved_entities if e.get("area_name")
        }
        domains_mentioned = {
            e.get("domain") for e in retrieved_entities if e.get("domain")
        }

        await self.memory_service.store_conversation_memory(
            conversation_id=session_id,
            entities=retrieved_entities,
            areas_mentioned=areas_mentioned,
            domains_mentioned=domains_mentioned,
            query_context=query,
        )

        # 4. Return enhancement data for immediate use
        return self.get_enhancement_data(session_id, query)

    def get_enhancement_data(self, session_id: str, query: str) -> Dict[str, Any]:
        """
        Get immediate enhancement data for current query

        Args:
            session_id: Session ID
            query: Current query

        Returns:
            Enhancement data with boosts and patterns
        """
        # Entity boosts from tracking
        entity_boosts = {}
        for entity_id, importance in self.entity_context.entity_importance.items():
            boost = self.entity_context.get_entity_boost(entity_id)
            if boost > 1.1:  # Only include significant boosts
                entity_boosts[entity_id] = boost

        # Query expansion suggestions
        expansion_data = self.query_patterns.get_expansion_suggestions(query)

        # Cached summary if available
        cached_summary = self._get_cached_summary(session_id)

        return {
            "entity_boosts": entity_boosts,
            "expansion_suggestions": expansion_data,
            "cached_summary": cached_summary,
            "processing_source": "immediate_context",
            "background_pending": session_id in self.background_tasks,
        }

    def _get_cached_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get cached summary with TTL check"""
        if session_id not in self._summary_cache:
            return None

        timestamp = self._cache_timestamps.get(session_id)
        if not timestamp:
            return None

        # Check 15-minute TTL
        if (datetime.utcnow() - timestamp).total_seconds() > 900:
            self._summary_cache.pop(session_id, None)
            self._cache_timestamps.pop(session_id, None)
            return None

        return self._summary_cache[session_id]

    def cache_summary(self, session_id: str, summary_data: Dict[str, Any]) -> None:
        """Cache summary data with timestamp"""
        self._summary_cache[session_id] = summary_data
        self._cache_timestamps[session_id] = datetime.utcnow()

    async def get_memory_stage_debug_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get debug information for memory stage visualization

        Args:
            session_id: Session ID

        Returns:
            Debug info for pipeline debugger
        """
        # Get conversation memory stats
        memory_stats = await self.memory_service.get_conversation_stats(session_id)

        # Get cached summary info
        cached_summary = self._get_cached_summary(session_id)
        summary_age_ms = 0
        if cached_summary and session_id in self._cache_timestamps:
            age_seconds = (
                datetime.utcnow() - self._cache_timestamps[session_id]
            ).total_seconds()
            summary_age_ms = int(age_seconds * 1000)

        # Get entity context stats
        entity_count = len(self.entity_context.entity_importance)
        active_boosts = {
            entity_id: boost
            for entity_id, boost in [
                (eid, self.entity_context.get_entity_boost(eid))
                for eid in self.entity_context.entity_importance.keys()
            ]
            if boost > 1.1
        }

        # Background task status
        active_task = session_id in self.background_tasks

        return {
            "cache_status": "hit" if cached_summary else "miss",
            "summary_age_ms": summary_age_ms,
            "background_tasks": ["summary_pending"] if active_task else [],
            "entity_boosts": active_boosts,
            "memory_stats": memory_stats,
            "entity_tracking": {
                "tracked_entities": entity_count,
                "area_patterns": len(self.entity_context.area_patterns),
                "domain_patterns": len(self.entity_context.domain_patterns),
            },
            "query_patterns": {
                "learned_patterns": len(self.query_patterns.successful_patterns),
                "entity_associations": len(
                    self.query_patterns.query_entity_associations
                ),
            },
        }
