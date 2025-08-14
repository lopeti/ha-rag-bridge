"""Centralized configuration management with comprehensive documentation.

This module provides type-safe, validated configuration management for the
HA RAG Bridge application. All environment variables are centrally managed
with detailed Hungarian and English documentation for the admin UI.
"""

import os
from typing import Dict, Optional, Any, Literal
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    """ArangoDB and vector database configuration.

    Adatbázis és vektor konfiguráció beállítások.
    """

    # Connection settings
    arango_url: str = Field(
        default="http://localhost:8529",
        env="ARANGO_URL",
        title_hu="ArangoDB URL",
        title_en="ArangoDB URL",
        description_hu="Az ArangoDB adatbázis szerver címe és portja. Alapértelmezett: http://localhost:8529",
        description_en="ArangoDB database server URL and port. Default: http://localhost:8529",
        example="http://localhost:8529",
    )

    arango_user: str = Field(
        default="root",
        env="ARANGO_USER",
        title_hu="Adatbázis felhasználónév",
        title_en="Database Username",
        description_hu="Az ArangoDB bejelentkezési felhasználónév. Alapértelmezett: root",
        description_en="ArangoDB login username. Default: root",
    )

    arango_pass: str = Field(
        default="changeme",
        env="ARANGO_PASS",
        title_hu="Adatbázis jelszó",
        title_en="Database Password",
        description_hu="Az ArangoDB bejelentkezési jelszó. Biztonsági okokból módosítsa!",
        description_en="ArangoDB login password. Change for security!",
        is_sensitive=True,
    )

    arango_db: str = Field(
        default="_system",
        env="ARANGO_DB",
        title_hu="Adatbázis neve",
        title_en="Database Name",
        description_hu="Az használt ArangoDB adatbázis neve. Alapértelmezett: _system",
        description_en="ArangoDB database name to use. Default: _system",
    )

    # Vector settings
    embed_dim: int = Field(
        default=384,
        env="EMBED_DIM",
        title_hu="Vektor dimenzió",
        title_en="Vector Dimension",
        description_hu="A vektor embedding dimenzió. Magasabb érték = jobb pontosság, több erőforrás",
        description_en="Vector embedding dimension. Higher value = better accuracy, more resources",
        recommendation_hu="384: alapértelmezett, 768: optimális minőség, 1536: maximum pontosság",
        recommendation_en="384: default, 768: optimal quality, 1536: maximum accuracy",
        ge=256,
        le=3072,
        restart_required=True,
    )

    auto_bootstrap: bool = Field(
        default=True,
        env="AUTO_BOOTSTRAP",
        title_hu="Automatikus inicializálás",
        title_en="Auto Bootstrap",
        description_hu="Automatikusan inicializálja az adatbázis sémát indításkor",
        description_en="Automatically initialize database schema on startup",
    )


class EmbeddingSettings(BaseModel):
    """AI embedding and model configuration.

    Mesterséges intelligencia és embedding beállítások.
    """

    backend: Literal["local", "openai", "gemini"] = Field(
        default="local",
        env="EMBEDDING_BACKEND",
        title_hu="Embedding háttérszolgáltatás",
        title_en="Embedding Backend",
        description_hu="Válassza ki a vektor embedding szolgáltatást",
        description_en="Choose the vector embedding service",
        recommendation_hu="local: ingyenes, lassabb | openai: fizetős, gyors | gemini: fizetős, kiváló minőség",
        recommendation_en="local: free, slower | openai: paid, fast | gemini: paid, excellent quality",
    )

    model_name: str = Field(
        default="paraphrase-multilingual-mpnet-base-v2",
        env="SENTENCE_TRANSFORMER_MODEL",
        title_hu="Local embedding modell",
        title_en="Local Embedding Model",
        description_hu="A helyi SentenceTransformer modell neve. Csak 'local' backend esetén",
        description_en="Local SentenceTransformer model name. Only for 'local' backend",
    )

    cpu_threads: int = Field(
        default=4,
        env="EMBEDDING_CPU_THREADS",
        title_hu="CPU szálak száma",
        title_en="CPU Threads Count",
        description_hu="CPU szálak száma a helyi embedding generáláshoz. Ajánlott: CPU magok száma",
        description_en="Number of CPU threads for local embedding generation. Recommended: number of CPU cores",
        ge=1,
        le=32,
    )

    # API Keys (sensitive)
    openai_api_key: Optional[str] = Field(
        default=None,
        env="OPENAI_API_KEY",
        title_hu="OpenAI API kulcs",
        title_en="OpenAI API Key",
        description_hu="OpenAI API kulcs az embedding szolgáltatáshoz. Csak 'openai' backend esetén",
        description_en="OpenAI API key for embedding service. Only for 'openai' backend",
        is_sensitive=True,
    )

    gemini_api_key: Optional[str] = Field(
        default=None,
        env="GEMINI_API_KEY",
        title_hu="Gemini API kulcs",
        title_en="Gemini API Key",
        description_hu="Google Gemini API kulcs az embedding szolgáltatáshoz. Csak 'gemini' backend esetén",
        description_en="Google Gemini API key for embedding service. Only for 'gemini' backend",
        is_sensitive=True,
    )


class PerformanceSettings(BaseModel):
    """Performance and caching configuration.

    Teljesítmény és gyorsítótár beállítások.
    """

    # Cache sizes
    state_cache_maxsize: int = Field(
        default=1024,
        env="CACHE_MAXSIZE_STATE",
        title_hu="Állapot cache mérete",
        title_en="State Cache Size",
        description_hu="Az entitás állapot cache maximum elemeinek száma",
        description_en="Maximum number of elements in entity state cache",
        ge=100,
        le=10000,
    )

    conversation_cache_maxsize: int = Field(
        default=100,
        env="CACHE_MAXSIZE_CONVERSATION",
        title_hu="Beszélgetés cache mérete",
        title_en="Conversation Cache Size",
        description_hu="A beszélgetési aliases cache maximum elemeinek száma",
        description_en="Maximum number of elements in conversation aliases cache",
        ge=1,
        le=1000,
    )

    entity_score_cache_maxsize: int = Field(
        default=1000,
        env="CACHE_MAXSIZE_ENTITY_SCORE",
        title_hu="Entitás pontszám cache mérete",
        title_en="Entity Score Cache Size",
        description_hu="Az entitás újrarangsorolási pontszámok cache mérete",
        description_en="Entity reranking scores cache size",
        ge=100,
        le=5000,
    )

    entity_context_cache_maxsize: int = Field(
        default=500,
        env="CACHE_MAXSIZE_ENTITY_CONTEXT",
        title_hu="Entitás kontextus cache mérete",
        title_en="Entity Context Cache Size",
        description_hu="Az entitás kontextus cache maximum elemeinek száma",
        description_en="Maximum number of elements in entity context cache",
        ge=50,
        le=2000,
    )

    # Cache TTLs (in seconds)
    state_cache_ttl: int = Field(
        default=30,
        env="STATE_CACHE_TTL",
        title_hu="Állapot cache élettartam",
        title_en="State Cache TTL",
        description_hu="Az entitás állapot cache élettartama másodpercben",
        description_en="Entity state cache time-to-live in seconds",
        ge=5,
        le=3600,
    )

    conversation_aliases_ttl: int = Field(
        default=600,
        env="CONVERSATION_ALIASES_TTL",
        title_hu="Beszélgetési aliases TTL",
        title_en="Conversation Aliases TTL",
        description_hu="A beszélgetési területi aliases cache élettartama másodpercben",
        description_en="Conversation area aliases cache TTL in seconds",
        ge=60,
        le=3600,
    )

    entity_reranker_cache_ttl: int = Field(
        default=300,
        env="ENTITY_RERANKER_CACHE_TTL",
        title_hu="Entitás újrarangsorolás cache TTL",
        title_en="Entity Reranker Cache TTL",
        description_hu="Az entitás újrarangsorolási cache élettartama másodpercben",
        description_en="Entity reranking cache time-to-live in seconds",
        ge=60,
        le=1800,
    )

    service_cache_ttl: int = Field(
        default=21600,  # 6 hours
        env="SERVICE_CACHE_TTL",
        title_hu="Szolgáltatás cache élettartam",
        title_en="Service Cache TTL",
        description_hu="A Home Assistant szolgáltatások cache élettartama másodpercben (6 óra)",
        description_en="Home Assistant services cache TTL in seconds (6 hours)",
        ge=300,
        le=86400,
    )


class QueryScopeSettings(BaseModel):
    """Query scope detection and adaptive retrieval configuration.

    Lekérdezési hatókör észlelés és adaptív visszakeresés beállítások.
    """

    # Scope thresholds
    scope_threshold_micro: float = Field(
        default=0.8,
        env="SCOPE_THRESHOLD_MICRO",
        title_hu="Mikro hatókör küszöb",
        title_en="Micro Scope Threshold",
        description_hu="Pontos entitás műveletek (pl. 'kapcsold fel a lámpát') észlelési küszöbe",
        description_en="Specific entity operations (e.g. 'turn on the light') detection threshold",
        ge=0.5,
        le=1.0,
    )

    scope_threshold_macro: float = Field(
        default=0.7,
        env="SCOPE_THRESHOLD_MACRO",
        title_hu="Makro hatókör küszöb",
        title_en="Macro Scope Threshold",
        description_hu="Terület-alapú lekérdezések (pl. 'mi van a nappaliban') küszöbe",
        description_en="Area-based queries (e.g. 'what's in the living room') threshold",
        ge=0.5,
        le=1.0,
    )

    scope_threshold_overview: float = Field(
        default=0.6,
        env="SCOPE_THRESHOLD_OVERVIEW",
        title_hu="Áttekintő hatókör küszöb",
        title_en="Overview Scope Threshold",
        description_hu="Ház-szintű áttekintő lekérdezések (pl. 'mi a helyzet otthon') küszöbe",
        description_en="House-wide overview queries (e.g. 'what's the situation at home') threshold",
        ge=0.4,
        le=1.0,
    )

    # K-value ranges for different scopes
    scope_k_min_micro: int = Field(
        default=5,
        env="SCOPE_K_MIN_MICRO",
        title_hu="Mikro hatókör min. eredmények",
        title_en="Micro Scope Min Results",
        description_hu="Pontos entitás műveletek esetén minimum visszaadott eredmények száma",
        description_en="Minimum number of results returned for specific entity operations",
        ge=1,
        le=20,
    )

    scope_k_max_micro: int = Field(
        default=10,
        env="SCOPE_K_MAX_MICRO",
        title_hu="Mikro hatókör max. eredmények",
        title_en="Micro Scope Max Results",
        description_hu="Pontos entitás műveletek esetén maximum visszaadott eredmények száma",
        description_en="Maximum number of results returned for specific entity operations",
        ge=5,
        le=30,
    )

    scope_k_min_macro: int = Field(
        default=15,
        env="SCOPE_K_MIN_MACRO",
        title_hu="Makro hatókör min. eredmények",
        title_en="Macro Scope Min Results",
        description_hu="Terület-alapú lekérdezések esetén minimum visszaadott eredmények száma",
        description_en="Minimum number of results returned for area-based queries",
        ge=10,
        le=40,
    )

    scope_k_max_macro: int = Field(
        default=30,
        env="SCOPE_K_MAX_MACRO",
        title_hu="Makro hatókör max. eredmények",
        title_en="Macro Scope Max Results",
        description_hu="Terület-alapú lekérdezések esetén maximum visszaadott eredmények száma",
        description_en="Maximum number of results returned for area-based queries",
        ge=20,
        le=60,
    )

    scope_k_min_overview: int = Field(
        default=30,
        env="SCOPE_K_MIN_OVERVIEW",
        title_hu="Áttekintő hatókör min. eredmények",
        title_en="Overview Scope Min Results",
        description_hu="Ház-szintű áttekintő lekérdezések esetén minimum eredmények száma",
        description_en="Minimum number of results for house-wide overview queries",
        ge=20,
        le=80,
    )

    scope_k_max_overview: int = Field(
        default=50,
        env="SCOPE_K_MAX_OVERVIEW",
        title_hu="Áttekintő hatókör max. eredmények",
        title_en="Overview Scope Max Results",
        description_hu="Ház-szintű áttekintő lekérdezések esetén maximum eredmények száma",
        description_en="Maximum number of results for house-wide overview queries",
        ge=40,
        le=100,
    )


class SimilaritySettings(BaseModel):
    """Semantic similarity threshold configuration.

    Szemantikus hasonlóság küszöb beállítások.
    """

    similarity_threshold_excellent: Optional[float] = Field(
        default=None,
        env="SIMILARITY_THRESHOLD_EXCELLENT",
        title_hu="Kiváló hasonlóság küszöb",
        title_en="Excellent Similarity Threshold",
        description_hu="Kiváló szemantikus hasonlóság küszöbértéke. None = automatikus modell-specifikus érték",
        description_en="Excellent semantic similarity threshold. None = automatic model-specific value",
        ge=0.7,
        le=1.0,
    )

    similarity_threshold_good: Optional[float] = Field(
        default=None,
        env="SIMILARITY_THRESHOLD_GOOD",
        title_hu="Jó hasonlóság küszöb",
        title_en="Good Similarity Threshold",
        description_hu="Jó szemantikus hasonlóság küszöbértéke. None = automatikus modell-specifikus érték",
        description_en="Good semantic similarity threshold. None = automatic model-specific value",
        ge=0.5,
        le=0.9,
    )

    similarity_threshold_acceptable: Optional[float] = Field(
        default=None,
        env="SIMILARITY_THRESHOLD_ACCEPTABLE",
        title_hu="Elfogadható hasonlóság küszöb",
        title_en="Acceptable Similarity Threshold",
        description_hu="Elfogadható szemantikus hasonlóság küszöbértéke",
        description_en="Acceptable semantic similarity threshold",
        ge=0.3,
        le=0.8,
    )

    similarity_threshold_minimum: Optional[float] = Field(
        default=None,
        env="SIMILARITY_THRESHOLD_MINIMUM",
        title_hu="Minimum hasonlóság küszöb",
        title_en="Minimum Similarity Threshold",
        description_hu="Minimum elfogadott szemantikus hasonlóság küszöbértéke",
        description_en="Minimum accepted semantic similarity threshold",
        ge=0.1,
        le=0.7,
    )


class NetworkSettings(BaseModel):
    """Network and HTTP configuration.

    Hálózat és HTTP beállítások.
    """

    http_timeout: float = Field(
        default=30.0,
        env="HTTP_TIMEOUT",
        title_hu="HTTP időtúllépés",
        title_en="HTTP Timeout",
        description_hu="HTTP kérések általános időtúllépése másodpercben",
        description_en="General HTTP requests timeout in seconds",
        ge=1.0,
        le=300.0,
    )

    http_timeout_short: float = Field(
        default=5.0,
        env="HTTP_TIMEOUT_SHORT",
        title_hu="Rövid HTTP időtúllépés",
        title_en="Short HTTP Timeout",
        description_hu="Gyors HTTP kérések időtúllépése (pl. állapot lekérdezés)",
        description_en="Fast HTTP requests timeout (e.g. state queries)",
        ge=1.0,
        le=30.0,
    )

    http_timeout_medium: float = Field(
        default=15.0,
        env="HTTP_TIMEOUT_MEDIUM",
        title_hu="Közepes HTTP időtúllépés",
        title_en="Medium HTTP Timeout",
        description_hu="Közepes HTTP kérések időtúllépése (pl. embedding generálás)",
        description_en="Medium HTTP requests timeout (e.g. embedding generation)",
        ge=5.0,
        le=60.0,
    )

    http_timeout_long: float = Field(
        default=60.0,
        env="HTTP_TIMEOUT_LONG",
        title_hu="Hosszú HTTP időtúllépés",
        title_en="Long HTTP Timeout",
        description_hu="Hosszú HTTP kérések időtúllépése (pl. nagy adatátvitel)",
        description_en="Long HTTP requests timeout (e.g. large data transfer)",
        ge=30.0,
        le=600.0,
    )

    log_stream_max_timeout: int = Field(
        default=300,
        env="LOG_STREAM_MAX_TIMEOUT",
        title_hu="Log stream maximum időtúllépés",
        title_en="Log Stream Max Timeout",
        description_hu="Log streaming maximum időtúllépése másodpercben (5 perc)",
        description_en="Log streaming maximum timeout in seconds (5 minutes)",
        ge=60,
        le=1800,
    )


class HomeAssistantSettings(BaseModel):
    """Home Assistant integration configuration.

    Home Assistant integráció beállítások.
    """

    ha_url: Optional[str] = Field(
        default=None,
        env="HA_URL",
        title_hu="Home Assistant URL",
        title_en="Home Assistant URL",
        description_hu="A Home Assistant példány URL címe (pl. http://homeassistant.local:8123)",
        description_en="Home Assistant instance URL (e.g. http://homeassistant.local:8123)",
        example="http://homeassistant.local:8123",
    )

    ha_token: Optional[str] = Field(
        default=None,
        env="HA_TOKEN",
        title_hu="Home Assistant token",
        title_en="Home Assistant Token",
        description_hu="Home Assistant hosszú távú hozzáférési token",
        description_en="Home Assistant long-lived access token",
        is_sensitive=True,
    )

    conversation_memory_ttl: int = Field(
        default=15,
        env="CONVERSATION_MEMORY_TTL",
        title_hu="Beszélgetés memória élettartam",
        title_en="Conversation Memory TTL",
        description_hu="Beszélgetési kontextus memória élettartama percekben",
        description_en="Conversation context memory TTL in minutes",
        ge=5,
        le=60,
    )


class CrossEncoderSettings(BaseModel):
    """Cross-encoder model configuration for semantic reranking.

    Cross-encoder modell konfiguráció a szemantikai újrarangsoroláshoz.
    """

    model_name: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        env="CROSS_ENCODER_MODEL",
        title_hu="Cross-encoder modell",
        title_en="Cross-encoder Model",
        description_hu="Hugging Face cross-encoder modell neve a szemantikai pontozáshoz",
        description_en="Hugging Face cross-encoder model name for semantic scoring",
        recommendation_hu="ms-marco-MiniLM-L-6-v2: alapértelmezett | paraphrase-multilingual-mpnet-base-v2: multilingual | all-MiniLM-L12-v2: nagyobb pontosság",
        recommendation_en="ms-marco-MiniLM-L-6-v2: default | paraphrase-multilingual-mpnet-base-v2: multilingual | all-MiniLM-L12-v2: higher accuracy",
        restart_required=True,
    )

    # Score normalization parameters
    score_scale_factor: float = Field(
        default=2.0,
        env="CROSS_ENCODER_SCALE_FACTOR",
        title_hu="Score skálázási faktor",
        title_en="Score Scale Factor",
        description_hu="Cross-encoder nyers score skálázási faktora (-1..+1 → 0..1 normalizáláshoz)",
        description_en="Cross-encoder raw score scaling factor for (-1..+1 → 0..1 normalization)",
        ge=1.0,
        le=5.0,
    )

    score_offset: float = Field(
        default=1.0,
        env="CROSS_ENCODER_OFFSET",
        title_hu="Score eltolás",
        title_en="Score Offset",
        description_hu="Cross-encoder score eltolási érték a normalizálás során",
        description_en="Cross-encoder score offset value during normalization",
        ge=0.0,
        le=2.0,
    )

    score_min_bound: float = Field(
        default=0.0,
        env="CROSS_ENCODER_MIN_BOUND",
        title_hu="Minimum score határ",
        title_en="Minimum Score Bound",
        description_hu="Normalizált score minimum értéke",
        description_en="Normalized score minimum value",
        ge=0.0,
        le=1.0,
    )

    score_max_bound: float = Field(
        default=1.0,
        env="CROSS_ENCODER_MAX_BOUND",
        title_hu="Maximum score határ",
        title_en="Maximum Score Bound",
        description_hu="Normalizált score maximum értéke",
        description_en="Normalized score maximum value",
        ge=0.0,
        le=1.0,
    )

    # Performance settings
    enable_caching: bool = Field(
        default=True,
        env="CROSS_ENCODER_ENABLE_CACHING",
        title_hu="Cache engedélyezése",
        title_en="Enable Caching",
        description_hu="Cross-encoder eredmények gyorsítótárazásának engedélyezése",
        description_en="Enable caching of cross-encoder results",
    )

    fallback_threshold: float = Field(
        default=0.1,
        env="CROSS_ENCODER_FALLBACK_THRESHOLD",
        title_hu="Fallback küszöb",
        title_en="Fallback Threshold",
        description_hu="Küszöb érték ami alatt text matching-re vált keresztentrópia helyett",
        description_en="Threshold below which to fallback to text matching instead of cross-encoder",
        ge=0.0,
        le=1.0,
    )


class RankingSettings(BaseModel):
    """Entity ranking boost factors configuration.

    Entitás rangsorolási boost faktorok konfigurációja.
    """

    # Area boost factors
    area_generic_house_boost: float = Field(
        default=1.2,
        env="RANKING_AREA_GENERIC_BOOST",
        title_hu="Általános ház boost",
        title_en="Generic House Boost",
        description_hu="Boost faktor általános ház említésekhez ('ház', 'itthon')",
        description_en="Boost factor for generic house references ('house', 'home')",
        ge=1.0,
        le=3.0,
    )

    area_specific_boost: float = Field(
        default=2.0,
        env="RANKING_AREA_SPECIFIC_BOOST",
        title_hu="Specifikus terület boost",
        title_en="Specific Area Boost",
        description_hu="Boost faktor konkrét terület említésekhez (pl. 'nappali', 'konyha')",
        description_en="Boost factor for specific area mentions (e.g. 'living room', 'kitchen')",
        ge=1.0,
        le=5.0,
    )

    area_followup_multiplier: float = Field(
        default=1.5,
        env="RANKING_AREA_FOLLOWUP_MULTIPLIER",
        title_hu="Követő kérdés szorzó",
        title_en="Follow-up Question Multiplier",
        description_hu="Szorzó faktor a terület boost-okhoz követő kérdések esetén",
        description_en="Multiplier factor for area boosts in follow-up questions",
        ge=1.0,
        le=3.0,
    )

    # Domain and device class boosts
    domain_boost: float = Field(
        default=1.5,
        env="RANKING_DOMAIN_BOOST",
        title_hu="Domain boost",
        title_en="Domain Boost",
        description_hu="Boost faktor entitás domain említésekhez (pl. 'sensor', 'light')",
        description_en="Boost factor for entity domain mentions (e.g. 'sensor', 'light')",
        ge=1.0,
        le=3.0,
    )

    device_class_boost: float = Field(
        default=2.0,
        env="RANKING_DEVICE_CLASS_BOOST",
        title_hu="Eszköz osztály boost",
        title_en="Device Class Boost",
        description_hu="Boost faktor eszköz osztály említésekhez (pl. 'temperature', 'motion')",
        description_en="Boost factor for device class mentions (e.g. 'temperature', 'motion')",
        ge=1.0,
        le=5.0,
    )

    # Intent-based boosts
    previous_mention_boost: float = Field(
        default=0.3,
        env="RANKING_PREVIOUS_MENTION_BOOST",
        title_hu="Korábbi említés boost",
        title_en="Previous Mention Boost",
        description_hu="Boost faktor korábban említett entitásokhoz",
        description_en="Boost factor for previously mentioned entities",
        ge=0.0,
        le=1.0,
    )

    controllable_intent_boost: float = Field(
        default=0.2,
        env="RANKING_CONTROLLABLE_BOOST",
        title_hu="Vezérelhető entitás boost",
        title_en="Controllable Entity Boost",
        description_hu="Boost faktor vezérelhető entitásokhoz vezérlési szándék esetén",
        description_en="Boost factor for controllable entities in control intents",
        ge=0.0,
        le=1.0,
    )

    readable_intent_boost: float = Field(
        default=0.1,
        env="RANKING_READABLE_BOOST",
        title_hu="Olvasható entitás boost",
        title_en="Readable Entity Boost",
        description_hu="Boost faktor érzékelőkhöz olvasási szándék esetén",
        description_en="Boost factor for sensors in read intents",
        ge=0.0,
        le=1.0,
    )

    # Sensor availability factors
    active_sensor_boost: float = Field(
        default=2.0,
        env="RANKING_ACTIVE_SENSOR_BOOST",
        title_hu="Aktív érzékelő boost",
        title_en="Active Sensor Boost",
        description_hu="Erős boost faktor aktív értékkel rendelkező érzékelőkhoz",
        description_en="Strong boost factor for sensors with active state values",
        ge=0.0,
        le=5.0,
    )

    unavailable_sensor_penalty: float = Field(
        default=-0.5,
        env="RANKING_UNAVAILABLE_PENALTY",
        title_hu="Nem elérhető érzékelő büntetés",
        title_en="Unavailable Sensor Penalty",
        description_hu="Büntetés faktor nem elérhető vagy inaktív érzékelőkhöz",
        description_en="Penalty factor for unavailable or inactive sensors",
        ge=-2.0,
        le=0.0,
    )

    # Multiplicative area boosting
    area_multiplier_base: float = Field(
        default=1.0,
        env="RANKING_AREA_MULTIPLIER_BASE",
        title_hu="Terület szorzó alap",
        title_en="Area Multiplier Base",
        description_hu="Alap érték a multiplikatív terület boost-hoz",
        description_en="Base value for multiplicative area boost",
        ge=0.5,
        le=2.0,
    )

    area_context_factor: float = Field(
        default=0.5,
        env="RANKING_AREA_CONTEXT_FACTOR",
        title_hu="Terület kontextus faktor",
        title_en="Area Context Factor",
        description_hu="Kontextus boost faktor a multiplikatív terület boost számításához",
        description_en="Context boost factor for multiplicative area boost calculation",
        ge=0.0,
        le=2.0,
    )


class DebugSettings(BaseModel):
    """Debug and development configuration.

    Debug és fejlesztői beállítások.
    """

    debug: bool = Field(
        default=False,
        env="DEBUG",
        title_hu="Debug mód",
        title_en="Debug Mode",
        description_hu="Debug mód engedélyezése fejlesztési célokra",
        description_en="Enable debug mode for development purposes",
    )

    log_level: str = Field(
        default="INFO",
        env="LOG_LEVEL",
        title_hu="Log szint",
        title_en="Log Level",
        description_hu="Általános alkalmazás log szint (DEBUG, INFO, WARNING, ERROR)",
        description_en="General application log level (DEBUG, INFO, WARNING, ERROR)",
    )

    ha_rag_log_level: str = Field(
        default="INFO",
        env="HA_RAG_LOG_LEVEL",
        title_hu="HA RAG log szint",
        title_en="HA RAG Log Level",
        description_hu="HA RAG komponensek specifikus log szintje",
        description_en="HA RAG components specific log level",
    )

    log_file: Optional[str] = Field(
        default=None,
        env="LOG_FILE",
        title_hu="Log fájl elérési útja",
        title_en="Log File Path",
        description_hu="Log fájl elérési útja. None = csak konzol kimenet",
        description_en="Log file path. None = console output only",
    )

    skip_arango_healthcheck: bool = Field(
        default=False,
        env="SKIP_ARANGO_HEALTHCHECK",
        title_hu="ArangoDB health check kihagyása",
        title_en="Skip ArangoDB Health Check",
        description_hu="Az ArangoDB kapcsolat ellenőrzésének kihagyása indításkor",
        description_en="Skip ArangoDB connection check on startup",
    )


class SecuritySettings(BaseModel):
    """Security and authentication configuration.

    Biztonsági és hitelesítési beállítások.
    """

    admin_token: str = Field(
        default="",
        env="ADMIN_TOKEN",
        title_hu="Admin token",
        title_en="Admin Token",
        description_hu="Admin felület hozzáférési token. Üres = token ellenőrzés kikapcsolva debug módban",
        description_en="Admin interface access token. Empty = token check disabled in debug mode",
        is_sensitive=True,
    )


class AppSettings(BaseSettings):
    """Main application settings with all configuration fields.

    Fő alkalmazás beállítások az összes konfigurációs mezővel.
    """

    # Database settings
    arango_url: str = Field(
        default="http://localhost:8529",
        env="ARANGO_URL",
        title_hu="ArangoDB URL",
        title_en="ArangoDB URL",
        description_hu="Az ArangoDB szerver teljes URL címe (http://host:port)",
        description_en="Full URL of the ArangoDB server (http://host:port)",
    )

    arango_user: str = Field(
        default="root",
        env="ARANGO_USER",
        title_hu="Adatbázis felhasználó",
        title_en="Database User",
        description_hu="ArangoDB felhasználónév az authentikációhoz",
        description_en="ArangoDB username for authentication",
    )

    arango_pass: str = Field(
        default="changeme",
        env="ARANGO_PASS",
        title_hu="Adatbázis jelszó",
        title_en="Database Password",
        description_hu="ArangoDB jelszó az authentikációhoz",
        description_en="ArangoDB password for authentication",
        is_sensitive=True,
    )

    arango_db: str = Field(
        default="_system",
        env="ARANGO_DB",
        title_hu="Adatbázis neve",
        title_en="Database Name",
        description_hu="Az használt ArangoDB adatbázis neve",
        description_en="ArangoDB database name to use",
    )

    embed_dim: int = Field(
        default=384,
        env="EMBED_DIM",
        title_hu="Vektor dimenzió",
        title_en="Vector Dimension",
        description_hu="Vektor embedding dimenzió. KRITIKUS: Dimenzió változtatás után kötelező a teljes reindex!",
        description_en="Vector embedding dimension. CRITICAL: Dimension change requires complete reindex!",
        recommendation_hu="384: gyors, 768: balanced (ajánlott), 1536: maximum pontosság. FIGYELEM: Dimenzió váltás után Maintenance → Reindex kötelező!",
        recommendation_en="384: fast, 768: balanced (recommended), 1536: maximum accuracy. WARNING: After dimension change, Maintenance → Reindex is mandatory!",
        ge=256,
        le=3072,
        restart_required=False,
    )

    auto_bootstrap: bool = Field(
        default=True,
        env="AUTO_BOOTSTRAP",
        title_hu="Automatikus inicializálás",
        title_en="Auto Bootstrap",
        description_hu="Automatikusan inicializálja az adatbázis sémát indításkor",
        description_en="Automatically initialize database schema on startup",
    )

    # Embedding settings
    embedding_backend: Literal["local", "openai", "gemini"] = Field(
        default="local",
        env="EMBEDDING_BACKEND",
        title_hu="Embedding backend",
        title_en="Embedding Backend",
        description_hu="Melyik AI szolgáltatást használja az embedding generáláshoz. FIGYELEM: Változtatás után újra kell generálni az összes entity embeddinget!",
        description_en="Which AI service to use for embedding generation. WARNING: After changing, you must regenerate all entity embeddings!",
        recommendation_hu="Backend váltás után: 1) Mentés, 2) Maintenance → Re-ingest entities, 3) Reindex vector indexes",
        recommendation_en="After backend change: 1) Save, 2) Maintenance → Re-ingest entities, 3) Reindex vector indexes",
        restart_required=False,
    )

    sentence_transformer_model: str = Field(
        default="paraphrase-multilingual-mpnet-base-v2",
        env="SENTENCE_TRANSFORMER_MODEL",
        title_hu="SentenceTransformer model",
        title_en="SentenceTransformer Model",
        description_hu="A használt SentenceTransformer model neve (helyi backend esetén). Model váltás után újra kell generálni az embeddings-eket!",
        description_en="SentenceTransformer model name to use (for local backend). After model change, embeddings must be regenerated!",
        recommendation_hu="Népszerű modellek: all-MiniLM-L6-v2 (gyors), paraphrase-multilingual-mpnet-base-v2 (többnyelvű)",
        recommendation_en="Popular models: all-MiniLM-L6-v2 (fast), paraphrase-multilingual-mpnet-base-v2 (multilingual)",
        example="paraphrase-multilingual-mpnet-base-v2",
        restart_required=False,
    )

    embedding_cpu_threads: int = Field(
        default=4,
        env="EMBEDDING_CPU_THREADS",
        title_hu="CPU szálak száma",
        title_en="CPU Threads",
        description_hu="CPU szálak száma a helyi embedding számításhoz",
        description_en="Number of CPU threads for local embedding computation",
        ge=1,
        le=32,
    )

    openai_api_key: Optional[str] = Field(
        default=None,
        env="OPENAI_API_KEY",
        title_hu="OpenAI API kulcs",
        title_en="OpenAI API Key",
        description_hu="OpenAI API kulcs az embedding szolgáltatáshoz",
        description_en="OpenAI API key for embedding service",
        is_sensitive=True,
    )

    gemini_api_key: Optional[str] = Field(
        default=None,
        env="GEMINI_API_KEY",
        title_hu="Gemini API kulcs",
        title_en="Gemini API Key",
        description_hu="Google Gemini API kulcs az embedding szolgáltatáshoz",
        description_en="Google Gemini API key for embedding service",
        is_sensitive=True,
    )

    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com",
        env="GEMINI_BASE_URL",
        title_hu="Gemini base URL",
        title_en="Gemini Base URL",
        description_hu="Google Gemini API alap URL címe",
        description_en="Google Gemini API base URL",
    )

    # Network settings
    http_timeout: float = Field(
        default=30.0,
        env="HTTP_TIMEOUT",
        title_hu="HTTP timeout",
        title_en="HTTP Timeout",
        description_hu="HTTP kérések timeout értéke másodpercben",
        description_en="HTTP request timeout in seconds",
        ge=1.0,
        le=300.0,
    )

    # Security settings
    admin_token: str = Field(
        default="",
        env="ADMIN_TOKEN",
        title_hu="Admin token",
        title_en="Admin Token",
        description_hu="Titkos token az admin felület eléréséhez",
        description_en="Secret token for admin interface access",
        is_sensitive=True,
    )

    # Home Assistant settings
    ha_url: Optional[str] = Field(
        default=None,
        env="HA_URL",
        title_hu="Home Assistant URL",
        title_en="Home Assistant URL",
        description_hu="A Home Assistant példány URL címe (pl. http://homeassistant.local:8123)",
        description_en="Home Assistant instance URL (e.g. http://homeassistant.local:8123)",
        example="http://homeassistant.local:8123",
    )

    ha_token: Optional[str] = Field(
        default=None,
        env="HA_TOKEN",
        title_hu="Home Assistant token",
        title_en="Home Assistant Token",
        description_hu="Home Assistant hosszú távú hozzáférési token",
        description_en="Home Assistant long-lived access token",
        is_sensitive=True,
    )

    # Debug settings
    debug: bool = Field(
        default=False,
        env="DEBUG",
        title_hu="Debug mód",
        title_en="Debug Mode",
        description_hu="Debug mód engedélyezése fejlesztési célokra",
        description_en="Enable debug mode for development purposes",
    )

    log_level: str = Field(
        default="INFO",
        env="LOG_LEVEL",
        title_hu="Log szint",
        title_en="Log Level",
        description_hu="Általános alkalmazás log szint (DEBUG, INFO, WARNING, ERROR)",
        description_en="General application log level (DEBUG, INFO, WARNING, ERROR)",
    )

    ha_rag_log_level: str = Field(
        default="INFO",
        env="HA_RAG_LOG_LEVEL",
        title_hu="HA RAG log szint",
        title_en="HA RAG Log Level",
        description_hu="HA RAG komponensek specifikus log szintje",
        description_en="HA RAG components specific log level",
    )

    log_file: Optional[str] = Field(
        default=None,
        env="LOG_FILE",
        title_hu="Log fájl elérési útja",
        title_en="Log File Path",
        description_hu="Log fájl elérési útja. None = csak konzol kimenet",
        description_en="Log file path. None = console output only",
    )

    skip_arango_healthcheck: bool = Field(
        default=False,
        env="SKIP_ARANGO_HEALTHCHECK",
        title_hu="ArangoDB health check kihagyása",
        title_en="Skip ArangoDB Health Check",
        description_hu="Az ArangoDB kapcsolat ellenőrzésének kihagyása indításkor",
        description_en="Skip ArangoDB connection check on startup",
    )

    # Performance settings
    state_cache_maxsize: int = Field(
        default=1024,
        env="CACHE_MAXSIZE_STATE",
        title_hu="Állapot cache mérete",
        title_en="State Cache Size",
        description_hu="Az entitás állapot cache maximum elemeinek száma",
        description_en="Maximum number of elements in entity state cache",
        ge=100,
        le=10000,
    )

    conversation_cache_maxsize: int = Field(
        default=100,
        env="CACHE_MAXSIZE_CONVERSATION",
        title_hu="Beszélgetés cache mérete",
        title_en="Conversation Cache Size",
        description_hu="A beszélgetési aliases cache maximum elemeinek száma",
        description_en="Maximum number of elements in conversation aliases cache",
        ge=1,
        le=1000,
    )

    entity_score_cache_maxsize: int = Field(
        default=1000,
        env="CACHE_MAXSIZE_ENTITY_SCORE",
        title_hu="Entitás pontszám cache mérete",
        title_en="Entity Score Cache Size",
        description_hu="Az entitás újrarangsorolási pontszámok cache mérete",
        description_en="Entity reranking scores cache size",
        ge=100,
        le=5000,
    )

    entity_context_cache_maxsize: int = Field(
        default=500,
        env="CACHE_MAXSIZE_ENTITY_CONTEXT",
        title_hu="Entitás kontextus cache mérete",
        title_en="Entity Context Cache Size",
        description_hu="Az entitás kontextus cache maximum elemeinek száma",
        description_en="Maximum number of elements in entity context cache",
        ge=50,
        le=2000,
    )

    # Cache TTL settings
    state_cache_ttl: int = Field(
        default=30,
        env="STATE_CACHE_TTL",
        title_hu="Állapot cache élettartam",
        title_en="State Cache TTL",
        description_hu="Az entitás állapot cache élettartama másodpercben",
        description_en="Entity state cache time-to-live in seconds",
        ge=5,
        le=3600,
    )

    conversation_aliases_ttl: int = Field(
        default=600,
        env="CONVERSATION_ALIASES_TTL",
        title_hu="Beszélgetési aliases TTL",
        title_en="Conversation Aliases TTL",
        description_hu="A beszélgetési területi aliases cache élettartama másodpercben",
        description_en="Conversation area aliases cache TTL in seconds",
        ge=60,
        le=3600,
    )

    entity_reranker_cache_ttl: int = Field(
        default=300,
        env="ENTITY_RERANKER_CACHE_TTL",
        title_hu="Entitás újrarangsorolás cache TTL",
        title_en="Entity Reranker Cache TTL",
        description_hu="Az entitás újrarangsorolási cache élettartama másodpercben",
        description_en="Entity reranking cache time-to-live in seconds",
        ge=60,
        le=1800,
    )

    service_cache_ttl: int = Field(
        default=21600,  # 6 hours
        env="SERVICE_CACHE_TTL",
        title_hu="Szolgáltatás cache élettartam",
        title_en="Service Cache TTL",
        description_hu="A Home Assistant szolgáltatások cache élettartama másodpercben (6 óra)",
        description_en="Home Assistant services cache TTL in seconds (6 hours)",
        ge=300,
        le=86400,
    )

    # Additional Home Assistant settings
    conversation_memory_ttl: int = Field(
        default=15,
        env="CONVERSATION_MEMORY_TTL",
        title_hu="Beszélgetés memória élettartam",
        title_en="Conversation Memory TTL",
        description_hu="Beszélgetési kontextus memória élettartama percekben",
        description_en="Conversation context memory TTL in minutes",
        ge=5,
        le=60,
    )

    # InfluxDB settings
    influx_url: Optional[str] = Field(
        default=None,
        env="INFLUX_URL",
        title_hu="InfluxDB URL",
        title_en="InfluxDB URL",
        description_hu="InfluxDB adatbázis URL címe idősorozat adatok tárolásához",
        description_en="InfluxDB database URL for time series data storage",
        example="http://localhost:8086",
    )

    influx_org: str = Field(
        default="homeassistant",
        env="INFLUX_ORG",
        title_hu="InfluxDB szervezet",
        title_en="InfluxDB Organization",
        description_hu="InfluxDB szervezet neve",
        description_en="InfluxDB organization name",
    )

    influx_bucket: str = Field(
        default="homeassistant",
        env="INFLUX_BUCKET",
        title_hu="InfluxDB bucket",
        title_en="InfluxDB Bucket",
        description_hu="InfluxDB bucket neve az adatok tárolásához",
        description_en="InfluxDB bucket name for data storage",
    )

    influx_db: str = Field(
        default="homeassistant",
        env="INFLUX_DB",
        title_hu="InfluxDB adatbázis",
        title_en="InfluxDB Database",
        description_hu="InfluxDB adatbázis neve (v1.x kompatibilitáshoz)",
        description_en="InfluxDB database name (for v1.x compatibility)",
    )

    influx_user: Optional[str] = Field(
        default=None,
        env="INFLUX_USER",
        title_hu="InfluxDB felhasználó",
        title_en="InfluxDB User",
        description_hu="InfluxDB felhasználónév az authentikációhoz",
        description_en="InfluxDB username for authentication",
    )

    # Cross-encoder settings
    cross_encoder_model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        env="CROSS_ENCODER_MODEL",
        title_hu="Cross-encoder modell",
        title_en="Cross-encoder Model",
        description_hu="Hugging Face cross-encoder modell neve a szemantikai pontozáshoz",
        description_en="Hugging Face cross-encoder model name for semantic scoring",
        recommendation_hu="ms-marco-MiniLM-L-6-v2: alapértelmezett | paraphrase-multilingual-mpnet-base-v2: multilingual",
        recommendation_en="ms-marco-MiniLM-L-6-v2: default | paraphrase-multilingual-mpnet-base-v2: multilingual",
        restart_required=True,
    )

    cross_encoder_scale_factor: float = Field(
        default=2.0,
        env="CROSS_ENCODER_SCALE_FACTOR",
        title_hu="Score skálázási faktor",
        title_en="Score Scale Factor",
        description_hu="Cross-encoder score normalizálási skálázási faktor",
        description_en="Cross-encoder score normalization scale factor",
        ge=1.0,
        le=5.0,
    )

    cross_encoder_offset: float = Field(
        default=1.0,
        env="CROSS_ENCODER_OFFSET",
        title_hu="Score eltolás",
        title_en="Score Offset",
        description_hu="Cross-encoder score eltolási érték",
        description_en="Cross-encoder score offset value",
        ge=0.0,
        le=2.0,
    )

    cross_encoder_enable_caching: bool = Field(
        default=True,
        env="CROSS_ENCODER_ENABLE_CACHING",
        title_hu="Cache engedélyezése",
        title_en="Enable Caching",
        description_hu="Cross-encoder eredmények gyorsítótárazása",
        description_en="Enable caching of cross-encoder results",
    )

    # Ranking boost factors
    ranking_area_generic_boost: float = Field(
        default=1.2,
        env="RANKING_AREA_GENERIC_BOOST",
        title_hu="Általános ház boost",
        title_en="Generic House Boost",
        description_hu="Boost faktor általános ház említésekhez",
        description_en="Boost factor for generic house references",
        ge=1.0,
        le=3.0,
    )

    ranking_area_specific_boost: float = Field(
        default=2.0,
        env="RANKING_AREA_SPECIFIC_BOOST",
        title_hu="Specifikus terület boost",
        title_en="Specific Area Boost",
        description_hu="Boost faktor konkrét terület említésekhez",
        description_en="Boost factor for specific area mentions",
        ge=1.0,
        le=5.0,
    )

    ranking_area_followup_multiplier: float = Field(
        default=1.5,
        env="RANKING_AREA_FOLLOWUP_MULTIPLIER",
        title_hu="Követő kérdés szorzó",
        title_en="Follow-up Question Multiplier",
        description_hu="Szorzó faktor követő kérdések esetén",
        description_en="Multiplier factor for follow-up questions",
        ge=1.0,
        le=3.0,
    )

    ranking_domain_boost: float = Field(
        default=1.5,
        env="RANKING_DOMAIN_BOOST",
        title_hu="Domain boost",
        title_en="Domain Boost",
        description_hu="Boost faktor domain említésekhez",
        description_en="Boost factor for domain mentions",
        ge=1.0,
        le=3.0,
    )

    ranking_device_class_boost: float = Field(
        default=2.0,
        env="RANKING_DEVICE_CLASS_BOOST",
        title_hu="Eszköz osztály boost",
        title_en="Device Class Boost",
        description_hu="Boost faktor eszköz osztály említésekhez",
        description_en="Boost factor for device class mentions",
        ge=1.0,
        le=5.0,
    )

    ranking_previous_mention_boost: float = Field(
        default=0.3,
        env="RANKING_PREVIOUS_MENTION_BOOST",
        title_hu="Korábbi említés boost",
        title_en="Previous Mention Boost",
        description_hu="Boost faktor korábban említett entitásokhoz",
        description_en="Boost factor for previously mentioned entities",
        ge=0.0,
        le=1.0,
    )

    ranking_controllable_boost: float = Field(
        default=0.2,
        env="RANKING_CONTROLLABLE_BOOST",
        title_hu="Vezérelhető entitás boost",
        title_en="Controllable Entity Boost",
        description_hu="Boost faktor vezérelhető entitásokhoz",
        description_en="Boost factor for controllable entities",
        ge=0.0,
        le=1.0,
    )

    ranking_readable_boost: float = Field(
        default=0.1,
        env="RANKING_READABLE_BOOST",
        title_hu="Olvasható entitás boost",
        title_en="Readable Entity Boost",
        description_hu="Boost faktor érzékelőkhöz",
        description_en="Boost factor for sensors",
        ge=0.0,
        le=1.0,
    )

    ranking_active_sensor_boost: float = Field(
        default=2.0,
        env="RANKING_ACTIVE_SENSOR_BOOST",
        title_hu="Aktív érzékelő boost",
        title_en="Active Sensor Boost",
        description_hu="Boost faktor aktív érzékelőkhez",
        description_en="Boost factor for active sensors",
        ge=0.0,
        le=5.0,
    )

    ranking_unavailable_penalty: float = Field(
        default=-0.5,
        env="RANKING_UNAVAILABLE_PENALTY",
        title_hu="Nem elérhető büntetés",
        title_en="Unavailable Penalty",
        description_hu="Büntetés faktor nem elérhető érzékelőkhöz",
        description_en="Penalty factor for unavailable sensors",
        ge=-2.0,
        le=0.0,
    )

    # Additional network timeouts
    http_timeout_short: float = Field(
        default=5.0,
        env="HTTP_TIMEOUT_SHORT",
        title_hu="Rövid HTTP időtúllépés",
        title_en="Short HTTP Timeout",
        description_hu="Gyors HTTP kérések időtúllépése (pl. állapot lekérdezés)",
        description_en="Fast HTTP requests timeout (e.g. state queries)",
        ge=1.0,
        le=30.0,
    )

    http_timeout_medium: float = Field(
        default=15.0,
        env="HTTP_TIMEOUT_MEDIUM",
        title_hu="Közepes HTTP időtúllépés",
        title_en="Medium HTTP Timeout",
        description_hu="Közepes HTTP kérések időtúllépése (pl. embedding generálás)",
        description_en="Medium HTTP requests timeout (e.g. embedding generation)",
        ge=5.0,
        le=60.0,
    )

    http_timeout_long: float = Field(
        default=60.0,
        env="HTTP_TIMEOUT_LONG",
        title_hu="Hosszú HTTP időtúllépés",
        title_en="Long HTTP Timeout",
        description_hu="Hosszú HTTP kérések időtúllépése (pl. nagy adatátvitel)",
        description_en="Long HTTP requests timeout (e.g. large data transfer)",
        ge=30.0,
        le=600.0,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_prefix="",  # No prefix for environment variables
        extra="ignore",  # Ignore extra fields from .env temporarily
    )

    def __getattr__(self, name: str):
        """Fallback for missing attributes - provides defaults for legacy compatibility"""
        fallback_values = {
            "state_cache_maxsize": 1024,
            "state_cache_ttl": 30,
            "conversation_cache_maxsize": 100,
            "entity_score_cache_maxsize": 1000,
            "entity_context_cache_maxsize": 500,
            "conversation_aliases_ttl": 600,
            "entity_reranker_cache_ttl": 300,
            "service_cache_ttl": 21600,
            "http_timeout_short": 5.0,
            "http_timeout_medium": 15.0,
            "http_timeout_long": 60.0,
            "log_stream_max_timeout": 300,
            "ha_url": None,
            "ha_token": None,
            "conversation_memory_ttl": 15,
            "influx_url": None,
            "influx_org": "homeassistant",
            "influx_bucket": "homeassistant",
            "influx_db": "homeassistant",
            "influx_user": None,
            "debug": False,
            "log_level": "INFO",
            "ha_rag_log_level": "INFO",
            "log_file": None,
            "skip_arango_healthcheck": False,
            "gemini_output_dim": 1536,
        }

        if name in fallback_values:
            return fallback_values[name]

        # If it's an environment variable, try to get from os.environ
        env_value = os.getenv(name.upper())
        if env_value is not None:
            return env_value

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    @classmethod
    def get_field_metadata(cls) -> Dict[str, Dict[str, Any]]:
        """Extract all field metadata for admin UI rendering.

        Returns comprehensive field information including translations,
        validation rules, sensitivity flags, and restart requirements.
        """
        # Field categorization mapping
        field_categories = {
            "database": [
                "arango_url",
                "arango_user",
                "arango_pass",
                "arango_db",
                "embed_dim",
                "auto_bootstrap",
            ],
            "embedding": [
                "embedding_backend",
                "sentence_transformer_model",
                "embedding_cpu_threads",
                "openai_api_key",
                "gemini_api_key",
                "gemini_base_url",
                "gemini_output_dim",
            ],
            "performance": [
                "state_cache_maxsize",
                "conversation_cache_maxsize",
                "entity_score_cache_maxsize",
                "entity_context_cache_maxsize",
                "state_cache_ttl",
                "conversation_aliases_ttl",
                "entity_reranker_cache_ttl",
                "service_cache_ttl",
            ],
            "network": [
                "http_timeout",
                "http_timeout_short",
                "http_timeout_medium",
                "http_timeout_long",
            ],
            "home_assistant": [
                "ha_url",
                "ha_token",
                "conversation_memory_ttl",
                "influx_url",
                "influx_org",
                "influx_bucket",
                "influx_db",
                "influx_user",
            ],
            "debug": [
                "debug",
                "log_level",
                "ha_rag_log_level",
                "log_file",
                "skip_arango_healthcheck",
            ],
            "cross_encoder": [
                "cross_encoder_model",
                "cross_encoder_scale_factor",
                "cross_encoder_offset",
                "cross_encoder_enable_caching",
            ],
            "entity_ranking": [
                "ranking_area_generic_boost",
                "ranking_area_specific_boost",
                "ranking_area_followup_multiplier",
                "ranking_domain_boost",
                "ranking_device_class_boost",
                "ranking_previous_mention_boost",
                "ranking_controllable_boost",
                "ranking_readable_boost",
                "ranking_active_sensor_boost",
                "ranking_unavailable_penalty",
            ],
            "security": ["admin_token"],
        }

        metadata = {}
        for category, field_names in field_categories.items():
            category_metadata = {}
            for field_name in field_names:
                if field_name in cls.model_fields:
                    field_info = cls.model_fields[field_name]

                    # Extract metadata from Field definition
                    field_extra = field_info.json_schema_extra or {}

                    # Get constraints from Field definition
                    constraints = {}
                    if hasattr(field_info, "metadata"):
                        for constraint in field_info.metadata:
                            if hasattr(constraint, "__dict__"):
                                constraint_dict = constraint.__dict__
                                for key, value in constraint_dict.items():
                                    if key in [
                                        "gt",
                                        "ge",
                                        "lt",
                                        "le",
                                        "min_length",
                                        "max_length",
                                    ]:
                                        constraints[key] = value

                    # Create comprehensive field metadata, preferring Field values over defaults
                    field_meta = {
                        "type": str(field_info.annotation),
                        "default": field_info.default,
                        "env_var": field_extra.get("env", field_name.upper()),
                        "title_hu": field_extra.get(
                            "title_hu", field_name.replace("_", " ").title()
                        ),
                        "title_en": field_extra.get(
                            "title_en", field_name.replace("_", " ").title()
                        ),
                        "description_hu": field_extra.get(
                            "description_hu", f"{field_name} beállítás"
                        ),
                        "description_en": field_extra.get(
                            "description_en", f"{field_name} setting"
                        ),
                        "recommendation_hu": field_extra.get("recommendation_hu"),
                        "recommendation_en": field_extra.get("recommendation_en"),
                        "example": field_extra.get("example"),
                        "is_sensitive": field_extra.get(
                            "is_sensitive",
                            "token" in field_name
                            or "pass" in field_name
                            or "key" in field_name,
                        ),
                        "restart_required": field_extra.get(
                            "restart_required",
                            field_name in ["embed_dim", "embedding_backend"],
                        ),
                        "constraints": constraints,
                    }
                    category_metadata[field_name] = field_meta
                else:
                    # Create basic metadata for fields not yet defined with Field()
                    field_meta = {
                        "type": "str",  # Default assumption
                        "default": None,
                        "env_var": field_name.upper(),
                        "title_hu": field_name.replace("_", " ").title(),
                        "title_en": field_name.replace("_", " ").title(),
                        "description_hu": f"{field_name} beállítás - Field() definíció szükséges a részletes leíráshoz",
                        "description_en": f"{field_name} setting - Field() definition needed for detailed description",
                        "is_sensitive": "token" in field_name
                        or "pass" in field_name
                        or "key" in field_name,
                        "restart_required": field_name
                        in ["embed_dim", "embedding_backend"],
                        "constraints": {},
                    }
                    category_metadata[field_name] = field_meta

            metadata[category] = category_metadata

        return metadata


# Global settings instance
settings = AppSettings()


def get_settings() -> AppSettings:
    """Get the global settings instance.

    Returns the application settings with all configuration categories.
    Used for dependency injection in FastAPI endpoints.
    """
    return settings


def reload_settings() -> AppSettings:
    """Reload settings from environment variables.

    Forces reload of all configuration from environment variables.
    Useful after configuration changes that require restart.
    """
    import os
    from pathlib import Path

    global settings

    # Manually reload .env file into os.environ
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Update environment variable
                    os.environ[key] = value

    # Create new settings instance with updated environment
    settings = AppSettings()
    return settings
