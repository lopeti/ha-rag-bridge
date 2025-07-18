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
curl -X POST /process-request -d '{"user_message":"Kapcsold fel a nappali lámpát"}'
```

## Process responses

Execute the returned tool-calls:

```bash
curl -X POST /process-response -d '{"id":"1","choices":[{"message":{"role":"assistant","content":"Felkapcsoltam a lámpát.","tool_calls":[{"id":"c1","type":"function","function":{"name":"homeassistant.turn_on","arguments":"{\"entity_id\":\"light.kitchen\"}"}}]}}]}'
```

## InfluxDB integration

Enable the official *InfluxDB* addon in Home Assistant and create a read-only token.
Add the connection details to your `.env` file (see `.env.sample`) and run `docker-compose up -d influxdb` to start a local instance.

### Influx config & caching

- `INFLUX_MEASUREMENT=""`  # üres, ha a HA addon üres measurementre ír
- Cache TTL: 30 s (változtatható az env-ben)
