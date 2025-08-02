# 🚀 HA-RAG Bridge Production Deployment

Ez a fájl tartalmazza a teljes production stack indításához szükséges Docker Compose konfigurációt.

## 📋 Szolgáltatások

A stack a következő szolgáltatásokat tartalmazza:

- **🤖 Ollama** - Lokális LLM modellek futtatása
- **💬 Open WebUI** - Web-es felület az LLM-ekhez
- **🧠 MindsDB** - ML adatbázis
- **🔗 Gemini Proxy** - Google Gemini API proxy
- **🎯 LiteLLM** - Egységes LLM API proxy
- **🗄️ ArangoDB** - Vektoros adatbázis
- **🌉 HA-RAG Bridge** - Fő alkalmazás
- **📓 Jupyter** - Fejlesztői környezet

## 🛠️ Telepítés

### 1. Környezeti változók beállítása

```bash
# Másold le a példa fájlt
cp .env.example .env

# Szerkeszd meg a .env fájlt
nano .env
```

**Fontos változók:**

- `GEMINI_API_KEY` - Google Gemini API kulcs
- `HA_TOKEN` - Home Assistant hosszú élettartamú token
- `ARANGO_ROOT_PASSWORD` - ArangoDB jelszó
- `HA_URL` - Home Assistant URL címe

### 2. Meglévő volume-ok migrálása (opcionális)

Ha már van Portainer stack-ed, használd a migration script-et:

```bash
./migrate-volumes.sh
```

### 3. Stack indítása

```bash
# Teljes stack indítása
docker-compose -f docker-compose.prod.yml up -d

# Logok követése
docker-compose -f docker-compose.prod.yml logs -f

# Csak bizonyos szolgáltatások
docker-compose -f docker-compose.prod.yml up -d arangodb ha-rag-bridge
```

### 4. Szolgáltatások elérése

| Szolgáltatás  | URL                    | Leírás             |
| ------------- | ---------------------- | ------------------ |
| Open WebUI    | http://localhost:3000  | LLM web felület    |
| HA-RAG Bridge | http://localhost:8001  | Fő API             |
| ArangoDB      | http://localhost:8529  | Adatbázis admin    |
| LiteLLM       | http://localhost:4000  | LLM proxy          |
| MindsDB       | http://localhost:47334 | ML adatbázis       |
| Jupyter       | http://localhost:8888  | Notebook környezet |
| Ollama        | http://localhost:11434 | LLM API            |

## 🔧 Konfigurációs opciók

### Volume kezelés

**Új telepítés esetén:**

```yaml
volumes:
  ollama_data:
  arangodb_data:
```

**Meglévő volume-ok használata:**

```yaml
volumes:
  ollama_data:
    external: true
  arangodb_data:
    external: true
```

### GPU támogatás

Az Ollama szolgáltatás támogatja az NVIDIA GPU-kat:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

### Health check-ek

Minden szolgáltatás rendelkezik health check-kel:

```bash
# Szolgáltatások állapotának ellenőrzése
docker-compose -f docker-compose.prod.yml ps
```

## 🚨 Troubleshooting

### Gyakori problémák

**1. ArangoDB nem indul el**

```bash
# Ellenőrizd a jogosultságokat
docker-compose -f docker-compose.prod.yml logs arangodb

# Volume tisztítása (FIGYELEM: törlődnek az adatok!)
docker volume rm ha-rag-bridge_arangodb_data
```

**2. HA-RAG Bridge nem kapcsolódik Home Assistant-hoz**

```bash
# Ellenőrizd a token-t és URL-t
docker-compose -f docker-compose.prod.yml exec ha-rag-bridge env | grep HA_

# Logok ellenőrzése
docker-compose -f docker-compose.prod.yml logs ha-rag-bridge
```

**3. Ollama modellek letöltése**

```bash
# Belépés az Ollama konténerbe
docker-compose -f docker-compose.prod.yml exec ollama bash

# Modell letöltése
ollama pull llama2
ollama pull mistral
```

### Hasznos parancsok

```bash
# Stack leállítása
docker-compose -f docker-compose.prod.yml down

# Volume-okkal együtt (FIGYELEM: adatvesztés!)
docker-compose -f docker-compose.prod.yml down -v

# Szolgáltatás újraindítása
docker-compose -f docker-compose.prod.yml restart ha-rag-bridge

# Resource használat
docker stats

# Volume-ok mérete
docker system df -v
```

## 🔒 Biztonsági megfontolások

1. **Jelszavak**: Változtasd meg az alapértelmezett jelszavakat
2. **Hálózat**: Korlátozd a hozzáférést tűzfallal
3. **API kulcsok**: Használj erős, egyedi kulcsokat
4. **Backup**: Rendszeres adatmentés
5. **Frissítések**: Rendszeres image frissítések

## 📊 Monitoring

### Logok

```bash
# Összes szolgáltatás logjai
docker-compose -f docker-compose.prod.yml logs -f

# Specifikus szolgáltatás
docker-compose -f docker-compose.prod.yml logs -f ha-rag-bridge

# Log szűrés
docker-compose -f docker-compose.prod.yml logs -f | grep ERROR
```

### Metrics

A szolgáltatások health endpoint-jain keresztül monitorozhatóak:

- HA-RAG Bridge: `http://localhost:8001/health`
- LiteLLM: `http://localhost:4000/health`
- ArangoDB: `http://localhost:8529/_api/version`

## 🔄 Frissítések

```bash
# Image-ek frissítése
docker-compose -f docker-compose.prod.yml pull

# Újraindítás frissített image-ekkel
docker-compose -f docker-compose.prod.yml up -d
```

## 📦 Backup és Restore

### Volume backup

```bash
# ArangoDB backup
docker run --rm -v ha-rag-bridge_arangodb_data:/data -v $(pwd):/backup alpine tar czf /backup/arangodb-backup.tar.gz -C /data .

# Ollama backup
docker run --rm -v ha-rag-bridge_ollama_data:/data -v $(pwd):/backup alpine tar czf /backup/ollama-backup.tar.gz -C /data .
```

### Volume restore

```bash
# ArangoDB restore
docker volume create ha-rag-bridge_arangodb_data
docker run --rm -v ha-rag-bridge_arangodb_data:/data -v $(pwd):/backup alpine tar xzf /backup/arangodb-backup.tar.gz -C /data
```
