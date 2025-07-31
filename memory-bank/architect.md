# HA RAG Bridge: System Architect

## Overview

Ez a fájl tartalmazza a Home Assistant RAG Bridge projekt architekturális döntéseit és tervezési mintáit.

## Teljes Stack Architektúra

```
Felhasználó → Home Assistant → Extended OpenAI Conversation → LiteLLM Proxy → HA-RAG Bridge → ArangoDB
                                                                     ↓                ↑
                                                              OpenAI/Gemini/Ollama    InfluxDB
```

## Architectural Decisions

### 1. RAG-alapú Entitás Szűrés

**Döntés**: Retrieval Augmented Generation használata a releváns Home Assistant entitások kiválasztására
**Indoklás**: Az összes entitás beillesztése a promptba felesleges token fogyasztást és zajos válaszokat eredményez

### 2. LiteLLM Proxy Integráció

**Döntés**: LiteLLM hooks rendszeren keresztüli integráció
**Indoklás**: Egységes interfész különböző LLM szolgáltatókhoz, és real-time prompt optimalizálás

### 3. Multi-Backend Embedding Support

**Döntés**: Plugin architecture Local, OpenAI és Gemini embeddings támogatásával
**Indoklás**: Rugalmasság költség és teljesítmény optimalizálásban

### 4. Dual Database Strategy

**Döntés**: ArangoDB vektoros kereséshez, InfluxDB idősorokhoz
**Indoklás**: ArangoDB kiváló vektoros kereséshez és gráf kapcsolatokhoz, InfluxDB optimális idősor adatokhoz

## Design Considerations

### Performance & Scalability

- Vector index support required in ArangoDB
- Real-time sync with Home Assistant
- Multiple embedding backend support
- Scalable for large HA installations
- Development and production environments

### Integration Points

- LiteLLM hooks for real-time prompt modification
- Extended OpenAI Conversation component integration
- Tool execution modes (ha-rag-bridge, caller, both, disabled)
- WebSocket connections for real-time HA synchronization

### Cost Optimization

- Token usage minimization through relevant entity selection
- Local embedding options to reduce API costs
- Caching strategies for frequently accessed data

## Components

### 1. Home Assistant Extended OpenAI Conversation

HA integráció LLM-ekkel való beszélgetéshez

**Responsibilities:**

- Felhasználói kérdések fogadása
- LiteLLM proxy-n keresztüli kommunikáció
- HA entitások kontextusának biztosítása
- Tool hívások koordinálása

### 2. LiteLLM Proxy + HA-RAG Hooks

Proxy layer különböző LLM szolgáltatókhoz RAG képességekkel

**Responsibilities:**

- Egységes interfész OpenAI, Gemini, Ollama felé
- Real-time prompt optimization RAG hook-okkal
- Placeholder replacement ({{HA_RAG_ENTITIES}})
- Tool execution mode management

### 3. HA-RAG Bridge FastAPI Service

Main API service handling requests and orchestrating data flow

**Responsibilities:**

- HTTP API endpoints (/api/query, /api/execute_tool)
- WebSocket connections to HA
- RAG query processing
- Request/response handling
- Authentication and middleware

### 4. ArangoDB Vector Database

Vector database for metadata and graph relationships

**Responsibilities:**

- Store HA device metadata with embeddings
- Vector similarity search
- Graph edge relationships (device-area, device-type)
- Collection management (devices, areas, services, etc.)

### 5. InfluxDB Time-Series Database

Time-series database for state data

**Responsibilities:**

- Store device states over time
- Historical data queries
- State change tracking
- Performance metrics

### 6. Embedding Backends System

Pluggable embedding generation system

**Responsibilities:**

- Generate text embeddings for queries and entities
- Support multiple providers (Local/SentenceTransformers, OpenAI, Gemini)
- Vector dimension management (384 local, 1536 OpenAI, 768 Gemini)
- Cost optimization strategies

### 7. Bootstrap & Migration System

Database initialization and migration system

**Responsibilities:**

- Database schema setup
- Index creation (especially vector indexes)
- Data migration (e.g., \_meta → meta)
- Initial data population from HA
- Collection validation and cleanup

## Data Flow Architecture

### 1. Initial Setup Flow

```
HA Entities → WebSocket/REST → HA-RAG Bridge → Embedding Backend → ArangoDB (with vectors)
HA States → WebSocket → HA-RAG Bridge → InfluxDB
```

### 2. Query Processing Flow

```
User Question → HA → Extended OpenAI → LiteLLM Proxy → HA-RAG Hook
                                                            ↓
                                            Query → HA-RAG Bridge → ArangoDB Vector Search
                                                            ↓
                                            Relevant Entities ← ArangoDB
                                                            ↓
Modified Prompt ← LiteLLM ← HA-RAG Hook ← Formatted Response
         ↓
    LLM Provider (OpenAI/Gemini/Ollama) → Response → Extended OpenAI → HA → User
```

### 3. Tool Execution Flow (opcionális)

```
LLM Tool Call → LiteLLM → HA-RAG Bridge → HA Tool Execution → Result → LiteLLM → LLM
```

## Key Integration Points

### LiteLLM Hook Configuration

- `HA_RAG_PLACEHOLDER`: "{{HA_RAG_ENTITIES}}" (default)
- `HA_RAG_TOOL_EXECUTION_MODE`: "ha-rag-bridge" | "caller" | "both" | "disabled"
- `HA_RAG_API_URL`: HA-RAG Bridge endpoint

### Extended OpenAI Conversation Setup

- Custom prompt template with RAG placeholder
- Long-lived access token configuration
- Tool calling enablement

### Development Environment

- Docker Compose orchestration
- Auto-bootstrap on startup
- Hot reload during development
