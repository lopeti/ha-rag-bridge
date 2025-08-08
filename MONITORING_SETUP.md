# Monitoring Stack Setup - Development Guide

A Phase 3 LiteLLM hook-kal integrált Prometheus monitoring stack fejlesztési környezethez.

## Gyors Indítás

```bash
# 1. Monitoring stack indítása
make monitoring-up

# 2. Főszolgáltatás indítása monitoring-gal
make dev-up
```

## Elérhető Szolgáltatások

- **Prometheus**: http://localhost:9090 - Metrics collection és query
- **Grafana**: http://localhost:3001 - Visualization dashboard (admin/admin123)
- **Jaeger**: http://localhost:16686 - Distributed tracing (opcionális)
- **LiteLLM Metrics**: Port 4317 - Phase 3 hook metrics

## Monitoring Adatok

### LiteLLM Phase 3 Metrics
- `litellm_requests_total` - Összes request száma
- `litellm_request_duration` - Request response time
- `litellm_conversation_memory_hits` - Memory cache találatok
- `litellm_workflow_quality_score` - Phase 3 workflow minőség
- `litellm_cluster_retrieval_ratio` - Cluster-based retrieval arány

### HA-RAG Bridge Metrics  
- `ha_rag_entity_retrieval_count` - Entity lekérdezések
- `ha_rag_conversation_analysis_duration` - Beszélgetés analízis időtartama
- `ha_rag_memory_service_operations` - Memory service műveletek

## Fejlesztési Workflow

### 1. Alapvető Monitoring
```bash
# Prometheus indítása és alapmetrikák
make monitoring-up

# Grafana megtekintése
open http://localhost:3001
```

### 2. Debug Session
```bash
# Logok követése real-time
make monitoring-logs

# LiteLLM-specifikus logok  
docker logs -f litellm
```

### 3. Performance Optimalizálás
```bash
# Phase 3 workflow metrikák 
curl http://localhost:4317/metrics | grep litellm_workflow

# Memory service státusz
curl http://localhost:8000/admin/memory/stats
```

## Grafana Dashboardok

### Előre Konfigurált Panelok
- **Phase 3 Workflow Quality** - Workflow teljesítmény trending
- **Conversation Memory Usage** - Memory service kihasználtság  
- **Entity Retrieval Performance** - RAG retrieval metrikák
- **LiteLLM Hook Integration** - Hook működés monitoring

### Custom Queries
```promql
# Átlagos workflow minőség
avg(litellm_workflow_quality_score)

# Memory találati arány
rate(litellm_conversation_memory_hits[5m]) / rate(litellm_requests_total[5m])

# Cluster vs vector retrieval arány
litellm_cluster_retrieval_ratio
```

## DevContainer Integration

### Host Network Módban
A monitoring stack a host hálózaton fut, így a devcontainer-ből is elérhető minden szolgáltatás.

### Environment Variables
```bash
# LiteLLM hook konfiguráció  
PROMETHEUS_ENDPOINT=http://localhost:4317/metrics
JAEGER_ENDPOINT=http://localhost:14268/api/traces
```

## Troubleshooting

### Common Issues

1. **Port ütközések**: Grafana 3001-en fut a 3000-as port ütközés elkerülésére
2. **Network connectivity**: Biztosítsd, hogy a `ha-rag-network` létezik
3. **Metrics not appearing**: Ellenőrizd a prometheus.yml config-ot

### Debug Commands
```bash
# Network ellenőrzése
docker network ls | grep ha-rag

# Prometheus targets státusza
curl http://localhost:9090/api/v1/targets

# LiteLLM metrics elérhetősége
curl http://localhost:4317/metrics
```

## Production Considerations

### Security
- Grafana admin jelszó megváltoztatása
- Prometheus query API limitálás
- Network isoláció éles környezetben

### Storage
- Prometheus retention policy (jelenleg 7 nap)
- Grafana dashboard perzisztens tárolás
- Log rotation monitoring stack számára

### Alerting (Opcionális)
- Alertmanager integráció
- Phase 3 workflow quality alerts
- Memory service health checks