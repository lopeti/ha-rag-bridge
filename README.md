# HA RAG Bridge

This project syncs Home Assistant metadata into ArangoDB and provides a simple FastAPI service.

## Embedding Provider

Set `EMBEDDING_PROVIDER` to choose how text embeddings are created. Valid values:

- `local` – runs on CPU using the MiniLM model from the `sentence-transformers` package.
- `openai` – uses the OpenAI API with your `OPENAI_API_KEY`.

