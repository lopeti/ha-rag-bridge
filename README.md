# HA RAG Bridge

This project syncs Home Assistant metadata into ArangoDB and provides a simple FastAPI service.

## Embedding Provider

Set `EMBEDDING_PROVIDER` to choose how text embeddings are created. Valid values:

- `local` – runs on CPU using the MiniLM model from the `sentence-transformers` package.
- `openai` – uses the OpenAI API with your `OPENAI_API_KEY`.

Run `make migrate` to set up the database.

## Watch entity updates

Run the realtime watcher to ingest entity metadata whenever it changes:

```bash
python scripts/watch_entities.py
# add --debug for verbose output
```

## Process requests

Example usage:

```bash
curl -X POST http://localhost:8000/process-request \
    -H 'Content-Type: application/json' \
    -d '{"user_message":"Kapcsold le a nappali lámpát!"}'
```
