# HA RAG Bridge

This project syncs Home Assistant metadata into ArangoDB and provides a simple FastAPI service.

## Embedding Provider

Set `EMBEDDING_PROVIDER` to choose how text embeddings are created. Valid values:

- `local` – runs on CPU using the MiniLM model from the `sentence-transformers` package.
- `openai` – uses the OpenAI API with your `OPENAI_API_KEY`.
- `gemini` – uses Google's Gemini API via `GEMINI_API_KEY`.

### Gemini beágyazás (1 536 dim)

```
curl -X POST \ \
  -H "Authorization: Bearer $GEMINI_API_KEY" \
  "$GEMINI_BASE_URL/v1beta/models/gemini-embedding-001:embedText" \
  -d '{"texts":["hello"],"task_type":"RETRIEVAL_DOCUMENT","output_dimensionality":1536}'
```

Python:

```python
from scripts.embedding_backends import GeminiBackend

os.environ["GEMINI_API_KEY"] = "key"
backend = GeminiBackend()
vec = backend.embed(["hello"])[0]
```

The `GEMINI_OUTPUT_DIM` env can be set to 768 or 3072 to change the vector size.

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
curl -X POST /process-request -d '{"user_message":"Kapcsold fel a nappali lámpát"}'
```

## Process responses

Execute the returned tool-calls:

```bash
curl -X POST /process-response -d '{"id":"1","choices":[{"message":{"role":"assistant","content":"Felkapcsoltam a lámpát.","tool_calls":[{"id":"c1","type":"function","function":{"name":"homeassistant.turn_on","arguments":"{\"entity_id\":\"light.kitchen\"}"}}]}}]}'
```

## Add graph edge

```bash
curl -X POST :8000/graph/edge \
  -H 'Content-Type: application/json' \
  -d '{"_from":"area/nappali","_to":"area/etkezo","label":"area_adjacent"}'
```

## Manual ingest

Add device manuals to the graph:

```bash
poetry run python scripts/ingest_docs.py --file manuals/gree.pdf --device_id=gree_klima
```

After ingest you can ask for instructions, e.g.:

> "Hogyan tudom a Gree klímát Wi-Fi módba állítani?"

## InfluxDB integration

Enable the official *InfluxDB* addon in Home Assistant and create a read-only token.
Add the connection details to your `.env` file (see `.env.sample`) and run `docker-compose up -d influxdb` to start a local instance.

### Influx config & caching

- `INFLUX_MEASUREMENT=""`  # üres, ha a HA addon üres measurementre ír
- Cache TTL: 30 s (változtatható az env-ben)

### Service cache
The catalog of `/api/services` is fetched on first request and cached for 6 h
(configurable via `SERVICE_CACHE_TTL`).

### Quick demo
poetry run python demo.py "Hány fok van a nappaliban?"

## Architecture
![Architecture diagram](docs/architecture.svg)

- LiteLLM proxy forwards requests from OpenWebUI or the HA Conversation agent.
- `ha-rag-bridge` FastAPI exposes `/process-request` and `/process-response`.
- ArangoDB stores entity metadata and graph edges.
- InfluxDB keeps the latest state values.
- Home Assistant is accessed via REST and WebSocket APIs.

## Live demo

Run the demo locally (requires HA token and running services):

```bash
poetry run python demo.py "Kapcsold fel a nappali lámpát"
```

## Docker

```
# Lokális build tesztelése:
docker build -t ha-rag-bridge .
docker run -p 8000:8000 ha-rag-bridge
```
