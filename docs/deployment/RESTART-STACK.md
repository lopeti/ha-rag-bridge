# Stack Újraindítási Utasítások

## Mi történt?
✅ Módosítottuk a `docker-compose.yml`-t:
- ❌ Eltávolítottuk az InfluxDB-t
- ✅ Hozzáadtuk a LiteLLM service-t (port 4000)
- ✅ Konfigurálás: `http://bridge:8000` → RAG hook

## Újraindítás szükséges!

### Opció 1: VS Code DevContainer
```
Ctrl+Shift+P → "Dev Containers: Rebuild Container"
```

### Opció 2: Docker Compose (host gépen)
```bash
docker compose down
docker compose up -d
```

### Opció 3: Portainer
1. Stack leállítása
2. Stack újraindítása

## Ellenőrzés újraindítás után:
```bash
# LiteLLM elérhető?
curl http://localhost:4000/health

# Hook teszt
python test_local_hook.py
```

## Várható eredmény:
- ❌ InfluxDB eltűnik (port 8086)
- ✅ LiteLLM megjelenik (port 4000)  
- ✅ Bridge továbbra is fut (port 8000)
- ✅ RAG hook működik helyben