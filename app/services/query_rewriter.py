"""
Conversational Query Rewriter Service for multi-turn dialogue.

Provides LLM-based query rewriting with coreference resolution
to transform context-dependent queries into standalone searchable queries.

Examples:
    User: "Hány fok van a nappaliban?"
    Assistant: "A nappaliban 22.5 fok van."
    User: "És a kertben?"

    Rewritten: "Hány fok van a kertben?"
"""

import asyncio
import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from ha_rag_bridge.config import get_settings
from ha_rag_bridge.logging import get_logger
from app.schemas import ChatMessage

logger = get_logger(__name__)


@dataclass
class QueryRewriteResult:
    """Result of query rewriting operation."""

    original_query: str
    rewritten_query: str
    confidence: float
    method: str  # "llm", "rule_based", "fallback"
    reasoning: str
    processing_time_ms: int
    coreferences_resolved: List[str]
    intent_inherited: Optional[str] = None


@dataclass
class CoreferenceInfo:
    """Information about resolved coreferences."""

    pronoun: str
    antecedent: str
    confidence: float
    source: str  # "memory", "history", "context"


class ConversationalQueryRewriter:
    """LLM-based conversational query rewriting with coreference resolution."""

    # Few-shot examples for prompt engineering
    FEW_SHOT_EXAMPLES = """
Example 1:
History: User: "Hány fok van a nappaliban?" | Assistant: "A nappaliban 22.5 fok van."
Current: "És a kertben?"
Rewritten: Hány fok van a kertben?

Example 2:
History: User: "Kapcsold fel a világítást a konyhában" | Assistant: "Felkapcsoltam a konyhai lámpákat."
Current: "És a nappaliban is"
Rewritten: Kapcsold fel a világítást a nappaliban is

Example 3:
History: User: "Milyen a páratartalom?" | Assistant: "A páratartalom 65%."
Current: "És mennyi ott a hőmérséklet?"
Rewritten: Mennyi a hőmérséklet?

Example 4:
History: User: "Mi a helyzet a szenzorral?" | Assistant: "A szenzor értéke 25.3."
Current: "És azt ki kapcsolta ki?"
Rewritten: Ki kapcsolta ki a szenzort?

Example 5:
History: User: "Nyisd ki az ablakot" | Assistant: "Megnyitottam az ablakot."
Current: "Most zárd be azt"
Rewritten: Zárd be az ablakot
"""

    # Patterns for follow-up detection
    FOLLOW_UP_PATTERNS = [
        r"\bés\s+(a|az|azt|annak)\b",  # "és a kertben", "és azt"
        r"\bmi\s+(a|az|azt)\b",  # "mi a helyzet"
        r"\b(ott|itt)\b",  # "mennyi ott"
        r"\b(akkor|aztán)\b",  # "akkor mennyi"
        r"\b(szintén|is)\b",  # "nappaliban is"
        r"\b(még|még\s+mi)\b",  # "még mi van"
        r"\b(hogy|hogyan)\s+(van|áll)\b",  # "hogy van"
    ]

    # Pronouns that need resolution
    PRONOUNS = {
        "spatial": ["ott", "itt", "there", "here"],
        "entity": ["az", "azt", "annak", "it", "that", "those"],
        "additive": ["is", "szintén", "also", "too"],
        "demonstrative": ["ez", "ezt", "ennek", "this", "these"],
    }

    def __init__(self):
        """Initialize the query rewriter."""
        self.settings = get_settings()
        self.enabled = self.settings.query_rewriting_enabled
        self.model = self.settings.query_rewriting_model
        self.timeout_ms = self.settings.query_rewriting_timeout_ms
        self.coreference_enabled = self.settings.coreference_resolution_enabled

        logger.info(
            f"QueryRewriter initialized: enabled={self.enabled}, "
            f"model={self.model}, timeout={self.timeout_ms}ms"
        )

    async def rewrite_query(
        self,
        current_query: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        conversation_memory: Optional[Dict[str, Any]] = None,
    ) -> QueryRewriteResult:
        """
        Rewrite a conversational query to be standalone and searchable.

        Args:
            current_query: The current user query that may be context-dependent
            conversation_history: Previous conversation messages
            conversation_memory: Optional conversation memory for context

        Returns:
            QueryRewriteResult with rewritten query and metadata
        """
        start_time = datetime.now()

        # Quick check if rewriting is needed
        if not self.enabled or self.model == "disabled":
            return self._create_fallback_result(
                current_query, "disabled", "Query rewriting is disabled", start_time
            )

        # Check if query needs rewriting
        needs_rewriting = self._needs_rewriting(current_query, conversation_history)
        if not needs_rewriting:
            return self._create_fallback_result(
                current_query,
                "no_rewrite_needed",
                "Query is already standalone",
                start_time,
            )

        try:
            # Try LLM-based rewriting first
            if self.model not in ["disabled", ""]:
                result = await self._llm_rewrite(
                    current_query, conversation_history, conversation_memory
                )
                if result:
                    return result

            # Fallback to rule-based rewriting
            logger.warning("LLM rewriting failed, falling back to rule-based")
            return await self._rule_based_rewrite(
                current_query, conversation_history, start_time
            )

        except Exception as e:
            logger.error(f"Query rewriting failed: {e}", exc_info=True)
            return self._create_fallback_result(
                current_query, "error", f"Rewriting failed: {str(e)}", start_time
            )

    def _needs_rewriting(
        self, query: str, history: Optional[List[ChatMessage]]
    ) -> bool:
        """Check if query needs rewriting based on follow-up patterns."""
        if not history or len(history) == 0:
            return False

        # Check for follow-up patterns
        query_lower = query.lower()
        for pattern in self.FOLLOW_UP_PATTERNS:
            if re.search(pattern, query_lower):
                logger.debug(f"Follow-up pattern detected: {pattern} in '{query}'")
                return True

        # Check for short queries that might be incomplete
        words = query.strip().split()
        if len(words) <= 3:
            # Short queries are likely follow-ups
            return True

        return False

    async def _llm_rewrite(
        self,
        current_query: str,
        conversation_history: Optional[List[ChatMessage]],
        conversation_memory: Optional[Dict[str, Any]],
    ) -> Optional[QueryRewriteResult]:
        """LLM-based query rewriting with few-shot prompting."""
        start_time = datetime.now()

        try:
            # Build the rewriting prompt
            prompt = self._build_rewrite_prompt(current_query, conversation_history)

            # Call LLM (placeholder for actual implementation)
            rewritten = await self._call_llm(prompt)

            if not rewritten or rewritten.strip() == current_query.strip():
                return None

            # Analyze what was resolved
            coreferences = self._detect_resolved_coreferences(
                current_query, rewritten, conversation_history
            )

            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            return QueryRewriteResult(
                original_query=current_query,
                rewritten_query=rewritten.strip(),
                confidence=0.85,  # LLM confidence
                method="llm",
                reasoning=f"LLM ({self.model}) rewriting with coreference resolution",
                processing_time_ms=processing_time,
                coreferences_resolved=[c.pronoun for c in coreferences],
                intent_inherited=self._extract_intent_from_history(
                    conversation_history
                ),
            )

        except asyncio.TimeoutError:
            logger.warning(f"LLM rewriting timeout after {self.timeout_ms}ms")
            return None
        except Exception as e:
            logger.error(f"LLM rewriting error: {e}")
            return None

    def _build_rewrite_prompt(
        self, current_query: str, conversation_history: Optional[List[ChatMessage]]
    ) -> str:
        """Build few-shot prompt for LLM query rewriting."""

        # Format conversation history
        history_str = "No previous context"
        if conversation_history and len(conversation_history) > 0:
            history_parts = []
            for msg in conversation_history[-4:]:  # Last 4 messages
                role = "User" if msg.role == "user" else "Assistant"
                content = msg.content[:100]  # Truncate long messages
                history_parts.append(f'{role}: "{content}"')
            history_str = " | ".join(history_parts)

        prompt = f"""Task: Rewrite conversational queries to be standalone and searchable for a smart home system.

Instructions:
1. Resolve pronouns (ott, az, azt, itt) to their antecedents from conversation history
2. Fill in missing information from context (intent, domain, area)
3. Preserve the user's exact intent and meaning
4. Output ONLY the rewritten query in Hungarian, nothing else
5. If the query is already complete, output it unchanged

{self.FEW_SHOT_EXAMPLES}

Now rewrite this query:
History: {history_str}
Current: "{current_query}"
Rewritten:"""

        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM for query rewriting using LiteLLM with local model support."""
        import asyncio
        
        try:
            import litellm
            
            # Get API configuration from settings
            api_base = getattr(self.settings, 'query_rewriting_api_base', 'http://192.168.1.115:8001/v1')
            api_key = getattr(self.settings, 'query_rewriting_api_key', 'fake-key')
            
            logger.debug(f"Calling LLM rewriter: model={self.model}, api_base={api_base}")
            
            # Create chat completion for query rewriting
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model=f"openai/{self.model}",  # e.g., "openai/home-llama-3b"
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a smart home query rewriter. Rewrite conversational queries to be standalone. Output ONLY the rewritten query in Hungarian, nothing else.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    api_base=api_base,
                    api_key=api_key,
                    max_tokens=100,
                    temperature=0.3,
                    timeout=self.timeout_ms / 1000.0,  # Convert ms to seconds
                ),
                timeout=self.timeout_ms / 1000.0,
            )

            rewritten = response.choices[0].message.content.strip()
            logger.debug(f"LLM rewrite result: '{rewritten}'")

            # Clean up the response (remove quotes, extra text)
            if rewritten.startswith('"') and rewritten.endswith('"'):
                rewritten = rewritten[1:-1]

            # Extract just the query if there's extra text
            lines = rewritten.split("\n")
            for line in lines:
                line = line.strip()
                if line and not line.startswith("Rewritten:") and not line.startswith("Output:"):
                    return line

            return rewritten

        except asyncio.TimeoutError:
            logger.warning(f"LLM rewriting timeout after {self.timeout_ms}ms")
            raise
        except Exception as e:
            logger.error(f"LLM rewriting error: {e}")
            raise

    async def _rule_based_rewrite(
        self,
        current_query: str,
        conversation_history: Optional[List[ChatMessage]],
        start_time: datetime,
    ) -> QueryRewriteResult:
        """Rule-based query rewriting as fallback."""

        rewritten = current_query
        coreferences = []

        if conversation_history and len(conversation_history) > 0:
            # Simple rule-based coreference resolution
            last_user_msg = None
            for msg in reversed(conversation_history):
                if msg.role == "user":
                    last_user_msg = msg.content
                    break

            if last_user_msg:
                # Extract intent from previous query
                intent = self._extract_intent_from_query(last_user_msg)

                # Simple substitution rules
                query_lower = current_query.lower()

                if "és a" in query_lower and intent:
                    # "és a kertben?" → "hány fok van a kertben?"
                    area_match = re.search(r"és\s+a\s+(\w+)", query_lower)
                    if area_match:
                        area = area_match.group(1)
                        rewritten = f"{intent} a {area}?"
                        coreferences.append("és a")

                elif "ott" in query_lower and intent:
                    # "mennyi ott?" → previous intent with area
                    rewritten = f"{intent}?"
                    coreferences.append("ott")

                elif (
                    query_lower.endswith(" is")
                    or " is " in query_lower
                    or "szintén" in query_lower
                ):
                    # "nappaliban is" or "és a fürdőszobában is" → include previous intent
                    if intent:
                        # Clean up the query to remove connective words
                        cleaned_query = (
                            current_query.replace(" is", "")
                            .replace("és a", "")
                            .replace("és", "")
                            .strip()
                        )
                        rewritten = f"{intent} {cleaned_query}"
                        coreferences.append("is")

        processing_time = max(
            1, int((datetime.now() - start_time).total_seconds() * 1000)
        )

        return QueryRewriteResult(
            original_query=current_query,
            rewritten_query=rewritten,
            confidence=0.6,  # Lower confidence for rule-based
            method="rule_based",
            reasoning="Rule-based coreference resolution with pattern matching",
            processing_time_ms=processing_time,
            coreferences_resolved=coreferences,
        )

    def _create_fallback_result(
        self, query: str, method: str, reasoning: str, start_time: datetime
    ) -> QueryRewriteResult:
        """Create fallback result when no rewriting is performed."""
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return QueryRewriteResult(
            original_query=query,
            rewritten_query=query,
            confidence=1.0 if method == "no_rewrite_needed" else 0.0,
            method=method,
            reasoning=reasoning,
            processing_time_ms=processing_time,
            coreferences_resolved=[],
        )

    def _detect_resolved_coreferences(
        self, original: str, rewritten: str, history: Optional[List[ChatMessage]]
    ) -> List[CoreferenceInfo]:
        """Detect what coreferences were resolved in rewriting."""
        coreferences = []

        original_lower = original.lower()
        rewritten_lower = rewritten.lower()

        # Check for resolved pronouns
        for category, pronouns in self.PRONOUNS.items():
            for pronoun in pronouns:
                if pronoun in original_lower and pronoun not in rewritten_lower:
                    # Pronoun was resolved
                    coreferences.append(
                        CoreferenceInfo(
                            pronoun=pronoun,
                            antecedent="resolved",  # Could be more specific
                            confidence=0.8,
                            source="llm",
                        )
                    )

        return coreferences

    def _extract_intent_from_history(
        self, history: Optional[List[ChatMessage]]
    ) -> Optional[str]:
        """Extract intent from conversation history."""
        if not history:
            return None

        # Find the last user message
        for msg in reversed(history):
            if msg.role == "user":
                return self._extract_intent_from_query(msg.content)

        return None

    def _extract_intent_from_query(self, query: str) -> Optional[str]:
        """Extract the main intent from a query."""
        query_lower = query.lower()

        # Common intent patterns
        if any(word in query_lower for word in ["hány", "mennyi", "milyen", "mekkora"]):
            # Question intent
            if "fok" in query_lower or "hőmérséklet" in query_lower:
                return "hány fok van"
            elif "páratartalom" in query_lower or "nedves" in query_lower:
                return "mennyi a páratartalom"
            else:
                return "mennyi"

        elif any(word in query_lower for word in ["kapcsold", "indítsd", "állítsd"]):
            # Control intent
            if "fel" in query_lower or "be" in query_lower:
                return "kapcsold fel"
            elif "le" in query_lower or "ki" in query_lower:
                return "kapcsold le"
            else:
                return "kapcsold"

        # Default: use first few words
        words = query.split()[:3]
        return " ".join(words) if words else None


# Global instance for use across the application
query_rewriter = ConversationalQueryRewriter()
