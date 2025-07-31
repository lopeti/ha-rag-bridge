# System Patterns

## Architectural Patterns

- Pattern 1: Description

## Design Patterns

- Pattern 1: Description

## Common Idioms

- Idiom 1: Description

## Service Catalog Pattern

Service catalog pattern for managing cached service instances and dependencies with TTL-based expiration

### Examples

- /app/app/services/service_catalog.py
- Used in main.FastAPI app for SERVICE_CACHE_TTL configuration


## Plugin Architecture

Plugin-based embedding backend system allowing swapping between Local, OpenAI, and Gemini providers with consistent interface

### Examples

- /app/scripts/embedding_backends.py
- BaseEmbeddingBackend abstract class
- LocalBackend, OpenAIBackend, GeminiBackend implementations


## Auto-Bootstrap Pattern

Bootstrap system with automatic database initialization, schema setup, and conditional execution based on environment variables

### Examples

- /app/ha_rag_bridge/bootstrap/
- AUTO_BOOTSTRAP environment variable
- bootstrap() function in main.py
