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

### Cluster-based RAG Development (Planned)
- **Phase 1**: Core cluster infrastructure - `cluster` and `cluster_entity` collections
- **Phase 2**: Adaptive scope detection - query classification and variable k-values  
- **Phase 3**: Conversation memory - multi-turn context with TTL-based entity caching
- See `memory-bank/cluster-based-rag-optimization.md` for detailed implementation plan

### Application
- `poetry run uvicorn app.main:app --reload` - Run FastAPI server in development
- `poetry run python demo.py "query"` - Run demo with query
- `poetry run python scripts/watch_entities.py` - Watch entity updates
- `poetry run python scripts/ingest_docs.py --file path --device_id id` - Ingest device manuals

## Architecture Overview

This is a Home Assistant RAG (Retrieval Augmented Generation) bridge that syncs HA metadata into ArangoDB and provides semantic search capabilities through a FastAPI service.

### Core Components

**FastAPI Application** (`app/main.py`)
- Main API server with `/process-request` and `/process-response` endpoints
- Auto-bootstraps database on startup unless `AUTO_BOOTSTRAP=false`
- Handles embedding generation, vector search, and HA service calls
- Supports multiple embedding backends: local (sentence-transformers), OpenAI, Gemini

**Database Layer** (`ha_rag_bridge/db/`)
- ArangoDB integration with vector indexes for semantic search
- Collections: `entity` (HA entities), `document` (device manuals), `area`, `device`, `edge` (relationships)
- **Planned**: `cluster` (semantic entity groups), `cluster_entity` (cluster-entity relationships), `conversation_memory` (multi-turn context cache)
- ArangoSearch view `v_meta` for hybrid vector/text search
- TTL indexes for automatic event cleanup (30-day retention)
- Graph relationships: device-manual links, area adjacency, planned cluster-entity associations

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

1. **Ingestion**: Entity metadata from Home Assistant → ArangoDB collections
2. **Query Processing**: User query → embedding vector → **Planned: semantic cluster search** → ArangoDB vector search → relevant entities
3. **Tool Generation**: Found entities → HA service definitions → OpenAI tool schema
4. **Execution**: LLM tool calls → Home Assistant API calls → execution results

### Planned Enhancements (Cluster-based RAG Optimization)

**Smart Query Scope Detection ("Zoom Level" System)**
- **Micro queries** (k=5-10): Specific entity operations like "kapcsold fel a lámpát" → targeted cluster lookup
- **Macro queries** (k=15-30): Area-based queries like "mi van a nappaliban" → area-specific clusters
- **Overview queries** (k=30-50): House-wide queries like "mi a helyzet otthon" → summary clusters

**Semantic Entity Clustering**
- Pre-computed entity clusters for common use cases (solar performance, climate control, security)
- Graph-based cluster-entity relationships with relevance weights
- Hierarchical clusters: micro (specific function) → macro (area/domain) → overview (house-level)

**Multi-turn Conversation Memory**
- Conversation-scoped entity cache with 15-minute TTL
- Previous entity boosting in reranking algorithm
- Smart query augmentation using conversation context

### Key Configuration

**Database & API**
- `ARANGO_URL`, `ARANGO_USER`, `ARANGO_PASS`, `ARANGO_DB` - Database connection
- `HA_URL`, `HA_TOKEN` - Home Assistant API access
- `OPENAI_API_KEY`, `GEMINI_API_KEY` - Embedding service credentials

**Embedding System**
- `EMBEDDING_BACKEND` - Choose between "local", "openai", "gemini"
- `EMBED_DIM` - Vector dimensions (auto-detected for local models)
- `SENTENCE_TRANSFORMER_MODEL` - Local model selection
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
- VS Code integration: "Reopen in Container" for DevContainer workflow
- Environment switching: Use `scripts/switch_env.sh` to toggle between dev/home modes

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

**Phase 2: Conversation Memory & Multi-turn Enhancement** 📋 PLANNED
- TTL-based conversation entity persistence across turns
- Context-aware query augmentation with previous entity boosting
- Smart query augmentation using conversation history
- Dynamic cluster learning from usage patterns