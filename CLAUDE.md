# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Code Quality Standards

### Type Safety & MyPy Compliance
- **MANDATORY**: All new code MUST pass mypy type checking without errors
- **Type Annotations**: Every function, method, and variable MUST have proper type annotations
- **Exception Handling**: Always catch specific exceptions (`except ValueError:`, never bare `except:`)
- **Ruff & Black**: All code MUST pass ruff linting and black formatting

### CSS & Design System
- **NO INLINE STYLES**: Never use `style={{}}` - use design system classes
- **USE THEME VARIABLES**: Always use `bg-primary`, `text-success`, `border-destructive`, etc.
- **NO HARDCODED COLORS**: Never use `bg-blue-500` - use semantic colors only

### Visual Debugging
- **Screenshot Command**: `chromium --headless --screenshot=screenshots/tmp/filename.png URL`
- **Live Environment**: Admin UI at `http://192.168.1.105:8000/admin/ui/`

## Development Commands

### Environment Setup
- `make dev-up` - Development stack with debugpy + auto-reload
- `make dev-down` - Stop development stack
- `docker compose up -d` - Production stack (low CPU)
- `poetry install` - Install dependencies
- `poetry shell` - Activate virtual environment

### Frontend Development
⚠️ **MANDATORY AFTER UI CHANGES**: `cd frontend/admin-ui && npm run build`

### Database Management
- `ha-rag-bootstrap` - Bootstrap database collections and indexes
- `ha-rag-bootstrap --force` - Force recreate indexes on dimension mismatch

### Application
- `poetry run uvicorn app.main:app --reload` - Run FastAPI development server
- `poetry run pytest` - Run tests

### Admin UI
- **Access**: `http://localhost:8001` (when FastAPI server is running)
- **Key Pages**:
  - `/settings` - Configuration management with real-time connection testing
  - `/entities` - Entity browser with debugging tools
  - `/hook-debugger` - Real-time LiteLLM hook monitoring
  - `/monitoring` - Live log streaming and performance metrics

## Project Structure

```
ha-rag-bridge/
├── app/                          # FastAPI application
│   ├── services/                 # Service layer
│   ├── langgraph_workflow/       # LangGraph workflow implementation  
│   ├── routers/                  # FastAPI route handlers
│   └── middleware/               # Request middleware
├── ha_rag_bridge/                # Core library and CLI tools
├── scripts/                      # Standalone utility scripts
├── tests/                        # Test suite
├── config/litellm/               # LiteLLM configurations
├── frontend/admin-ui/            # React admin interface
└── deployments/                  # Docker Compose configurations
```

## Architecture Overview

Home Assistant RAG bridge that syncs HA metadata into ArangoDB and provides semantic search through FastAPI.

### Core Components

**FastAPI Application** (`app/main.py`)
- Main endpoints: `/process-request`, `/process-request-workflow` (LangGraph), `/process-response`
- Auto-bootstraps database on startup
- Multiple embedding backends: local (sentence-transformers), OpenAI, Gemini
- LangGraph workflow with conversation memory and diagnostics

**Database Layer** (`ha_rag_bridge/db/`)
- ArangoDB with vector indexes for semantic search
- Collections: `entity`, `cluster`, `conversation_memory`, `document`, `area`, `device`
- TTL indexes: 30-day retention, 15-minute conversation memory

**Query Processing Pipeline** (`app/services/rag/`)
- LLM-based query rewriting with coreference resolution
- Semantic expansion with Hungarian-English synonyms
- Cluster-first retrieval with vector fallback
- Multi-turn conversation memory with entity boosting

### Key Configuration

**Environment Variables**
- `ARANGO_URL`, `ARANGO_USER`, `ARANGO_PASS`, `ARANGO_DB` - Database connection
- `HA_URL`, `HA_TOKEN` - Home Assistant API access
- `EMBEDDING_BACKEND` - "local", "openai", "gemini"
- `OPENAI_API_KEY`, `GEMINI_API_KEY` - API credentials when needed

### Current Status

**Production Features** ✅ LIVE
- **LangGraph Workflow**: Phase 3 production system with `/process-request-workflow` endpoint
- **LiteLLM Integration**: OpenWebUI-compatible hook with real-time entity context injection  
- **Hook Debugger**: Live monitoring system for LiteLLM interactions in admin UI
- **Conversation Memory**: 15-minute TTL entity persistence with multi-turn context enhancement
- **Cluster-based RAG**: Semantic entity clustering with intelligent scope detection
- **Bilingual System**: Hungarian UI with English embeddings for better semantic consistency
- **Advanced Configuration**: Real-time connection testing and specialized admin components