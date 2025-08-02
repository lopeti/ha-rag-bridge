# 🔄 Portainer vs Docker Compose Migration Guide

## 📊 Összehasonlítás

| Szempont              | Portainer Stack | Docker Compose     |
| --------------------- | --------------- | ------------------ |
| **Kezelés**           | Web UI          | Parancssor/fájlok  |
| **Verziókövetés**     | ❌ Nehéz        | ✅ Git-friendly    |
| **Reprodukálhatóság** | ❌ Manuális     | ✅ Automatikus     |
| **Backup**            | Volume szintű   | Fájl + volume      |
| **CI/CD**             | ❌ Korlátozott  | ✅ Natív támogatás |
| **Hibakeresés**       | Web UI          | Logs + parancssor  |

## 📋 Migrációs lépések

### 🔒 AJÁNLOTT: Biztonságos átállás

```bash
# 1. Preparation
./migrate-from-portainer.sh

# 2. Test deployment (különböző portokkal)
docker-compose -f docker-compose.test.yml up -d

# 3. Tesztelés
curl http://localhost:8002/health  # HA-RAG Bridge test port
curl http://localhost:3001         # Open WebUI test port

# 4. Ha minden OK, átváltás
docker-compose -f docker-compose.test.yml down
# Portainerben stop stack
docker-compose -f docker-compose.prod.yml up -d
```

### ⚡ GYORS: Közvetlen csere

```bash
# 1. Backup volumes
docker run --rm -v ollama_data:/data -v $(pwd):/backup alpine tar czf /backup/ollama-backup.tar.gz -C /data .
docker run --rm -v arangodb_data:/data -v $(pwd):/backup alpine tar czf /backup/arangodb-backup.tar.gz -C /data .

# 2. Portainer stack stop (Portainer UI-ban)

# 3. Docker Compose start
docker-compose -f docker-compose.prod.yml up -d
```

## 🎯 Döntési kritériumok

### Használd a **Biztonságos átállást** ha:

- ✅ Éles rendszerről van szó
- ✅ Van időd tesztelni
- ✅ Fontos az adatbiztonság
- ✅ Szeretnéd összehasonlítani a teljesítményt

### Használd a **Gyors cserét** ha:

- ✅ Dev/test környezet
- ✅ Gyorsan akarsz átállni
- ✅ Van backup terved
- ✅ Tapasztalt vagy Docker-rel

## 🔧 Port mapping különbségek

### Portainer stack (jelenlegi):

- Open WebUI: 3000
- HA-RAG Bridge: 8001
- ArangoDB: 8529
- LiteLLM: 4000
- MindsDB: 47334, 47335
- Jupyter: 8888

### Docker Compose test (átmeneti):

- Open WebUI: **3001**
- HA-RAG Bridge: **8002**
- ArangoDB: **8530**
- LiteLLM: **4001**
- MindsDB: **47335, 47336**
- Jupyter: **8889**

### Docker Compose prod (végső):

- Ugyanazok a portok mint Portainer (átváltás után)

## ⚠️ Fontos figyelmeztetések

1. **API kulcsok**: A `.env.prod` fájlban lévő kulcsok élesek - ne commitold!
2. **Volume nevek**: Docker Compose `projektname_volumename` formátumot használ
3. **Network**: Docker Compose saját network-öt hoz létre
4. **Dependencies**: Docker Compose jobb dependency management-tel rendelkezik

## 🔍 Troubleshooting

### Volume problémák

```bash
# Volume lista
docker volume ls | grep -E "(ollama|arangodb|webui|mindsdb)"

# Volume inspect
docker volume inspect volume_name

# Volume használat
docker system df -v
```

### Port ütközések

```bash
# Port ellenőrzés
netstat -tulpn | grep :8001
ss -tulpn | grep :8001

# Service stop/start
docker-compose -f docker-compose.prod.yml stop service_name
docker-compose -f docker-compose.prod.yml start service_name
```

### Service health check

```bash
# Összes service status
docker-compose -f docker-compose.prod.yml ps

# Egyes service logok
docker-compose -f docker-compose.prod.yml logs -f ha-rag-bridge

# Health check
curl -f http://localhost:8001/health || echo "Service down"
```
