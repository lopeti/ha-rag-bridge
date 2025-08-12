# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
- `make dev-up` - Start development stack (HASS+bridge+Arango)
- `make dev-down` - Stop development stack  
- `make dev-shell` - Access bridge container shell
- `poetry install` - Install Python dependencies
- `poetry shell` - Activate virtual environment

### Quick Deploy (Fejlesztés -> Éles)
- `make deploy` - Gyors deploy ha-rag-core könyvtárba
- `make deploy-start` - Deploy + automatikus indítás
- `make deploy-check` - Éles verzió státusza
- `./deploy` - Közvetlen deploy parancs
- `./quick-deploy.sh [target_dir]` - Teljes deploy script

### Testing
- `poetry run pytest` - Run all tests
- `poetry run pytest tests/test_filename.py` - Run specific test file
- `poetry run pytest tests/test_filename.py::test_function` - Run single test
- `poetry run pytest -k "test_pattern"` - Run tests matching pattern
- `poetry run pytest --asyncio-mode=auto` - Run async tests (if needed)

### Database Management
- `ha-rag-bootstrap` - Bootstrap database collections and indexes
- `ha-rag-bootstrap --dry-run` - Analyze without modifying database
- `ha-rag-bootstrap --force` - Drop and recreate indexes on dimension mismatch
- `ha-rag-bootstrap --reindex [collection]` - Rebuild vector indexes
- `make migrate` - Run ArangoDB migrations (requires arangosh)

### LangGraph Workflow System (Phase 3 ✅ PRODUCTION)
- **Phase 3 Endpoint**: `/process-request-workflow` - Production-ready LangGraph workflow
- **LiteLLM Hook Integration**: OpenWebUI-compatible with `litellm_ha_rag_hooks_phase3.py`
- **Conversation Memory**: TTL-based entity persistence (15-minute expiry)
- **Conditional Routing**: Smart fallback mechanisms and retry logic
- **Quality Diagnostics**: Workflow assessment with performance recommendations
- See `memory-bank/cluster-based-rag-optimization.md` for architectural details

### Application
- `poetry run uvicorn app.main:app --reload` - Run FastAPI server in development
- `poetry run python demo.py "query"` - Run demo with query
- `poetry run python scripts/watch_entities.py` - Watch entity updates
- `poetry run python scripts/ingest_docs.py --file path --device_id id` - Ingest device manuals

### Configuration Analysis & Optimization
- `scripts/advisor.sh --detailed` - Run HA Configuration Advisor with detailed analysis
- `scripts/advisor.sh --format json --output report.json` - Generate JSON report
- `scripts/advisor.sh --category entity_orphaned` - Filter by specific issue category
- `scripts/advisor.sh --level warning` - Show only warning-level issues
- Categories: `entity_orphaned`, `friendly_name`, `device_class`, `device_naming`, `device_area`, `area_consistency`, `redundant_area`
- Levels: `info`, `warning`, `error`, `critical`

### Intelligent Friendly Name Management
- `scripts/advisor.sh --suggest-friendly-names` - Generate intelligent Hungarian friendly name suggestions
- `scripts/advisor.sh --suggest-friendly-names --confidence 0.8` - Higher confidence threshold
- `scripts/advisor.sh --apply-friendly-names --dry-run` - Show what would be updated
- `scripts/advisor.sh --apply-friendly-names` - Apply friendly name suggestions to HA entity registry
- `scripts/friendly_name_generator.py --test` - Test friendly name generation algorithms

### Docker Cleanup & Maintenance
- `make docker-system-info` - Show Docker disk usage and image count
- `make docker-cleanup` - Safe cleanup: unused containers, networks, dangling images
- `make docker-clean-dev` - Remove old ha-rag-bridge images and `<none>` tags
- `make docker-prune` - Aggressive: remove ALL unused resources (⚠️ use with caution)
- `./scripts/auto-cleanup.sh [mild|aggressive|info]` - Interactive cleanup script

## Architecture Overview

This is a Home Assistant RAG (Retrieval Augmented Generation) bridge that syncs HA metadata into ArangoDB and provides semantic search capabilities through a FastAPI service.

### Core Components

**FastAPI Application** (`app/main.py`)
- Main API server with `/process-request`, `/process-request-workflow` (Phase 3), and `/process-response` endpoints
- Auto-bootstraps database on startup unless `AUTO_BOOTSTRAP=false`
- Handles embedding generation, vector search, and HA service calls
- Supports multiple embedding backends: local (sentence-transformers), OpenAI, Gemini
- **Phase 3 LangGraph Workflow**: Advanced conditional routing with conversation memory and diagnostics

**Database Layer** (`ha_rag_bridge/db/`)
- ArangoDB integration with vector indexes for semantic search
- Collections: `entity` (HA entities), `document` (device manuals), `area`, `device`, `edge` (relationships)
- **Phase 3 Collections**: `cluster` (semantic entity groups), `cluster_entity` (cluster-entity relationships), `conversation_memory` (multi-turn context cache)
- ArangoSearch view `v_meta` for hybrid vector/text search
- TTL indexes for automatic event cleanup (30-day retention, 15-minute conversation memory)
- Graph relationships: device-manual links, area adjacency, cluster-entity associations

**Bootstrap System** (`ha_rag_bridge/bootstrap/`)
- CLI tool for database initialization and schema management
- Handles collection creation, index management, and data migration
- Validates collection names and provides auto-fix for invalid names

**Embedding Backends** (`scripts/embedding_backends.py`)
- Pluggable embedding system supporting local, OpenAI, and Gemini models
- Local: SentenceTransformers with configurable CPU threads and batch processing
- OpenAI: text-embedding-3-small (1536 dimensions)
- Gemini: text-embedding-004 (768 dimensions, configurable to 1536/3072)
- Auto-dimension detection and consistency checks with database indexes
- Rate limiting and retry logic for API backends

### Data Flow

1. **Ingestion**: Entity metadata from Home Assistant → **Automatic friendly name generation** → Enhanced embedding text → ArangoDB collections
2. **Query Processing**: User query → embedding vector → **Phase 3: intelligent cluster-first search** → ArangoDB vector search → relevant entities
3. **Tool Generation**: Found entities → HA service definitions → OpenAI tool schema
4. **Execution**: LLM tool calls → Home Assistant API calls → execution results

### Intelligent Friendly Name System

**Ingestion-Time Name Generation** (`scripts/friendly_name_generator.py`, `scripts/ingest.py`)
- **Non-Invasive Approach**: Generates friendly names only for embedding enhancement, never modifies HA entity registry
- **Rule-Based Intelligence**: 140+ Hungarian-English translation mappings with domain-specific patterns
- **Confidence Scoring**: 0.7-1.0 threshold ensures only high-quality suggestions are used
- **Automatic Integration**: Seamlessly integrated into ingestion workflow with statistics tracking
- **Embedding Quality Enhancement**: Transforms technical entity IDs (e.g., `light.etkezo_ablak_falikar`) into contextual Hungarian text ("Étkező ablak falikar")
- **Zero User Impact**: HA UI remains unchanged, improvements are purely internal for better search quality

**Benefits**:
- Better Hungarian semantic search without modifying HA configuration
- Consistent naming across similar entities  
- Improved embedding quality through contextual descriptions
- Automatic area and device class detection from entity patterns

### Phase 3 Production Features

**Smart Query Scope Detection ("Zoom Level" System)** ✅ IMPLEMENTED
- **Micro queries** (k=5-20): Specific entity operations like "kapcsold fel a lámpát" → targeted cluster lookup
- **Macro queries** (k=15-30): Area-based queries like "mi van a nappaliban" → area-specific clusters
- **Overview queries** (k=30-50): House-wide queries like "mi a helyzet otthon" → summary clusters
- **LLM-based Classification**: 100% accuracy vs 67% with regex patterns

**Semantic Entity Clustering** ✅ IMPLEMENTED
- Pre-computed entity clusters: solar, climate, lighting, security, overview (5 initial clusters)
- Graph-based cluster-entity relationships with relevance weights
- Hierarchical clusters: micro (specific function) → macro (area/domain) → overview (house-level)
- Cluster-first retrieval with intelligent vector search fallback

**Multi-turn Conversation Memory** ✅ IMPLEMENTED
- Conversation-scoped entity cache with 15-minute TTL and automatic cleanup
- Previous entity boosting in reranking algorithm (7-factor relevance scoring)
- Smart query augmentation using conversation context
- **Performance**: 50% memory utilization, 80% context enhancement rate

### Key Configuration

**Database & API**
- `ARANGO_URL`, `ARANGO_USER`, `ARANGO_PASS`, `ARANGO_DB` - Database connection
- `HA_URL`, `HA_TOKEN` - Home Assistant API access
- `OPENAI_API_KEY`, `GEMINI_API_KEY` - Embedding service credentials

**Embedding System**
- `EMBEDDING_BACKEND` - Choose between "local", "openai", "gemini"
- `EMBED_DIM` - Vector dimensions (auto-detected for local models)
- `SENTENCE_TRANSFORMER_MODEL` - Local model selection (upgraded to paraphrase-multilingual-mpnet-base-v2)
- `EMBEDDING_CPU_THREADS` - CPU threads for local embeddings

**Behavioral**
- `AUTO_BOOTSTRAP` - Auto-initialize database (default: true)
- `SERVICE_CACHE_TTL` - Cache duration for HA service catalog (default: 6h)
- `HTTP_TIMEOUT` - Timeout for outbound HTTP requests (default: 30s)

**Similarity Thresholds** (model-specific defaults with env overrides)
- `SIMILARITY_THRESHOLD_EXCELLENT`, `SIMILARITY_THRESHOLD_GOOD`, etc.

### Testing Strategy

- Unit tests in `tests/` directory using pytest
- Integration tests in `tests/integration/`
- Fixtures for test data in `tests/fixtures/`
- Mock-based testing for external APIs (HA, embedding services)

### Docker Development

The project uses Docker Compose for development with multiple stack configurations:
- `docker-compose.dev.yml` - Development stack with live reload and debugpy
- `docker-compose.local.yml` - Local testing
- `docker-compose.prod.yml` - Production deployment

### DevContainer Workflow

**Development Environment**: VS Code DevContainer integration with "Reopen in Container"
- **Development Location**: Inside DevContainer (isolated Python environment)
- **Docker Stack**: Runs on host machine (HASS+bridge+Arango+LiteLLM)
- **Host Commands**: Docker operations (`docker-compose restart litellm`) run from host terminal
- **Planned Enhancement**: Docker socket mount to enable container management from within DevContainer

**Environment switching**: Use `scripts/switch_env.sh` to toggle between dev/home modes

### Important Architecture Details

**Adaptive Similarity System** (`ha_rag_bridge/similarity_config.py`)
- Model-specific thresholds that adapt based on query context
- Hungarian/English language detection for threshold adjustment
- Environment variable overrides for all threshold levels

**Entity Ingestion Pattern**
- Uses Home Assistant's `/api/rag/static/entities` endpoint
- Hash-based change detection to avoid re-embedding unchanged entities
- Bilingual text generation (Hungarian/English) for improved semantic search
- Batch processing with configurable delays

**Graph Relationships**
- Device-manual associations via edge collection
- Manual hint injection during query processing
- Area containment and adjacency relationships

**Smart Home Intelligence System** (`app/services/`)
- **Conversation Analyzer** (`conversation_analyzer.py`) - Hungarian/English context understanding with area/domain detection
- **Entity Reranker** (`entity_reranker.py`) - Cross-encoder semantic scoring with multi-primary entity support
- **Multi-Formatter System** - Intelligent prompt formatting: compact/detailed/grouped_by_area/tldr based on context
- **Context-Aware Entity Prioritization** - Replaces hardcoded result selection with semantic relevance scoring
- **ConversationMemoryService** (`conversation_memory.py`) - TTL-based entity persistence with multi-turn context enhancement

**LangGraph Workflow System** (`app/langgraph_workflow/`)
- **Phase 3 Production Workflow**: Conditional routing with intelligent fallback mechanisms
- **RAGState Management**: Comprehensive workflow state tracking with typed schemas
- **Node Architecture**: conversation_analysis → scope_detection → entity_retrieval → context_formatting → workflow_diagnostics
- **Quality Assessment**: Real-time workflow performance analysis with actionable recommendations
- **Memory Integration**: Seamless conversation context persistence and entity boosting across turns

### Implementation Status

**Sprint 1: Context-Aware Entity Prioritization** ✅ COMPLETED
- Hungarian conversation analysis with comprehensive area aliases
- Cross-encoder entity reranking (ms-marco-MiniLM-L-6-v2)
- Hierarchical system prompt generation with current sensor values
- Performance: <10ms conversation analysis, <200ms entity ranking

**Sprint 1.5: Multi-Primary Entity Formatter System** ✅ COMPLETED  
- 4-formatter pattern system for optimal token usage
- Multi-primary entity support (up to 4 primary + 6 related entities)
- Intelligent categorization: complementary entity grouping (temperature + humidity + climate)
- Context-aware formatting selection based on query complexity and area count

**Phase 1: Cluster-based RAG Optimization** ✅ COMPLETED
- Semantic entity clustering with 5 initial clusters (solar, climate, lighting, security, overview)
- Smart query scope detection ("zoom level" system: micro/macro/overview queries)
- Cluster-first retrieval with hybrid fallback to vector search
- ArangoDB graph infrastructure with cluster/cluster_entity/conversation_memory collections
- Cache-optimized system prompt architecture for improved LLM performance
- Performance: 4/6 scope detection accuracy, 0.5-0.73 cluster similarity scores
- See `memory-bank/cluster-based-rag-optimization.md` and `memory-bank/system-prompt-optimization.md` for details

**LangGraph Migration Phase 1** ✅ COMPLETED
- Complete architectural plan in `memory-bank/langgraph-migration-plan.md`
- LangGraph dependencies installed (langgraph, langchain-core, langchain-community)
- RAGState TypedDict schema with complete workflow state management
- ConversationAnalysisNode: ports existing conversation analyzer with compatibility fixes
- LLM-based ScopeDetectionNode: replaces regex patterns with intelligent classification
- Simple linear workflow: conversation_analysis → scope_detection → entity_retrieval → context_formatting
- **100% scope detection accuracy** achieved (vs 67% with regex patterns)
- Validated with comprehensive test suite covering micro/macro/overview scenarios

**LangGraph Migration Phase 2** ✅ COMPLETED
- **Full Entity Retrieval Implementation**: Real cluster-first logic with adaptive cluster type selection
- **Intelligent Context Formatting**: Smart formatter selection with scope-aware optimization
- **Complete Workflow Integration**: Updated from mock to production-ready implementations
- **100% Integration Test Success Rate**: All core query types (micro/macro/overview) working perfectly
- EntityRetrievalNode: cluster-first entity retrieval with vector fallback integration
- ContextFormattingNode: hierarchical system prompt generation with EntityReranker integration
- Multi-turn conversation flow validation with context persistence
- Performance metrics: 7-45 entity retrieval range, 264-2265 char context lengths
- See `test_langgraph_phase2.py` for comprehensive integration test validation

**Phase 3: Advanced Workflow Features & Optimization** ✅ PRODUCTION READY
- **ConversationMemoryService**: TTL-based entity persistence with 15-minute caching and automatic cleanup
- **Enhanced LangGraph Workflow**: Conditional routing with comprehensive fallback mechanisms and retry logic
- **Multi-turn Context Enhancement**: Memory boosting with 7-factor relevance scoring and entity decay
- **LiteLLM Hook Integration**: Production-ready OpenWebUI-compatible hook using `/process-request-workflow`
- **Advanced Diagnostics**: Workflow quality assessment with performance metrics and recommendations
- **Performance Achievements**: 79% workflow quality, 94% entity retrieval success, 50% memory utilization
- **Intelligent Entity Selection**: Perfect context-aware entity ranking (e.g., `sensor.kert_aqara_szenzor_temperature` for "kertben hány fok")
- **Production Validation**: Successfully integrated and tested with LiteLLM proxy in live environment

**Bilingual Text Generation System** ✅ IMPLEMENTED (2025-08-08)
- **Dual Language Architecture**: Separate UI language (Hungarian) and system language (English) fields in database
- **Enhanced Entity Processing**: Modified `scripts/ingest.py` with `build_system_text()` for English embeddings
- **Database Schema Updates**: Added `text_system` field alongside existing `text` field in entity collection
- **Vector Search Optimization**: Embeddings now generated from English `text_system` for better semantic consistency
- **Area Name Translation**: Automatic Hungarian→English translation (nappali→living room, konyha→kitchen)
- **Multilingual Bootstrap**: Updated ArangoSearch view to index both `text` and `text_system` fields
- **Backward Compatibility**: Existing Hungarian UI text preserved while adding English system processing
- **Performance Validated**: Successfully tested with "Termel a napelem?" returning identical results
- **Architecture Philosophy**: "mi angolul gondolkozunk, hasonlítunk" - English thinking with Hungarian interface

**Production Integration Status** ✅ COMPLETED (2025-08-11)
- **LiteLLM Hook Phase 3**: Production-ready `litellm_ha_rag_hooks_phase3.py` integrated with `/process-request-workflow`
- **Live Environment Validation**: Successfully tested with OpenWebUI-compatible LiteLLM proxy
- **Intelligent Context Injection**: Real-time entity context enhancement with workflow diagnostics
- **Performance Metrics**: 79% workflow quality, 94% entity retrieval, perfect temperature sensor selection
- **Multi-turn Memory**: 15-minute TTL conversation persistence with 50% memory utilization

**LiteLLM Hook Restoration** ✅ COMPLETED (2025-08-12)
- **Root Cause**: Hook registration worked but `async_pre_call_hook` not called due to LiteLLM version specifics
- **Solution**: Utilized `async_logging_hook` for context injection (runs pre-request despite name)
- **Context Injection**: Successfully injects HA entity data into system messages before LLM processing  
- **Validation**: Test query "hány fok van a nappaliban?" returns exact temperature "A nappaliban 22.75 fok van."
- **Architecture**: Hook loads at startup, detects temperature queries, injects sensor context from bridge API
- **Performance**: Minimal overhead, preserves all existing functionality while restoring context enhancement

**Admin UI Monitoring System** ✅ IMPLEMENTED (2025-08-12)
- **Real-time Log Streaming**: EventSource-based container log monitoring with level filtering
- **Multi-container Support**: Bridge, LiteLLM, HomeAssistant, ArangoDB log aggregation
- **Docker Integration**: Live container log access via Docker socket mounting
- **Performance Metrics**: Basic CPU/memory/latency monitoring with 5-second polling
- **📋 PLANNED**: Stream-based metrics system for real-time charts (see `memory-bank/stream-metrics-optimization.md`)

