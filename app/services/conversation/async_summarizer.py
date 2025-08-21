"""
Async Conversation Summarizer Service

Background conversation summarization with fire-and-forget architecture
to eliminate blocking LLM delays while providing progressive enhancement
for multi-turn conversations.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from datetime import datetime

import litellm
from ha_rag_bridge.config import get_settings
from app.services.conversation.conversation_memory import ConversationMemoryService


logger = logging.getLogger(__name__)


@dataclass
class ConversationMetaSummary:
    """Structured meta-information for conversation optimization"""

    session_id: str
    turn_count: int
    timestamp: datetime

    # Domain/cluster context
    detected_domains: List[str]
    active_clusters: List[str]
    entity_patterns: List[str]

    # Spatial and temporal context
    mentioned_areas: List[str]
    area_transitions: List[str]
    temporal_context: Optional[str]

    # Entity relevance scoring
    high_relevance_entities: Dict[str, float]

    # Query patterns
    query_types: List[str]
    intent_chain: List[str]

    # User preferences learned
    language_preference: str
    detail_level: str
    recurring_patterns: List[str]

    # Processing metadata
    processing_time_ms: int
    llm_used: bool
    cache_key: str


@dataclass
class QuickPatterns:
    """Fast rule-based pattern extraction results"""

    domains: Set[str]
    areas: Set[str]
    entity_patterns: Set[str]
    query_type: str
    language: str
    processing_time_ms: int


class AsyncSummarizer:
    """Background conversation summarization service with smart caching"""

    def __init__(self, memory_service: ConversationMemoryService):
        self.settings = get_settings()
        self.memory_service = memory_service

        # Background task queue
        self.background_queue: asyncio.Queue = asyncio.Queue()
        self.active_tasks: Dict[str, asyncio.Task] = {}

        # Domain and area patterns for quick extraction
        self.domain_keywords = {
            "temperature": {
                "hőmérséklet",
                "fok",
                "meleg",
                "hideg",
                "temperature",
                "temp",
            },
            "humidity": {"páratartalom", "nedvesség", "humidity", "humid"},
            "lighting": {"lámpa", "világítás", "fény", "light", "lamp", "illuminate"},
            "energy": {"energia", "fogyasztás", "termelés", "energy", "power", "watt"},
            "security": {"biztonság", "riasztó", "security", "alarm", "lock"},
            "climate": {"klíma", "fűtés", "hűtés", "climate", "heat", "cool"},
        }

        self.area_keywords = {
            "nappali",
            "living",
            "szoba",
            "room",
            "konyha",
            "kitchen",
            "hálószoba",
            "bedroom",
            "fürdő",
            "bathroom",
            "kert",
            "garden",
            "étkező",
            "dining",
            "iroda",
            "office",
            "garázs",
            "garage",
        }

        # Start background worker
        self._start_background_worker()

    def _start_background_worker(self) -> None:
        """Start background task processing worker"""
        asyncio.create_task(self._process_background_queue())

    async def _process_background_queue(self) -> None:
        """Process background summarization tasks"""
        while True:
            try:
                task_data = await self.background_queue.get()
                session_id = task_data["session_id"]

                # Avoid duplicate processing
                if session_id in self.active_tasks:
                    continue

                # Create and track task
                task = asyncio.create_task(
                    self._generate_background_summary_internal(task_data)
                )
                self.active_tasks[session_id] = task

                # Clean up completed task
                try:
                    await task
                finally:
                    self.active_tasks.pop(session_id, None)

            except Exception as e:
                logger.error(f"Background queue processing error: {e}")
                await asyncio.sleep(1)

    def extract_quick_patterns(
        self, query: str, history: List[Dict[str, Any]]
    ) -> QuickPatterns:
        """
        Fast rule-based pattern extraction (<50ms)

        Args:
            query: Current user query
            history: Conversation history

        Returns:
            QuickPatterns with basic context information
        """
        start_time = time.time()

        # Combine query and recent history for analysis
        text_content = query.lower()
        if history:
            # Only look at last 3 turns for quick analysis
            recent_history = history[-3:]
            for turn in recent_history:
                if "user_message" in turn:
                    text_content += " " + turn["user_message"].lower()

        # Extract domains
        domains = set()
        for domain, keywords in self.domain_keywords.items():
            if any(keyword in text_content for keyword in keywords):
                domains.add(domain)

        # Extract areas
        areas = set()
        for area_keyword in self.area_keywords:
            if area_keyword in text_content:
                areas.add(area_keyword)

        # Extract entity patterns (basic)
        entity_patterns = set()
        if domains:
            for domain in domains:
                entity_patterns.add(f"*{domain}*")
        if areas:
            for area in areas:
                entity_patterns.add(f"*{area}*")

        # Detect query type
        query_type = "unknown"
        if any(word in query.lower() for word in ["hány", "mennyi", "how", "what"]):
            query_type = "status_check"
        elif any(
            word in query.lower() for word in ["kapcsold", "állítsd", "turn", "set"]
        ):
            query_type = "control"
        elif any(word in query.lower() for word in ["mi", "what", "helyzet", "status"]):
            query_type = "overview"

        # Detect language
        hungarian_words = {"hány", "mennyi", "kapcsold", "állítsd", "fok", "lámpa"}
        english_words = {"how", "what", "turn", "set", "temperature", "light"}

        hu_count = sum(1 for word in hungarian_words if word in text_content)
        en_count = sum(1 for word in english_words if word in text_content)

        language = "hungarian" if hu_count >= en_count else "english"

        processing_time = int((time.time() - start_time) * 1000)

        return QuickPatterns(
            domains=domains,
            areas=areas,
            entity_patterns=entity_patterns,
            query_type=query_type,
            language=language,
            processing_time_ms=processing_time,
        )

    def should_generate_summary(self, history: List[Dict[str, Any]]) -> bool:
        """
        Determine if LLM summary generation should be triggered.
        Now generates summary from first turn for immediate meta-information extraction.

        Args:
            history: Conversation history (can be empty for first turn)

        Returns:
            True if summary should be generated
        """
        # Skip if disabled in settings
        if not self.settings.conversation_summary_enabled:
            return False

        # Skip if model is disabled
        if self.settings.conversation_summary_model == "disabled":
            return False

        # Generate summary from first turn onwards for immediate context building
        return True

    async def request_background_summary(
        self,
        session_id: str,
        query: str,
        history: List[Dict[str, Any]],
        retrieved_entities: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Request background summary generation (fire-and-forget)

        Args:
            session_id: Conversation session ID
            query: Current user query
            history: Conversation history
            retrieved_entities: Retrieved entities for context
        """
        if not self.should_generate_summary(history):
            return

        # Add to background queue
        task_data = {
            "session_id": session_id,
            "query": query,
            "history": history,
            "retrieved_entities": retrieved_entities or [],
            "timestamp": datetime.utcnow(),
        }

        try:
            await self.background_queue.put(task_data)
            logger.debug(f"Queued background summary for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to queue background summary: {e}")

    async def _generate_background_summary_internal(
        self, task_data: Dict[str, Any]
    ) -> None:
        """
        Internal background summary generation

        Args:
            task_data: Task data from queue
        """
        start_time = time.time()
        session_id = task_data["session_id"]

        try:
            # Generate summary using LLM
            summary = await self._generate_llm_summary(
                session_id=session_id,
                query=task_data["query"],
                history=task_data["history"],
                retrieved_entities=task_data["retrieved_entities"],
            )

            # Cache the summary
            await self._cache_summary(session_id, summary)

            processing_time = int((time.time() - start_time) * 1000)
            logger.info(
                f"Background summary generated for {session_id} in {processing_time}ms"
            )

        except Exception as e:
            logger.error(f"Background summary generation failed for {session_id}: {e}")

    async def _generate_llm_summary(
        self,
        session_id: str,
        query: str,
        history: List[Dict[str, Any]],
        retrieved_entities: List[Dict[str, Any]],
    ) -> ConversationMetaSummary:
        """
        Generate meta-summary using LLM

        Args:
            session_id: Conversation session ID
            query: Current user query
            history: Conversation history
            retrieved_entities: Retrieved entities

        Returns:
            ConversationMetaSummary with structured meta-information
        """
        start_time = time.time()

        # Build conversation context
        conversation_text = self._build_conversation_context(query, history)
        entity_context = self._build_entity_context(retrieved_entities)

        # LLM prompt for meta-information extraction
        prompt = f"""
Analyze this smart home conversation and extract META-INFORMATION for future query optimization:

CONVERSATION:
{conversation_text}

ENTITIES RETRIEVED:
{entity_context}

Extract the following structured information (respond in JSON format):

1. DOMAINS (max 3): Which smart home domains are discussed?
   Options: temperature, humidity, lighting, security, solar, climate, energy
   
2. ENTITY_PATTERNS (max 5): Which entity ID patterns are relevant?
   Example: ["sensor.*temperature", "light.*nappali", "switch.*kert"]
   
3. MENTIONED_AREAS (max 5): Which areas/rooms are mentioned?
   Hungarian names: ["nappali", "konyha", "hálószoba", "kert"]
   
4. AREA_TRANSITIONS: How does focus move between areas?
   Example: ["nappali→kert", "konyha→étkező"]
   
5. HIGH_RELEVANCE_ENTITIES: Which specific entities are most important?
   Example: {{"sensor.nappali_temperature": 0.95, "light.kert": 0.8}}
   
6. QUERY_TYPES: What types of queries appear?
   Options: status_check, control, comparison, overview
   
7. INTENT_CHAIN: How do intents connect across turns?
   Example: ["check", "compare", "control"]
   
8. TEMPORAL_CONTEXT: Time-based patterns?
   Options: morning_routine, evening_check, weekend_monitoring, none
   
9. RECURRING_PATTERNS: What patterns appear multiple times?
   Example: ["energy_monitoring", "lighting_control", "temperature_tracking"]

Respond with JSON containing these fields for VECTOR SEARCH optimization.
"""

        try:
            # Debug log the prompt being sent to LLM
            logger.info(
                f"🤖 LLM prompt for session {session_id} (first 200 chars): {prompt[:200]}..."
            )

            # Call LLM with timeout and loop prevention metadata
            timeout_seconds = self.settings.conversation_summary_timeout / 1000.0
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model=self.settings.conversation_summary_model,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=timeout_seconds,
                    temperature=0.1,
                    # Add metadata to prevent hook interference (loop prevention)
                    metadata={
                        "internal_call": True,
                        "purpose": "conversation_summary",
                        "session_id": session_id,
                    },
                    # For local models, add API base and key
                    **self._get_model_config(),
                ),
                timeout=timeout_seconds + 1.0,
            )

            # Parse LLM response
            llm_response_text = response.choices[0].message.content
            logger.info(
                f"🤖 LLM response for session {session_id} (first 300 chars): {llm_response_text[:300]}..."
            )

            summary_data = self._parse_llm_response(llm_response_text)

            # Build final summary
            processing_time = int((time.time() - start_time) * 1000)
            logger.info(
                f"✅ LLM summary successful for {session_id}: domains={summary_data.get('domains', [])}, processing_time={processing_time}ms"
            )

            summary = ConversationMetaSummary(
                session_id=session_id,
                turn_count=len(history) + 1,
                timestamp=datetime.utcnow(),
                detected_domains=summary_data.get("domains", []),
                active_clusters=summary_data.get(
                    "domains", []
                ),  # Use domains as clusters
                entity_patterns=summary_data.get("entity_patterns", []),
                mentioned_areas=summary_data.get("mentioned_areas", []),
                area_transitions=summary_data.get("area_transitions", []),
                temporal_context=summary_data.get("temporal_context"),
                high_relevance_entities=summary_data.get("high_relevance_entities", {}),
                query_types=summary_data.get("query_types", []),
                intent_chain=summary_data.get("intent_chain", []),
                language_preference="hungarian",  # Default for our system
                detail_level="concise",  # Default preference
                recurring_patterns=summary_data.get("recurring_patterns", []),
                processing_time_ms=processing_time,
                llm_used=True,
                cache_key=f"summary_{session_id}_{int(time.time())}",
            )

            return summary

        except asyncio.TimeoutError:
            logger.warning(f"LLM summary timeout for session {session_id}")
            return self._create_fallback_summary(session_id, query, history)
        except Exception as e:
            logger.error(f"LLM summary generation error: {e}")
            return self._create_fallback_summary(session_id, query, history)

    def _build_conversation_context(
        self, query: str, history: List[Dict[str, Any]]
    ) -> str:
        """Build conversation context for LLM analysis"""
        context_lines = []

        # Handle case with conversation history
        if history:
            # Add recent history (last 5 turns)
            recent_history = history[-5:] if len(history) > 5 else history

            for i, turn in enumerate(recent_history):
                if "user_message" in turn:
                    context_lines.append(f"Turn {i+1}: {turn['user_message']}")
                if "assistant_message" in turn:
                    context_lines.append(
                        f"Assistant {i+1}: {turn['assistant_message'][:100]}..."
                    )

        # Add current query
        context_lines.append(f"Current: {query}")

        # If no history, indicate this is the first interaction
        if not history:
            context_lines.insert(0, "[First interaction]")

        return "\n".join(context_lines)

    def _build_entity_context(self, entities: List[Dict[str, Any]]) -> str:
        """Build entity context for LLM analysis"""
        if not entities:
            return "No entities retrieved"

        entity_lines = []
        for entity in entities[:10]:  # Limit to top 10
            entity_id = entity.get("entity_id", "unknown")
            entity_type = entity_id.split(".")[0] if "." in entity_id else "unknown"
            entity_lines.append(f"- {entity_id} ({entity_type})")

        return "\n".join(entity_lines)

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM JSON response with fallback"""
        try:
            import json

            # Try to extract JSON from response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                return json.loads(json_text)
            else:
                logger.warning("No JSON found in LLM response")
                return {}
        except Exception as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return {}

    def _create_fallback_summary(
        self, session_id: str, query: str, history: List[Dict[str, Any]]
    ) -> ConversationMetaSummary:
        """Create fallback summary using rule-based extraction"""
        quick_patterns = self.extract_quick_patterns(query, history)

        # Create fallback summary with debug logging
        summary = ConversationMetaSummary(
            session_id=session_id,
            turn_count=len(history) + 1,
            timestamp=datetime.utcnow(),
            detected_domains=list(quick_patterns.domains),
            active_clusters=list(quick_patterns.domains),
            entity_patterns=list(quick_patterns.entity_patterns),
            mentioned_areas=list(quick_patterns.areas),
            area_transitions=[],
            temporal_context=None,
            high_relevance_entities={},
            query_types=[quick_patterns.query_type],
            intent_chain=[quick_patterns.query_type],
            language_preference=quick_patterns.language,
            detail_level="concise",
            recurring_patterns=[],
            processing_time_ms=quick_patterns.processing_time_ms,
            llm_used=False,
            cache_key=f"fallback_{session_id}_{int(time.time())}",
        )

        # Debug log the fallback summary quality
        logger.info(
            f"🔄 Fallback summary generated: domains={quick_patterns.domains}, areas={quick_patterns.areas}, patterns={quick_patterns.entity_patterns}, query_type={quick_patterns.query_type}"
        )

        return summary

    async def _cache_summary(
        self, session_id: str, summary: ConversationMetaSummary
    ) -> None:
        """Cache summary in conversation memory with TTL"""
        try:
            # Convert to dict and ensure JSON serializable
            summary_dict = asdict(summary)
            # Convert datetime to ISO string
            summary_dict["timestamp"] = summary.timestamp.isoformat()

            # Store as conversation memory entry
            await self.memory_service.store_conversation_summary(
                session_id=session_id,
                summary_data=summary_dict,
                ttl_minutes=15,  # 15-minute cache
            )

            logger.debug(f"Cached summary for session {session_id}")

        except Exception as e:
            logger.error(f"Failed to cache summary: {e}")

    async def get_cached_summary(
        self, session_id: str
    ) -> Optional[ConversationMetaSummary]:
        """
        Get cached summary if available and not expired

        Args:
            session_id: Conversation session ID

        Returns:
            ConversationMetaSummary if cached and valid, None otherwise
        """
        try:
            cached_data = await self.memory_service.get_conversation_summary(session_id)

            if cached_data:
                # Check if summary is still valid (not expired)
                summary = ConversationMetaSummary(**cached_data)
                age_minutes = (
                    datetime.utcnow() - summary.timestamp
                ).total_seconds() / 60

                if age_minutes < 15:  # 15-minute TTL
                    return summary
                else:
                    logger.debug(f"Cached summary expired for session {session_id}")

            return None

        except Exception as e:
            logger.error(f"Failed to get cached summary: {e}")
            return None

    async def get_active_task_count(self) -> int:
        """Get number of active background tasks"""
        return len(self.active_tasks)

    async def get_queue_size(self) -> int:
        """Get background queue size"""
        return self.background_queue.qsize()

    def _get_model_config(self) -> Dict[str, Any]:
        """
        Get model-specific configuration for API calls.

        Returns:
            Dictionary with api_base and api_key for local models, empty for cloud models
        """
        model = self.settings.conversation_summary_model

        # Local models need custom API base and key + custom_llm_provider
        if model in ["home-llama-3b", "qwen-7b"]:
            return {
                "api_base": self.settings.conversation_summary_api_base,
                "api_key": self.settings.conversation_summary_api_key,
                "custom_llm_provider": "openai",  # Tell LiteLLM to use OpenAI-compatible format
            }

        # Cloud models use their respective API keys from litellm
        elif model.startswith("gpt-"):
            # OpenAI models use OPENAI_API_KEY from environment
            return {}
        elif model.startswith("gemini-"):
            # Gemini models use GEMINI_API_KEY from environment
            return {}

        # Default: no special configuration
        return {}
