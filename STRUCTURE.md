# HA-RAG-Bridge Project Structure

## Overview

This document describes the project structure after the comprehensive refactoring completed in August 2025. The structure is designed for maintainability, clear separation of concerns, and scalability.

## Root Directory (Clean & Essential Only)

The root directory contains only essential project files:

```
ha-rag-bridge/
├── .env -> config/environments/.env        # Symlink to environment config
├── CHANGELOG.md                           # Project changelog
├── CLAUDE.md                              # Claude Code instructions
├── Dockerfile                             # Container build instructions
├── Makefile                               # Development & deployment commands
├── README.md                              # Main project documentation
├── TODO.md                                # Current development tasks
├── alembic/                               # Database migration scripts
├── poetry.lock                            # Python dependency lock file
├── pyproject.toml                         # Python project configuration
└── ...
```

## Core Application Structure

### app/ - FastAPI Application
```
app/
├── main.py                                # FastAPI application entry point
├── schemas.py                             # Pydantic models
├── api/v1/endpoints/                      # API version management
├── core/                                  # Application core
│   ├── config.py                         # Configuration management
│   └── logging_config.py                 # Logging setup
├── db/                                    # Database layer
├── langgraph_workflow/                    # LangGraph workflow implementation
├── middleware/                            # Request middleware
├── routers/                              # FastAPI route handlers
│   ├── admin.py                          # Admin API endpoints
│   ├── graph.py                          # Graph API endpoints
│   └── ui.py                             # UI serving endpoints
├── schemas/                              # Additional schema definitions
└── services/                             # Service layer (functionally organized)
    ├── core/                             # Core services
    │   ├── service_catalog.py            # HA service catalog management
    │   ├── state_service.py              # State management
    │   └── workflow_tracer.py            # Workflow tracing
    ├── rag/                              # RAG-specific services
    │   ├── cluster_manager.py            # Semantic entity clustering
    │   ├── entity_reranker.py            # Cross-encoder entity ranking
    │   ├── query_expander.py             # Query expansion & synonyms
    │   ├── query_rewriter.py             # LLM-based query rewriting
    │   ├── query_scope_detector.py       # Query scope classification
    │   └── search_debugger.py            # Semantic search debugging
    ├── conversation/                     # Conversation handling
    │   ├── conversation_analyzer.py      # Hungarian conversation analysis
    │   ├── conversation_memory.py        # TTL-based entity persistence
    │   ├── conversation_summarizer.py    # LLM-based context summarization
    │   ├── async_conversation_enricher.py # Background enrichment
    │   ├── async_summarizer.py           # Fire-and-forget summarization
    │   └── quick_pattern_analyzer.py     # Fast pattern recognition
    └── integrations/                     # External system integrations
        └── embeddings/                   # Embedding system integration
            ├── backends.py               # Embedding backend implementations
            └── friendly_name_generator.py # Intelligent name generation
```

### ha_rag_bridge/ - Core Library & CLI
```
ha_rag_bridge/
├── bootstrap/                            # Database initialization
│   ├── cli.py                           # Bootstrap CLI
│   ├── naming.py                        # Entity naming logic
│   ├── plan.py                          # Bootstrap planning
│   └── plan_validator.py                # Plan validation
├── cli/                                 # Command-line interface
│   └── ingest.py                        # Ingestion CLI wrapper
├── db/                                  # Database layer
│   └── index.py                         # Index management
├── eval/                                # Evaluation & metrics
├── utils/                               # Utility functions
└── ...
```

## Configuration Management

### config/ - Centralized Configuration
```
config/
├── environments/                         # Environment-specific configurations
│   ├── .env                             # Production configuration
│   ├── .env.example                     # Example configuration
│   ├── .env.template                    # Comprehensive template
│   ├── .env.development                 # Development settings
│   ├── .env.testing                     # Test settings
│   └── ...                              # Other environment configs
├── examples/                            # Configuration examples
│   └── extended_openai_config_example.yaml
├── prompts/                             # LLM prompt templates
│   └── prompt_template_optimized.txt
├── docker/                              # Docker-specific configs
│   ├── nginx-dev.conf
│   └── uvicorn_log.ini
├── litellm/                             # LiteLLM integration
│   ├── hooks/                           # LiteLLM hooks
│   │   └── litellm_ha_rag_hooks_phase3.py
│   ├── backups/                         # Config backups
│   ├── litellm_config.yaml              # Main LiteLLM config
│   └── litellm_config_phase3.yaml       # Phase 3 configuration
├── langgraph.json                       # LangGraph configuration
└── language_patterns_core.yaml          # Language processing patterns
```

## Scripts Organization

### scripts/ - Organized by Purpose
```
scripts/
├── ingestion/                           # Data ingestion scripts
│   ├── ingest.py                        # Main ingestion script
│   ├── ingest_docs.py                   # Document ingestion
│   └── watch_entities.py                # Entity monitoring
├── analysis/                            # Analysis & advisory scripts
│   ├── advisor.sh                       # HA config advisor
│   ├── ha_config_advisor.py             # Python advisor implementation
│   └── test_cluster_rag.py              # Cluster RAG testing
├── maintenance/                         # System maintenance
│   ├── auto-cleanup.sh                  # Docker cleanup
│   ├── bootstrap_clusters.py            # Cluster initialization
│   └── init_arango.py                   # Database initialization
└── utilities/                           # Helper scripts
    ├── switch_env.sh                    # Environment switching
    ├── test-mcp-servers.sh              # MCP server testing
    └── test_cache_prompt.py             # Cache testing
```

## Frontend Structure

### frontend/ - User Interface
```
frontend/
└── admin-ui/                            # React admin interface
    ├── dist/                            # Built application (served by FastAPI)
    ├── src/
    │   ├── components/                  # React components
    │   │   ├── layout/                  # Layout components
    │   │   ├── pipeline/                # Pipeline debugging UI
    │   │   └── ui/                      # Reusable UI components
    │   ├── pages/                       # Application pages
    │   ├── lib/                         # Utilities & API client
    │   └── hooks/                       # React hooks
    ├── package.json                     # Node.js dependencies
    └── vite.config.ts                   # Vite build configuration
```

## Testing Organization

### tests/ - Comprehensive Test Suite
```
tests/
├── fixtures/                            # Test data & mocks
│   └── qa_pairs.json                    # Q&A test pairs
├── unit/                                # Unit tests (moved from root)
│   ├── test_embeddings.py               # Embedding system tests
│   ├── test_conversation_analyzer.py    # Conversation analysis tests
│   ├── test_entity_reranker.py          # Entity ranking tests
│   └── ...                              # Other unit tests
├── integration/                         # Integration tests
│   ├── hooks/                           # LiteLLM hook tests
│   └── test_signal.py                   # Signal handling tests
└── performance/                         # Performance & benchmarks
    ├── test_embedding_performance.py    # Embedding benchmarks
    ├── test_langgraph_phase3.py         # LangGraph workflow tests
    ├── test_vector_search.py            # Vector search performance
    └── ...                              # Other performance tests
```

## Development Tools

### tools/ - Development & Debugging Tools
```
tools/
├── debug/                               # Debugging utilities (moved from tests/)
│   ├── debug_memory_service.py          # Memory service debugging
│   ├── debug_vector_scores.py           # Vector scoring analysis
│   ├── debug_workflow.py                # Workflow debugging
│   ├── workflow_debugger_web.py         # Web-based debugger
│   └── ...                              # Other debug tools
├── examples/                            # Example code & demos
│   ├── demo.py                          # Basic demo
│   ├── demo_ingestion_friendly_names.py # Friendly name demo
│   └── ...                              # Other examples
└── migration/                           # Database migration tools
    ├── auto_migrate.py                  # Automated migration
    └── ...                              # Migration utilities
```

## Deployment Structure

### deployments/ - Deployment Configurations
```
deployments/
├── docker-compose/                      # Docker Compose configurations
│   ├── docker-compose.yml              # Main production compose
│   ├── docker-compose.dev.yml          # Development stack
│   ├── docker-compose.prod.yml         # Production stack
│   └── ...                              # Other compose files
└── scripts/                             # Deployment scripts (moved from root)
    ├── deploy                           # Main deploy script
    ├── quick-deploy.sh                  # Quick deployment
    ├── host-deploy.sh                   # Host deployment
    └── ...                              # Other deployment scripts
```

## Documentation

### docs/ - Project Documentation
```
docs/
├── architecture/                        # Architecture documentation
├── deployment/                          # Deployment guides
├── development/                         # Development guides
├── architecture.svg                     # Architecture diagram
└── ...                                 # Other documentation
```

## Supporting Directories

```
custom_components/                       # Home Assistant custom component
migrations/                              # ArangoDB migration scripts
monitoring/                              # Monitoring configuration (Grafana, Prometheus)
screenshots/                             # UI screenshots & debug images
└── archive/2025-08-22/                 # Archived screenshots from refactor
memory-bank/                             # Project memory & planning documents
notebooks/                               # Jupyter notebooks for experimentation
```

## Key Design Principles

### 1. Separation of Concerns
- **app/services/** - Business logic organized by domain (rag, conversation, integrations)
- **app/routers/** - HTTP request handling
- **app/core/** - Application configuration and utilities
- **ha_rag_bridge/** - Reusable library components

### 2. Configuration Management
- Centralized in **config/** directory
- Environment-specific configurations
- Template files for easy setup

### 3. Tool Organization
- **scripts/** - Organized by purpose (ingestion, analysis, maintenance, utilities)
- **tools/** - Development and debugging utilities
- **tests/** - Organized by type (unit, integration, performance)

### 4. Frontend Architecture
- Modern React application with TypeScript
- Component-based architecture
- Built-in design system with shadcn/ui

### 5. Deployment Ready
- Docker-based deployment
- Multiple environment support
- Organized deployment scripts

## Migration Notes

This structure was created through a comprehensive refactoring process:

1. **Phase 1-2 (Completed)**: Root directory cleanup, service architecture fixes
2. **Phase 3 (Completed)**: Configuration organization
3. **Phase 4 (Completed)**: Script organization by purpose
4. **Phase 5 (Completed)**: Test structure improvement
5. **Phase 6 (Completed)**: Documentation and final cleanup

Total tasks completed: **95/95** (100%)

All functionality preserved, no breaking changes, improved maintainability and developer experience.