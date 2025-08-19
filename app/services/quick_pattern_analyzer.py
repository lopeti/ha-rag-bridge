"""
Quick Pattern Analyzer Service

Szinkron, gyors (<50ms) pattern felismerés minden RAG előtt.
Szétválasztja a gyors elemzést a lassú async summarization-től.
"""

import time
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass

from ha_rag_bridge.config import get_settings
from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QuickContext:
    """Gyors pattern elemzés eredménye"""

    # Alapvető kontextus
    detected_domains: Set[str]
    detected_areas: Set[str]
    query_type: str
    language: str
    confidence: float

    # Entitás pattern-ek
    entity_patterns: Set[str]
    suggested_entity_types: Set[str]

    # Metrika
    processing_time_ms: int
    pattern_matches: int

    # Debug info
    matched_keywords: Dict[str, List[str]]
    source: str = "quick_analysis"


class QuickPatternAnalyzer:
    """
    Gyors, szinkron pattern elemző szolgáltatás

    Felelősség:
    - Gyors nyelv detektálás
    - Domain/area/intent azonosítás
    - Entitás pattern javaslatok
    - <50ms válaszidő garantálva

    NEM felelős:
    - LLM-alapú elemzésért (az AsyncConversationEnricher feladata)
    - Hosszú távú tanulásért
    - Komplex kontextus építésért
    """

    def __init__(self):
        self.settings = get_settings()

        # TODO: Ezek majd a PatternService-ből jönnek
        # Egyelőre átmeneti megoldás a hardkódolt pattern-ök helyett
        self._init_temporary_patterns()

        logger.info("QuickPatternAnalyzer initialized")

    def _init_temporary_patterns(self) -> None:
        """Átmeneti pattern-ök inicializálása (majd PatternService váltja fel)"""

        # Domain detection patterns
        self.domain_patterns = {
            "temperature": {
                "hu": {"hőmérséklet", "fok", "meleg", "hideg", "forró", "langyos"},
                "en": {
                    "temperature",
                    "temp",
                    "degrees",
                    "hot",
                    "cold",
                    "warm",
                    "celsius",
                    "fahrenheit",
                },
            },
            "humidity": {
                "hu": {"páratartalom", "nedvesség", "párás", "száraz"},
                "en": {"humidity", "humid", "moisture", "damp", "dry"},
            },
            "lighting": {
                "hu": {
                    "lámpa",
                    "világítás",
                    "fény",
                    "felkapcsol",
                    "lekapcsol",
                    "kapcsol",
                    "villanykörte",
                },
                "en": {
                    "light",
                    "lamp",
                    "illuminate",
                    "bright",
                    "dim",
                    "turn on",
                    "turn off",
                    "switch",
                },
            },
            "energy": {
                "hu": {
                    "energia",
                    "fogyasztás",
                    "termelés",
                    "áram",
                    "napelem",
                    "solar",
                    "watt",
                    "kilowatt",
                },
                "en": {
                    "energy",
                    "power",
                    "consumption",
                    "production",
                    "solar",
                    "electricity",
                    "watt",
                    "kilowatt",
                },
            },
            "security": {
                "hu": {
                    "biztonság",
                    "riasztó",
                    "zár",
                    "kulcs",
                    "mozgás",
                    "nyitva",
                    "zárva",
                },
                "en": {
                    "security",
                    "alarm",
                    "lock",
                    "key",
                    "motion",
                    "open",
                    "closed",
                    "door",
                    "window",
                },
            },
            "climate": {
                "hu": {
                    "klíma",
                    "fűtés",
                    "hűtés",
                    "légkondicionáló",
                    "radiátor",
                    "termosztát",
                },
                "en": {
                    "climate",
                    "heating",
                    "cooling",
                    "hvac",
                    "air conditioning",
                    "radiator",
                    "thermostat",
                },
            },
        }

        # Area detection patterns
        self.area_patterns = {
            "hu": {
                "nappali": {"nappali", "living", "szoba", "előszoba"},
                "konyha": {"konyha", "kitchen", "étkezde"},
                "hálószoba": {"hálószoba", "háló", "bedroom", "alvószoba"},
                "fürdőszoba": {"fürdőszoba", "fürdő", "bathroom", "mosdó", "wc"},
                "kert": {
                    "kert",
                    "garden",
                    "terasz",
                    "balkon",
                    "udvar",
                    "kinti",
                    "kültér",
                },
                "étkező": {"étkező", "dining", "ebédlő"},
                "iroda": {"iroda", "office", "dolgozószoba", "munkaszoba"},
                "garázs": {"garázs", "garage", "műhely"},
                "pince": {"pince", "basement", "alagsor"},
                "padlás": {"padlás", "attic", "tetőtér"},
            },
            "en": {
                "living_room": {"living", "room", "lounge", "sitting"},
                "kitchen": {"kitchen", "dining", "cook"},
                "bedroom": {"bedroom", "bed", "sleep"},
                "bathroom": {"bathroom", "bath", "shower", "toilet"},
                "garden": {"garden", "yard", "outdoor", "outside", "patio"},
                "office": {"office", "study", "work"},
                "garage": {"garage", "workshop"},
                "basement": {"basement", "cellar"},
                "attic": {"attic", "loft"},
            },
        }

        # Query type patterns
        self.query_type_patterns = {
            "status_check": {
                "hu": {"hány", "mennyi", "milyen", "hogyan", "mi", "mekkora", "van-e"},
                "en": {"how", "what", "which", "is", "are", "many", "much", "any"},
            },
            "control": {
                "hu": {
                    "kapcsold",
                    "állítsd",
                    "indítsd",
                    "állítsd le",
                    "nyisd",
                    "zárd",
                    "emelj",
                    "csökkentsd",
                },
                "en": {
                    "turn",
                    "set",
                    "start",
                    "stop",
                    "open",
                    "close",
                    "increase",
                    "decrease",
                    "switch",
                },
            },
            "overview": {
                "hu": {
                    "helyzet",
                    "összefoglaló",
                    "minden",
                    "összes",
                    "mindenhol",
                    "átfogó",
                },
                "en": {
                    "overview",
                    "summary",
                    "all",
                    "everything",
                    "everywhere",
                    "status",
                },
            },
            "comparison": {
                "hu": {
                    "több",
                    "kevesebb",
                    "nagyobb",
                    "kisebb",
                    "jobb",
                    "rosszabb",
                    "különbség",
                },
                "en": {
                    "more",
                    "less",
                    "higher",
                    "lower",
                    "better",
                    "worse",
                    "difference",
                    "compare",
                },
            },
        }

    def analyze(
        self, query: str, history: Optional[List[Dict[str, Any]]] = None
    ) -> QuickContext:
        """
        Gyors pattern elemzés végrehajtása

        Args:
            query: Felhasználó lekérdezése
            history: Opcionális beszélgetés történet (utolsó 3 fordulót veszi csak figyelembe)

        Returns:
            QuickContext az azonosított pattern-ökkel
        """
        start_time = time.time()

        # Prepare text for analysis
        text_content = query.lower().strip()
        if history:
            # Csak az utolsó 3 fordulót nézzük a gyors elemzéshez
            recent_history = history[-3:] if len(history) > 3 else history
            for turn in recent_history:
                if isinstance(turn, dict):
                    if "user_message" in turn:
                        text_content += " " + turn["user_message"].lower()
                    elif "content" in turn and turn.get("role") == "user":
                        text_content += " " + turn["content"].lower()

        # 1. Language detection
        detected_language = self._detect_language(text_content)

        # 2. Domain detection
        detected_domains = self._detect_domains(text_content, detected_language)

        # 3. Area detection
        detected_areas = self._detect_areas(text_content, detected_language)

        # 4. Query type detection
        query_type = self._detect_query_type(query.lower(), detected_language)

        # 5. Generate entity patterns
        entity_patterns, suggested_types = self._generate_entity_patterns(
            detected_domains, detected_areas, query_type
        )

        # 6. Calculate confidence
        confidence = self._calculate_confidence(
            detected_domains, detected_areas, query_type, detected_language
        )

        # 7. Collect matched keywords for debugging
        matched_keywords = self._collect_matched_keywords(
            text_content, detected_language, detected_domains, detected_areas
        )

        processing_time = int((time.time() - start_time) * 1000)

        # Ensure we meet the <50ms promise
        if processing_time > 50:
            logger.warning(
                f"QuickPatternAnalyzer exceeded 50ms limit: {processing_time}ms"
            )

        result = QuickContext(
            detected_domains=detected_domains,
            detected_areas=detected_areas,
            query_type=query_type,
            language=detected_language,
            confidence=confidence,
            entity_patterns=entity_patterns,
            suggested_entity_types=suggested_types,
            processing_time_ms=processing_time,
            pattern_matches=len(matched_keywords),
            matched_keywords=matched_keywords,
        )

        logger.debug(
            f"Quick analysis completed in {processing_time}ms: domains={detected_domains}, areas={detected_areas}, type={query_type}"
        )

        return result

    def _detect_language(self, text: str) -> str:
        """Gyors nyelv detektálás"""

        # Hungarian-specific characters and patterns
        hu_indicators = {"ő", "ű", "ö", "ü", "é", "á", "í", "ó", "ú"}
        hu_words = {
            "hány",
            "mennyi",
            "van",
            "hogy",
            "mit",
            "hol",
            "mikor",
            "miért",
            "kapcsold",
            "állítsd",
        }

        # English indicators
        en_words = {
            "how",
            "what",
            "where",
            "when",
            "why",
            "turn",
            "set",
            "is",
            "are",
            "the",
            "and",
        }

        # Count indicators
        hu_score = 0
        en_score = 0

        # Character-based scoring
        for char in text:
            if char in hu_indicators:
                hu_score += 2

        # Word-based scoring
        words = text.lower().split()
        for word in words:
            if word in hu_words:
                hu_score += 3
            if word in en_words:
                en_score += 1

        # Decision with fallback
        if hu_score > en_score:
            return "hu"
        elif en_score > hu_score:
            return "en"
        else:
            # Fallback to user preference or default
            return getattr(self.settings, "primary_language", "hu")

    def _detect_domains(self, text: str, language: str) -> Set[str]:
        """Domain pattern-ök detektálása"""
        detected = set()

        for domain, lang_patterns in self.domain_patterns.items():
            if language in lang_patterns:
                keywords = lang_patterns[language]
                if any(keyword in text for keyword in keywords):
                    detected.add(domain)

        return detected

    def _detect_areas(self, text: str, language: str) -> Set[str]:
        """Terület pattern-ök detektálása"""
        detected = set()

        if language in self.area_patterns:
            area_dict = self.area_patterns[language]
            for area_name, keywords in area_dict.items():
                if any(keyword in text for keyword in keywords):
                    detected.add(area_name)

        return detected

    def _detect_query_type(self, query: str, language: str) -> str:
        """Query típus detektálása"""

        for query_type, lang_patterns in self.query_type_patterns.items():
            if language in lang_patterns:
                keywords = lang_patterns[language]
                if any(keyword in query for keyword in keywords):
                    return query_type

        return "unknown"

    def _generate_entity_patterns(
        self, domains: Set[str], areas: Set[str], query_type: str
    ) -> tuple[Set[str], Set[str]]:
        """Entitás pattern-ök és típus javaslatok generálása"""

        entity_patterns = set()
        suggested_types = set()

        # Domain-based patterns
        domain_to_patterns = {
            "temperature": ["sensor.*temp*", "sensor.*homerseklet*", "climate.*"],
            "humidity": ["sensor.*humidity*", "sensor.*paratartalom*"],
            "lighting": ["light.*", "switch.*lamp*", "switch.*lampa*"],
            "energy": [
                "sensor.*power*",
                "sensor.*energy*",
                "sensor.*solar*",
                "sensor.*napelem*",
            ],
            "security": [
                "binary_sensor.*door*",
                "binary_sensor.*window*",
                "lock.*",
                "alarm.*",
            ],
            "climate": ["climate.*", "sensor.*temp*", "fan.*"],
        }

        for domain in domains:
            if domain in domain_to_patterns:
                entity_patterns.update(domain_to_patterns[domain])

        # Area-based patterns
        for area in areas:
            entity_patterns.add(f"*{area}*")

        # Query type-based entity types
        type_to_entities = {
            "status_check": {"sensor"},
            "control": {"switch", "light", "climate", "cover", "fan"},
            "overview": {"sensor", "light", "switch", "climate"},
            "comparison": {"sensor"},
        }

        if query_type in type_to_entities:
            suggested_types.update(type_to_entities[query_type])

        return entity_patterns, suggested_types

    def _calculate_confidence(
        self, domains: Set[str], areas: Set[str], query_type: str, language: str
    ) -> float:
        """Összesített konfidencia számítás"""

        confidence = 0.0

        # Base confidence from detections
        if domains:
            confidence += 0.3 * min(len(domains) / 2, 1.0)

        if areas:
            confidence += 0.2 * min(len(areas) / 2, 1.0)

        if query_type != "unknown":
            confidence += 0.3

        # Language detection confidence
        if language in ["hu", "en"]:  # Supported languages
            confidence += 0.2

        return min(confidence, 1.0)

    def _collect_matched_keywords(
        self, text: str, language: str, domains: Set[str], areas: Set[str]
    ) -> Dict[str, List[str]]:
        """Matched keywords gyűjtése debug célokra"""

        matched: Dict[str, List[str]] = {"domains": [], "areas": [], "query_types": []}

        # Domain matches
        for domain in domains:
            if (
                domain in self.domain_patterns
                and language in self.domain_patterns[domain]
            ):
                keywords = self.domain_patterns[domain][language]
                found = [kw for kw in keywords if kw in text]
                if found:
                    matched["domains"].extend(found)

        # Area matches
        if language in self.area_patterns:
            for area in areas:
                if area in self.area_patterns[language]:
                    keywords = self.area_patterns[language][area]
                    found = [kw for kw in keywords if kw in text]
                    if found:
                        matched["areas"].extend(found)

        # Query type matches
        for query_type, lang_patterns in self.query_type_patterns.items():
            if language in lang_patterns:
                keywords = lang_patterns[language]
                found = [kw for kw in keywords if kw in text]
                if found:
                    matched["query_types"].extend(found)

        return matched
