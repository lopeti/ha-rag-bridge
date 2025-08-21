"""
Conversation Summarizer Service for LLM-based topic tracking and context understanding.

Provides intelligent conversation summarization to understand:
- Main conversation topic and current focus
- Intent patterns and context evolution
- Relevant entities and domains in discussion
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any

from ha_rag_bridge.config import get_settings
from ha_rag_bridge.logging import get_logger
from app.schemas import ChatMessage
from app.services.conversation.conversation_memory import ConversationMemory

logger = get_logger(__name__)


@dataclass
class ConversationSummary:
    """Structured conversation summary with topic and context information."""

    topic: str  # Main conversation topic (e.g., "temperature monitoring")
    current_focus: str  # Current area/entity of focus (e.g., "konyha")
    intent_pattern: str  # Query intent pattern (e.g., "sequential room queries")
    topic_domains: Set[str]  # Relevant domains (e.g., {"sensor", "climate"})
    context_entities: List[str]  # Important entity IDs in context
    confidence: float  # Summary confidence (0.0-1.0)
    focus_history: List[str] = field(default_factory=list)  # Previous focuses
    reasoning: str = ""  # Why this summary was generated

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/transmission."""
        return {
            "topic": self.topic,
            "current_focus": self.current_focus,
            "intent_pattern": self.intent_pattern,
            "topic_domains": list(self.topic_domains),
            "context_entities": self.context_entities,
            "confidence": self.confidence,
            "focus_history": self.focus_history,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSummary":
        """Create from dictionary."""
        return cls(
            topic=data.get("topic", "general"),
            current_focus=data.get("current_focus", ""),
            intent_pattern=data.get("intent_pattern", "read"),
            topic_domains=set(data.get("topic_domains", [])),
            context_entities=data.get("context_entities", []),
            confidence=data.get("confidence", 0.8),
            focus_history=data.get("focus_history", []),
            reasoning=data.get("reasoning", ""),
        )


class ConversationSummarizer:
    """LLM-based conversation summarization service."""

    # Enhanced prompt template for better Hungarian understanding
    SUMMARY_PROMPT_TEMPLATE = """
Elemezd ezt a beszélgetést és készíts strukturált összefoglalót.

### Beszélgetés történet:
{history}

### Jelenlegi kérdés:
{query}

### Korábbi memória (ha van):
Területek: {areas}
Domainek: {domains}
Entitások: {entities}

### Feladat:
Készíts JSON összefoglalót ezekkel a mezőkkel:

1. **topic**: Fő téma (pl. "temperature monitoring", "light control", "home overview")
2. **current_focus**: Jelenlegi terület/aspektus (pl. "konyha", "nappali", "")
3. **intent_pattern**: Kérdés minta (pl. "sequential room queries", "device control", "status check")
4. **topic_domains**: Releváns domainek (pl. ["sensor"], ["light", "switch"])
5. **context_entities**: Fontos entity ID-k (pl. ["sensor.konyha_temperature"])

### Szabályok:
- Ha hőmérsékletről kérdez → topic: "temperature monitoring"
- Ha világításról → topic: "light control"  
- Ha általános állapotról → topic: "home overview"
- Ha "és a [hely]ben?" minta → intent_pattern: "sequential room queries"
- current_focus: területnév magyar nevével (konyha, nappali, hálószoba, stb.)

### Válasz JSON formátumban:
"""

    # Fallback patterns for rule-based summarization
    TOPIC_PATTERNS = {
        "temperature": ["fok", "hőmérséklet", "meleg", "hideg", "temperature"],
        "light": ["lámpa", "világítás", "fény", "kapcsol", "light", "switch"],
        "climate": ["klíma", "fűtés", "hűtés", "páratartalom", "climate", "humidity"],
        "security": ["riasztó", "ajtó", "ablak", "security", "alarm", "door"],
        "energy": ["áram", "energia", "fogyasztás", "napelem", "energy", "power"],
    }

    INTENT_PATTERNS = {
        "sequential_rooms": [r"és\s+a\s+\w+ban", r"és\s+a\s+\w+ben", r"és\s+ott"],
        "device_control": ["kapcsold", "állítsd", "indítsd", "kapcsolj", "turn", "set"],
        "status_check": ["mi van", "milyen", "mennyi", "hány", "what", "how much"],
        "home_overview": [
            "helyzet",
            "állapot",
            "minden",
            "otthon",
            "overview",
            "status",
        ],
    }

    def __init__(self):
        """Initialize the conversation summarizer."""
        self.settings = get_settings()
        self.enabled = self.settings.conversation_summary_enabled
        self.model = self.settings.conversation_summary_model

        logger.info(
            f"ConversationSummarizer initialized: enabled={self.enabled}, model={self.model}"
        )

    async def generate_summary(
        self,
        query: str,
        history: List[ChatMessage],
        memory: Optional[ConversationMemory] = None,
    ) -> ConversationSummary:
        """
        Generate conversation summary using LLM with fallback to rule-based.

        Args:
            query: Current user query
            history: Previous conversation messages
            memory: Optional existing conversation memory

        Returns:
            ConversationSummary with topic and context information
        """
        if not self.enabled or self.model == "disabled":
            return self._create_fallback_summary(query, history, memory)

        try:
            # Try LLM-based summarization first
            llm_summary = await self._llm_summarize(query, history, memory)
            if llm_summary:
                logger.debug(f"LLM summarization successful: {llm_summary.topic}")
                return llm_summary

        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}")

        # Fallback to rule-based summarization
        logger.info("Falling back to rule-based conversation summarization")
        return self._create_fallback_summary(query, history, memory)

    async def _llm_summarize(
        self,
        query: str,
        history: List[ChatMessage],
        memory: Optional[ConversationMemory],
    ) -> Optional[ConversationSummary]:
        """LLM-based conversation summarization."""

        try:
            import litellm

            # Build the prompt
            prompt = self._build_summary_prompt(query, history, memory)

            # Get API configuration
            api_base = getattr(
                self.settings,
                "query_rewriting_api_base",
                "http://192.168.1.115:8001/v1",
            )
            api_key = getattr(self.settings, "query_rewriting_api_key", "fake-key")

            logger.debug(
                f"Calling LLM summarizer: model={self.model}, api_base={api_base}"
            )

            # Call local LLM
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model=f"openai/{self.model}",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a smart home conversation analyzer. Analyze conversations and generate JSON summaries. Output ONLY valid JSON, nothing else.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    api_base=api_base,
                    api_key=api_key,
                    max_tokens=200,
                    temperature=0.3,
                    timeout=2.0,  # 2 second timeout for summarization
                ),
                timeout=2.5,
            )

            content = response.choices[0].message.content.strip()
            logger.debug(f"LLM summary response: {content[:100]}...")

            # Parse JSON response
            try:
                summary_data = json.loads(content)
                return ConversationSummary(
                    topic=summary_data.get("topic", "general"),
                    current_focus=summary_data.get("current_focus", ""),
                    intent_pattern=summary_data.get("intent_pattern", "read"),
                    topic_domains=set(summary_data.get("topic_domains", [])),
                    context_entities=summary_data.get("context_entities", []),
                    confidence=0.85,  # LLM confidence
                    reasoning=f"LLM-based analysis with {self.model}",
                )

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM summary JSON: {e}")
                # Try to extract JSON from response if it has extra text
                json_match = self._extract_json_from_text(content)
                if json_match:
                    summary_data = json.loads(json_match)
                    return ConversationSummary(
                        topic=summary_data.get("topic", "general"),
                        current_focus=summary_data.get("current_focus", ""),
                        intent_pattern=summary_data.get("intent_pattern", "read"),
                        topic_domains=set(summary_data.get("topic_domains", [])),
                        context_entities=summary_data.get("context_entities", []),
                        confidence=0.8,
                        reasoning="LLM-based analysis (JSON extracted)",
                    )
                return None

        except asyncio.TimeoutError:
            logger.warning("LLM summarization timeout")
            return None
        except Exception as e:
            logger.error(f"LLM summarization error: {e}")
            return None

    def _build_summary_prompt(
        self,
        query: str,
        history: List[ChatMessage],
        memory: Optional[ConversationMemory],
    ) -> str:
        """Build the summarization prompt."""

        # Format conversation history
        history_str = "Nincs korábbi beszélgetés"
        if history and len(history) > 0:
            history_parts = []
            for msg in history[-6:]:  # Last 6 messages for context
                role = "Felhasználó" if msg.role == "user" else "Asszisztens"
                content = msg.content[:150]  # Truncate long messages
                history_parts.append(f'{role}: "{content}"')
            history_str = "\n".join(history_parts)

        # Format memory information
        areas = memory.areas_mentioned if memory else set()
        domains = memory.domains_mentioned if memory else set()
        entities = [e.entity_id for e in memory.entities[:5]] if memory else []

        return self.SUMMARY_PROMPT_TEMPLATE.format(
            history=history_str,
            query=query,
            areas=list(areas),
            domains=list(domains),
            entities=entities,
        )

    def _create_fallback_summary(
        self,
        query: str,
        history: List[ChatMessage],
        memory: Optional[ConversationMemory],
    ) -> ConversationSummary:
        """Create summary using rule-based patterns."""

        query_lower = query.lower()

        # Detect topic from patterns
        detected_topic = "general"
        topic_domains = set()

        for topic, patterns in self.TOPIC_PATTERNS.items():
            if any(pattern in query_lower for pattern in patterns):
                detected_topic = f"{topic} monitoring"
                if topic == "temperature":
                    topic_domains = {"sensor", "climate"}
                elif topic == "light":
                    topic_domains = {"light", "switch"}
                elif topic == "climate":
                    topic_domains = {"climate", "sensor"}
                elif topic == "security":
                    topic_domains = {"binary_sensor", "sensor"}
                elif topic == "energy":
                    topic_domains = {"sensor"}
                break

        # Detect intent pattern
        intent_pattern = "read"  # Default
        for intent, patterns in self.INTENT_PATTERNS.items():
            if any(re.search(pattern, query_lower) for pattern in patterns):
                intent_pattern = intent
                break

        # Extract current focus (area) from query
        current_focus = ""
        area_patterns = {
            "konyha": ["konyha", "konyhában", "konyhába"],
            "nappali": ["nappali", "nappaliban", "nappaliba"],
            "hálószoba": ["hálószoba", "hálóban", "hálóba", "háló"],
            "fürdőszoba": ["fürdőszoba", "fürdőben", "fürdőbe", "fürdő"],
            "kert": ["kert", "kertben", "kertbe", "kerti"],
            "garage": ["garázs", "garázsban"],
            "pince": ["pince", "pincében"],
            "dolgozószoba": ["dolgozószoba", "dolgozóban", "iroda"],
        }

        for area, patterns in area_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                current_focus = area
                break

        # Get context entities from memory if available
        context_entities = []
        if memory and memory.entities:
            # Get entities that match the current topic/focus
            for entity in memory.entities[:5]:
                if current_focus and current_focus in entity.entity_id.lower():
                    context_entities.append(entity.entity_id)
                elif any(domain in entity.entity_id for domain in topic_domains):
                    context_entities.append(entity.entity_id)

        return ConversationSummary(
            topic=detected_topic,
            current_focus=current_focus,
            intent_pattern=intent_pattern,
            topic_domains=topic_domains,
            context_entities=context_entities,
            confidence=0.7,  # Rule-based confidence
            reasoning="Rule-based pattern matching",
        )

    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """Extract JSON from text that might have extra content."""
        import re

        # Try to find JSON object in the text
        json_pattern = r"\{[^}]*\}"
        matches = re.findall(json_pattern, text, re.DOTALL)

        for match in matches:
            try:
                # Test if it's valid JSON
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue

        return None
