"""
Conversation analyzer service for context-aware entity prioritization.
Handles Hungarian language processing, area detection, and conversation context analysis.
"""

import os
import re
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from cachetools import TTLCache  # type: ignore

from ha_rag_bridge.logging import get_logger
from ha_rag_bridge.config import get_settings
from app.schemas import ChatMessage

logger = get_logger(__name__)


@dataclass
class ConversationContext:
    """Extracted conversation context information."""

    areas_mentioned: Set[str]
    domains_mentioned: Set[str]
    device_classes_mentioned: Set[str]
    previous_entities: Set[str]
    is_follow_up: bool
    intent: str
    confidence: float = 0.8  # Default confidence for compatibility


class ConversationAnalyzer:
    """Analyzes conversation context for better entity prioritization."""

    settings = get_settings()

    # Cache for dynamically loaded aliases
    _aliases_cache = TTLCache(
        maxsize=settings.conversation_cache_maxsize,
        ttl=settings.conversation_aliases_ttl,
    )

    # Hungarian area detection patterns with aliases (base patterns)
    AREA_PATTERNS = {
        "kert": [
            "kert",
            "kerti",
            "kertben",
            "kertből",
            "kertnek",
            "kertet",
            "garden",
            "kint",
            "kinn",
            "outside",
            "outdoor",
            "külső",
            "udvar",
            "udvari",
        ],
        "nappali": ["nappali", "nappaliban", "nappaliba", "nappalit", "living room"],
        "konyha": ["konyha", "konyhában", "konyhába", "konyhát", "kitchen"],
        "hálószoba": ["hálószoba", "hálóban", "hálóba", "hálót", "háló", "bedroom"],
        "fürdőszoba": [
            "fürdőszoba",
            "fürdőben",
            "fürdőbe",
            "fürdőt",
            "fürdő",
            "bathroom",
        ],
        "dolgozószoba": [
            "dolgozószoba",
            "dolgozóban",
            "dolgozóba",
            "dolgozót",
            "iroda",
            "office",
        ],
        "előszoba": ["előszoba", "előszobában", "bejárat", "hall", "hallway"],
        "pince": ["pince", "pincében", "pincébe", "basement"],
        "padlás": ["padlás", "padláson", "padlásra", "attic"],
        "terasz": ["terasz", "teraszon", "teraszra", "erkély", "terrace", "balcony"],
        "garázs": ["garázs", "garázsban", "garage"],
        "ház": [
            "ház",
            "házban",
            "házbó",
            "otthon",
            "benn",
            "bent",
            "house",
            "home",
            "inside",
            "indoor",
            "belső",
        ],
    }

    # Hungarian domain/device class patterns
    DOMAIN_PATTERNS = {
        "sensor": {
            "temperature": ["hőmérséklet", "fok", "meleg", "hideg", "temperature"],
            "humidity": ["nedveség", "páratartalom", "humid"],
            "illuminance": ["fény", "világítás", "lux", "light"],
            "motion": ["mozgás", "motion", "jelenl"],
            "door": ["ajtó", "door"],
            "window": ["ablak", "window"],
            "energy": ["energia", "áram", "watt", "energy", "power"],
            "air_quality": ["levegő", "co2", "air"],
        },
        "light": ["világítás", "lámpa", "light", "lamp", "kapcsold"],
        "switch": ["kapcsoló", "switch", "kapcsold"],
        "climate": ["klíma", "fűtés", "heating", "cooling", "thermostat"],
        "cover": ["redőny", "függöny", "blind", "curtain", "cover"],
        "lock": ["zár", "lock", "kulcs"],
        "alarm": ["riasztó", "alarm", "security"],
    }

    # Intent detection patterns
    CONTROL_PATTERNS = [
        r"\b(kapcsold|indítsd|állítsd|turn\s+on|turn\s+off|nyisd|zárd)\b",
        r"\b(fel|le|be|ki|on|off)\b",
    ]

    READ_PATTERNS = [
        r"\b(mennyi|hány|milyen|mekkora|mi|what|how)\b",
        r"\b(fok|temperature|status|állapot|érték)\b",
    ]

    FOLLOW_UP_PATTERNS = [
        r"\b(és\s+a|mi\s+a|what\s+about|how\s+about)\b",
        r"\b(ott|itt|there|here)\b",
        r"\b(akkor|then|so)\b",
    ]

    def __init__(self):
        """Initialize the conversation analyzer."""
        self._compile_patterns()
        self._load_dynamic_aliases()

    def _compile_patterns(self):
        """Compile regex patterns for better performance."""
        self.control_re = re.compile("|".join(self.CONTROL_PATTERNS), re.IGNORECASE)
        self.read_re = re.compile("|".join(self.READ_PATTERNS), re.IGNORECASE)
        self.follow_up_re = re.compile("|".join(self.FOLLOW_UP_PATTERNS), re.IGNORECASE)

    def _load_dynamic_aliases(self):
        """Load entity aliases from database and merge with static patterns."""
        cache_key = "area_aliases"

        if cache_key in self._aliases_cache:
            self.dynamic_area_patterns = self._aliases_cache[cache_key]
            return

        try:
            from arango import ArangoClient

            # Initialize database connection
            arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
            db = arango.db(
                os.getenv("ARANGO_DB", "_system"),
                username=os.environ["ARANGO_USER"],
                password=os.environ["ARANGO_PASS"],
            )

            # Query for entities with aliases
            cursor = db.aql.execute(
                """
                FOR e IN entity 
                FILTER e.text LIKE '%Aliases:%' AND e.area != null
                RETURN {
                    area: e.area,
                    text: e.text
                }
            """
            )

            # Start with base patterns
            dynamic_patterns = {}
            for area, patterns in self.AREA_PATTERNS.items():
                dynamic_patterns[area] = list(patterns)  # Copy base patterns

            # Add aliases from database
            for entity in cursor:
                area = entity["area"]
                text = entity["text"]

                if "Aliases:" in text:
                    aliases_part = text.split("Aliases:")[-1].strip()
                    if aliases_part:
                        # Split aliases by space and add them
                        aliases = [
                            alias.strip()
                            for alias in aliases_part.split()
                            if alias.strip()
                        ]

                        # Ensure area exists in patterns
                        if area not in dynamic_patterns:
                            dynamic_patterns[area] = []

                        # Add unique aliases
                        for alias in aliases:
                            if alias not in dynamic_patterns[area]:
                                dynamic_patterns[area].append(alias)
                                logger.debug(f"Added alias '{alias}' for area '{area}'")

            self.dynamic_area_patterns = dynamic_patterns
            self._aliases_cache[cache_key] = dynamic_patterns

            logger.info(f"Loaded dynamic aliases for {len(dynamic_patterns)} areas")

        except Exception as exc:
            logger.warning(f"Failed to load dynamic aliases: {exc}")
            # Fallback to static patterns
            self.dynamic_area_patterns = dict(self.AREA_PATTERNS)

    def analyze_conversation(
        self,
        current_message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
    ) -> ConversationContext:
        """
        Analyze conversation context and extract relevant information.

        Args:
            current_message: The current user message
            conversation_history: Previous conversation messages

        Returns:
            ConversationContext with extracted information
        """
        logger.debug(f"Analyzing conversation: {current_message}")

        # Extract areas from current message
        areas_mentioned = self._extract_areas(current_message)

        # Extract domains and device classes
        domains_mentioned, device_classes_mentioned = self._extract_domains_and_classes(
            current_message
        )

        # Check if this is a follow-up question
        is_follow_up = self._detect_follow_up(current_message)

        # Extract previous entities from conversation history
        previous_entities = self._extract_previous_entities(conversation_history)

        # If follow-up and no explicit area, inherit from previous context
        if is_follow_up and not areas_mentioned and conversation_history:
            areas_mentioned = self._extract_areas_from_history(conversation_history)

        # Detect intent
        intent = self._detect_intent(current_message)

        context = ConversationContext(
            areas_mentioned=areas_mentioned,
            domains_mentioned=domains_mentioned,
            device_classes_mentioned=device_classes_mentioned,
            previous_entities=previous_entities,
            is_follow_up=is_follow_up,
            intent=intent,
        )

        logger.debug(f"Extracted context: {context}")
        return context

    def _extract_areas(self, text: str) -> Set[str]:
        """Extract area mentions from text using Hungarian patterns and dynamic aliases."""
        areas = set()
        text_lower = text.lower()

        # Use dynamic patterns that include database aliases
        patterns_to_use = getattr(self, "dynamic_area_patterns", self.AREA_PATTERNS)

        for area, patterns in patterns_to_use.items():
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    areas.add(area)
                    logger.debug(f"Found area '{area}' from pattern '{pattern}'")

        return areas

    def _extract_domains_and_classes(self, text: str) -> Tuple[Set[str], Set[str]]:
        """Extract domain and device class mentions from text."""
        domains = set()
        device_classes = set()
        text_lower = text.lower()

        for domain, patterns in self.DOMAIN_PATTERNS.items():
            if isinstance(patterns, dict):
                # Sensor domain with device classes
                for device_class, class_patterns in patterns.items():
                    for pattern in class_patterns:
                        if pattern in text_lower:
                            domains.add(domain)
                            device_classes.add(device_class)
                            logger.debug(
                                f"Found domain '{domain}' and class '{device_class}' from pattern '{pattern}'"
                            )
            else:
                # Simple domain patterns
                for pattern in patterns:
                    if pattern in text_lower:
                        domains.add(domain)
                        logger.debug(
                            f"Found domain '{domain}' from pattern '{pattern}'"
                        )

        return domains, device_classes

    def _detect_follow_up(self, text: str) -> bool:
        """Detect if this is a follow-up question."""
        return bool(self.follow_up_re.search(text))

    def _extract_previous_entities(
        self, history: Optional[List[ChatMessage]]
    ) -> Set[str]:
        """Extract entity IDs mentioned in previous conversation turns."""
        entities: Set[str] = set()

        if not history:
            return entities

        # Look for entity_id patterns in system messages (our responses)
        for message in history[-5:]:  # Last 5 messages for performance
            # Handle both dict and object formats for compatibility
            role = (
                message.get("role")
                if isinstance(message, dict)
                else getattr(message, "role", None)
            )
            content = (
                message.get("content")
                if isinstance(message, dict)
                else getattr(message, "content", "")
            )

            if role == "system" and "Relevant entities:" in content:
                # Extract entity IDs from system prompts
                lines = content.split("\n")
                for line in lines:
                    if line.startswith("Relevant entities:"):
                        entity_part = line.replace("Relevant entities:", "").strip()
                        # Split by comma and clean up
                        for entity_id in entity_part.split(","):
                            clean_id = entity_id.strip()
                            if clean_id and "." in clean_id:  # Valid entity_id format
                                entities.add(clean_id)

        return entities

    def _extract_areas_from_history(self, history: List[ChatMessage]) -> Set[str]:
        """Extract areas from conversation history for follow-up questions."""
        areas = set()

        # Look at recent user messages for area context
        for message in reversed(history[-3:]):  # Last 3 messages
            # Handle both dict and object formats for compatibility
            role = (
                message.get("role")
                if isinstance(message, dict)
                else getattr(message, "role", None)
            )
            content = (
                message.get("content")
                if isinstance(message, dict)
                else getattr(message, "content", "")
            )

            if role == "user":
                areas.update(self._extract_areas(content))
                if areas:  # Found areas in recent history
                    break

        return areas

    def _detect_intent(self, text: str) -> str:
        """Detect user intent (control vs read)."""
        if self.control_re.search(text):
            return "control"
        else:
            return "read"  # Default to read intent

    def get_area_boost_factors(self, context: ConversationContext) -> Dict[str, float]:
        """
        Get boost factors for entities based on area context.

        Args:
            context: Analyzed conversation context

        Returns:
            Dictionary mapping area names to boost factors
        """
        boost_factors = {}

        # Higher boost for explicitly mentioned areas (using config values)
        from ha_rag_bridge.config import get_settings

        settings = get_settings()

        for area in context.areas_mentioned:
            if area == "ház":  # Generic house reference
                boost_factors[area] = settings.ranking_area_generic_boost
            else:  # Specific area
                boost_factors[area] = settings.ranking_area_specific_boost

        # Special handling for follow-up questions
        if context.is_follow_up and context.areas_mentioned:
            # Boost all mentioned areas more for follow-ups
            multiplier = settings.ranking_area_followup_multiplier
            for area in context.areas_mentioned:
                boost_factors[area] = boost_factors.get(area, 1.0) * multiplier

        return boost_factors

    def get_domain_boost_factors(
        self, context: ConversationContext
    ) -> Dict[str, float]:
        """
        Get boost factors for entities based on domain/device class context.

        Args:
            context: Analyzed conversation context

        Returns:
            Dictionary mapping domains/device_classes to boost factors
        """
        boost_factors = {}

        # Get config values
        from ha_rag_bridge.config import get_settings

        settings = get_settings()

        # Boost mentioned domains
        for domain in context.domains_mentioned:
            boost_factors[f"domain:{domain}"] = settings.ranking_domain_boost

        # Higher boost for specific device classes
        for device_class in context.device_classes_mentioned:
            boost_factors[f"device_class:{device_class}"] = (
                settings.ranking_device_class_boost
            )

        return boost_factors


# Global instance for reuse
conversation_analyzer = ConversationAnalyzer()
