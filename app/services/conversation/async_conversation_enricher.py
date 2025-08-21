"""
Async Conversation Enricher Service

Fire-and-forget háttérfeldolgozó, amely következő körre készít részletes kontextust.
Szétválasztva a QuickPatternAnalyzer gyors elemzésétől.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

import litellm
from ha_rag_bridge.config import get_settings
from ha_rag_bridge.logging import get_logger
from app.services.conversation.conversation_memory import ConversationMemoryService

logger = get_logger(__name__)


@dataclass
class EnrichedContext:
    """LLM által gazdagított kontextus következő körre"""

    session_id: str
    timestamp: datetime

    # Részletes elemzés
    detected_domains: List[str]
    mentioned_areas: List[str]
    entity_relationships: Dict[str, float]
    intent_chain: List[str]
    semantic_context: str

    # User profiling
    user_patterns: Dict[str, Any]
    language_preference: str
    interaction_style: str

    # Next-turn optimization
    expected_followups: List[str]
    entity_boost_weights: Dict[str, float]
    suggested_clusters: List[str]

    # Processing metadata
    llm_model_used: str
    processing_time_ms: int
    confidence_score: float
    cache_key: str


class AsyncConversationEnricher:
    """
    Aszinkron konverzáció gazdagító szolgáltatás

    Felelősség:
    - Háttérben futó LLM-alapú részletes elemzés
    - Következő kör optimalizálása
    - Pattern learning és user profiling
    - Cache-be mentés TTL-lel

    NEM felelős:
    - Gyors válaszért (az QuickPatternAnalyzer feladata)
    - Szinkron működésért
    - Blokkoló hívásokért
    """

    def __init__(self, memory_service: ConversationMemoryService):
        self.settings = get_settings()
        self.memory_service = memory_service

        # Background task queue
        self.background_queue: asyncio.Queue = asyncio.Queue()
        self.active_tasks: Dict[str, asyncio.Task] = {}

        # Start background worker
        self._start_background_worker()

        logger.info("AsyncConversationEnricher initialized")

    def _start_background_worker(self) -> None:
        """Háttér feldolgozó indítása"""
        asyncio.create_task(self._process_background_queue())
        logger.debug("Background worker started")

    async def _process_background_queue(self) -> None:
        """Háttér task queue feldolgozása"""
        while True:
            try:
                task_data = await self.background_queue.get()
                session_id = task_data["session_id"]

                # Avoid duplicate processing
                if (
                    session_id in self.active_tasks
                    and not self.active_tasks[session_id].done()
                ):
                    logger.debug(
                        f"Enrichment already in progress for session {session_id}"
                    )
                    continue

                # Create and track task
                task = asyncio.create_task(
                    self._enrich_conversation_internal(task_data)
                )
                self.active_tasks[session_id] = task

                # Clean up completed task (but don't await it)
                def cleanup_task(completed_task):
                    self.active_tasks.pop(session_id, None)
                    if completed_task.exception():
                        logger.error(
                            f"Background enrichment failed for {session_id}: {completed_task.exception()}"
                        )

                task.add_done_callback(cleanup_task)

            except Exception as e:
                logger.error(f"Background queue processing error: {e}")
                await asyncio.sleep(1)

    async def enrich_async(
        self,
        session_id: str,
        query: str,
        history: List[Dict[str, Any]],
        retrieved_entities: Optional[List[Dict[str, Any]]] = None,
        quick_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Aszinkron enrichment indítása (fire-and-forget)

        Args:
            session_id: Session azonosító
            query: Aktuális felhasználó lekérdezés
            history: Beszélgetés történet
            retrieved_entities: Lekért entitások (opcionális)
            quick_context: Gyors elemzés eredménye (opcionális)
        """

        # Skip if disabled
        if not self.settings.query_processing_enabled:
            logger.debug("Query processing disabled, skipping enrichment")
            return

        # Skip if model is disabled
        if self.settings.query_processing_model == "disabled":
            logger.debug("Query processing model disabled, skipping enrichment")
            return

        # Queue the enrichment task
        task_data = {
            "session_id": session_id,
            "query": query,
            "history": history,
            "retrieved_entities": retrieved_entities or [],
            "quick_context": quick_context or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            await self.background_queue.put(task_data)
            logger.debug(f"Queued background enrichment for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to queue background enrichment: {e}")

    async def _enrich_conversation_internal(self, task_data: Dict[str, Any]) -> None:
        """
        Belső enrichment végrehajtás

        Args:
            task_data: Task adatok a queue-ból
        """
        start_time = time.time()
        session_id = task_data["session_id"]

        try:
            logger.info(f"Starting background enrichment for session {session_id}")

            # Generate enriched context using LLM
            enriched_context = await self._generate_llm_enrichment(
                session_id=session_id,
                query=task_data["query"],
                history=task_data["history"],
                retrieved_entities=task_data["retrieved_entities"],
                quick_context=task_data["quick_context"],
            )

            # Cache the enriched context
            await self._cache_enriched_context(session_id, enriched_context)

            # Update pattern learning
            await self._update_pattern_learning(enriched_context)

            processing_time = int((time.time() - start_time) * 1000)
            logger.info(
                f"Background enrichment completed for {session_id} in {processing_time}ms"
            )

        except Exception as e:
            logger.error(f"Background enrichment failed for {session_id}: {e}")

    async def _generate_llm_enrichment(
        self,
        session_id: str,
        query: str,
        history: List[Dict[str, Any]],
        retrieved_entities: List[Dict[str, Any]],
        quick_context: Dict[str, Any],
    ) -> EnrichedContext:
        """
        LLM-alapú részletes kontextus generálás

        Args:
            session_id: Session azonosító
            query: Aktuális lekérdezés
            history: Beszélgetés történet
            retrieved_entities: Lekért entitások
            quick_context: Gyors elemzés eredménye

        Returns:
            EnrichedContext a következő körre
        """
        start_time = time.time()

        # Build context for LLM
        conversation_text = self._build_conversation_context(query, history)
        entity_context = self._build_entity_context(retrieved_entities)
        quick_analysis = json.dumps(quick_context, indent=2, ensure_ascii=False)

        # LLM prompt for detailed analysis
        prompt = f"""
Analyze this smart home conversation for NEXT-TURN OPTIMIZATION:

CURRENT QUERY: {query}

CONVERSATION HISTORY:
{conversation_text}

RETRIEVED ENTITIES:
{entity_context}

QUICK ANALYSIS RESULTS:
{quick_analysis}

Extract detailed meta-information for optimizing the NEXT query in this conversation:

1. DETECTED_DOMAINS (max 5): Which smart home domains are relevant?
   Options: temperature, humidity, lighting, security, solar, climate, energy, media, network

2. MENTIONED_AREAS (max 5): Which areas/rooms are mentioned or implied?
   Include: explicit mentions + contextual implications

3. ENTITY_RELATIONSHIPS: Which entities relate to each other? 
   Format: {{"entity_id": relevance_score_0_to_1}}

4. INTENT_CHAIN: How do intents connect across conversation turns?
   Example: ["status_check", "comparison", "control"]

5. SEMANTIC_CONTEXT: One sentence summary of conversation context

6. USER_PATTERNS: What patterns emerge about user behavior?
   Consider: language preference, detail level, common areas, time patterns

7. EXPECTED_FOLLOWUPS: What questions might come next? (max 3)
   Examples: ["És a másik szobában?", "Kapcsold le", "Mi van a kertben?"]

8. ENTITY_BOOST_WEIGHTS: Which entities should be boosted for next turn?
   Format: {{"entity_id": boost_multiplier}}

9. SUGGESTED_CLUSTERS: Which semantic clusters are relevant?
   Options: climate, lighting, security, solar, overview

Respond in JSON format optimized for NEXT-TURN entity retrieval enhancement.
"""

        try:
            # Call LLM with timeout and metadata to prevent loops
            timeout_seconds = self.settings.query_processing_timeout / 1000.0
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model=self.settings.query_processing_model,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=timeout_seconds,
                    temperature=0.1,
                    # Metadata to prevent hook interference
                    metadata={
                        "internal_call": True,
                        "purpose": "conversation_enrichment",
                        "session_id": session_id,
                    },
                    # Model-specific configuration
                    **self._get_model_config(),
                ),
                timeout=timeout_seconds + 1.0,
            )

            # Parse LLM response
            llm_response_text = response.choices[0].message.content
            logger.debug(
                f"LLM enrichment response for {session_id}: {llm_response_text[:200]}..."
            )

            enrichment_data = self._parse_llm_response(llm_response_text)

            # Build enriched context
            processing_time = int((time.time() - start_time) * 1000)

            enriched_context = EnrichedContext(
                session_id=session_id,
                timestamp=datetime.utcnow(),
                detected_domains=enrichment_data.get("detected_domains", []),
                mentioned_areas=enrichment_data.get("mentioned_areas", []),
                entity_relationships=enrichment_data.get("entity_relationships", {}),
                intent_chain=enrichment_data.get("intent_chain", []),
                semantic_context=enrichment_data.get("semantic_context", ""),
                user_patterns=enrichment_data.get("user_patterns", {}),
                language_preference=enrichment_data.get(
                    "language_preference", "hungarian"
                ),
                interaction_style=enrichment_data.get("interaction_style", "concise"),
                expected_followups=enrichment_data.get("expected_followups", []),
                entity_boost_weights=enrichment_data.get("entity_boost_weights", {}),
                suggested_clusters=enrichment_data.get("suggested_clusters", []),
                llm_model_used=self.settings.query_processing_model,
                processing_time_ms=processing_time,
                confidence_score=self._calculate_enrichment_confidence(enrichment_data),
                cache_key=f"enriched_{session_id}_{int(time.time())}",
            )

            logger.info(
                f"LLM enrichment successful for {session_id}: domains={enriched_context.detected_domains}"
            )
            return enriched_context

        except asyncio.TimeoutError:
            logger.warning(f"LLM enrichment timeout for session {session_id}")
            return self._create_fallback_enrichment(session_id, query, quick_context)
        except Exception as e:
            logger.error(f"LLM enrichment error for {session_id}: {e}")
            return self._create_fallback_enrichment(session_id, query, quick_context)

    def _build_conversation_context(
        self, query: str, history: List[Dict[str, Any]]
    ) -> str:
        """Beszélgetés kontextus építése LLM számára"""
        context_lines = []

        if history:
            # Only recent history for enrichment (last 5 turns)
            recent_history = history[-5:] if len(history) > 5 else history

            for i, turn in enumerate(recent_history):
                if isinstance(turn, dict):
                    if "user_message" in turn:
                        context_lines.append(f"User {i+1}: {turn['user_message']}")
                    elif "content" in turn and turn.get("role") == "user":
                        context_lines.append(f"User {i+1}: {turn['content']}")

                    if "assistant_message" in turn:
                        # Truncate long assistant responses
                        assistant_msg = (
                            turn["assistant_message"][:150] + "..."
                            if len(turn["assistant_message"]) > 150
                            else turn["assistant_message"]
                        )
                        context_lines.append(f"Assistant {i+1}: {assistant_msg}")

        # Add current query
        context_lines.append(f"Current: {query}")

        if not history:
            context_lines.insert(0, "[First interaction]")

        return "\n".join(context_lines)

    def _build_entity_context(self, entities: List[Dict[str, Any]]) -> str:
        """Entitás kontextus építése"""
        if not entities:
            return "No entities retrieved"

        entity_lines = []
        for entity in entities[:8]:  # Limit for LLM context
            entity_id = entity.get("entity_id", "unknown")
            area = entity.get("area_name", "")
            domain = entity_id.split(".")[0] if "." in entity_id else "unknown"

            line = f"- {entity_id} ({domain}"
            if area:
                line += f", {area}"
            line += ")"

            entity_lines.append(line)

        return "\n".join(entity_lines)

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """LLM válasz JSON parsing fallback-kel"""
        try:
            # Try to extract JSON from response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                return json.loads(json_text)
            else:
                logger.warning("No JSON found in LLM enrichment response")
                return {}
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM enrichment response as JSON: {e}")
            return {}

    def _calculate_enrichment_confidence(
        self, enrichment_data: Dict[str, Any]
    ) -> float:
        """Enrichment konfidencia számítás"""
        confidence = 0.0

        # Base confidence from data completeness
        if enrichment_data.get("detected_domains"):
            confidence += 0.2
        if enrichment_data.get("mentioned_areas"):
            confidence += 0.2
        if enrichment_data.get("intent_chain"):
            confidence += 0.2
        if enrichment_data.get("semantic_context"):
            confidence += 0.2
        if enrichment_data.get("expected_followups"):
            confidence += 0.2

        return min(confidence, 1.0)

    def _create_fallback_enrichment(
        self, session_id: str, query: str, quick_context: Dict[str, Any]
    ) -> EnrichedContext:
        """Fallback enrichment LLM hiba esetén"""

        return EnrichedContext(
            session_id=session_id,
            timestamp=datetime.utcnow(),
            detected_domains=quick_context.get("detected_domains", []),
            mentioned_areas=quick_context.get("detected_areas", []),
            entity_relationships={},
            intent_chain=[quick_context.get("query_type", "unknown")],
            semantic_context=f"Fallback context for query: {query[:50]}...",
            user_patterns={},
            language_preference=quick_context.get("language", "hungarian"),
            interaction_style="concise",
            expected_followups=[],
            entity_boost_weights={},
            suggested_clusters=[],
            llm_model_used="fallback",
            processing_time_ms=0,
            confidence_score=0.3,
            cache_key=f"fallback_{session_id}_{int(time.time())}",
        )

    async def _cache_enriched_context(
        self, session_id: str, context: EnrichedContext
    ) -> None:
        """Cache enriched context with TTL"""
        try:
            # Convert to dict for storage
            context_dict = asdict(context)
            context_dict["timestamp"] = context.timestamp.isoformat()

            # Store with 15-minute TTL
            await self.memory_service.store_conversation_summary(
                session_id=session_id, summary_data=context_dict, ttl_minutes=15
            )

            logger.debug(f"Cached enriched context for session {session_id}")

        except Exception as e:
            logger.error(f"Failed to cache enriched context: {e}")

    async def _update_pattern_learning(self, context: EnrichedContext) -> None:
        """Update pattern learning from enriched context"""
        try:
            # TODO: Implement pattern learning updates
            # This will interact with the PatternService when it's ready
            logger.debug(
                f"Pattern learning update for session {context.session_id} (placeholder)"
            )

        except Exception as e:
            logger.error(f"Pattern learning update failed: {e}")

    async def get_cached_enrichment(self, session_id: str) -> Optional[EnrichedContext]:
        """
        Cached enrichment lekérése

        Args:
            session_id: Session azonosító

        Returns:
            EnrichedContext ha van cache-elt és érvényes, None egyébként
        """
        try:
            cached_data = await self.memory_service.get_conversation_summary(session_id)

            if cached_data and "timestamp" in cached_data:
                # Convert back from dict
                if isinstance(cached_data["timestamp"], str):
                    cached_data["timestamp"] = datetime.fromisoformat(
                        cached_data["timestamp"]
                    )

                context = EnrichedContext(**cached_data)

                # Check if still valid (15-minute TTL)
                age_minutes = (
                    datetime.utcnow() - context.timestamp
                ).total_seconds() / 60
                if age_minutes < 15:
                    logger.debug(f"Using cached enrichment for session {session_id}")
                    return context
                else:
                    logger.debug(f"Cached enrichment expired for session {session_id}")

            return None

        except Exception as e:
            logger.error(f"Failed to get cached enrichment: {e}")
            return None

    def _get_model_config(self) -> Dict[str, Any]:
        """
        Model-specifikus konfiguráció API hívásokhoz

        Returns:
            Dictionary API base és key konfigurációval
        """
        # Local models need custom API base and key
        if self.settings.query_processing_api_base:
            return {
                "api_base": self.settings.query_processing_api_base,
                "api_key": self.settings.query_processing_api_key or "local-key",
                "custom_llm_provider": "openai",
            }

        # Cloud models use environment variables
        return {}

    async def get_active_task_count(self) -> int:
        """Aktív background task-ok száma"""
        return len([task for task in self.active_tasks.values() if not task.done()])

    async def get_queue_size(self) -> int:
        """Background queue mérete"""
        return self.background_queue.qsize()
