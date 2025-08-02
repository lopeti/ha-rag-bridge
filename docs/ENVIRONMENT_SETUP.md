# 🔧 Environment Configuration Guide

Ez az útmutató segít megérteni, hogy mikor mit használj a környezeti változók kezeléséhez.

## 📁 Fájlok áttekintése

### `.env` fájlok (runtime konfiguráció)

- **`.env.example`** - Általános/production konfiguráció sablon
- **`.env.dev.example`** - Fejlesztői környezet külső szolgáltatásokkal
- **`.env.containerized.example`** - Fejlesztői környezet Docker szolgáltatásokkal

### `.devcontainer/*.json` fájlok (VS Code fejlesztői környezet)

- **`devcontainer.json`** - Alapértelmezett (home environment)
- **`devcontainer.json.dev`** - Containerized fejlesztés
- **`devcontainer.json.home`** - Home environment specifikus

## 🎯 Mikor mit használj?

### 🏠 Home Lab fejlesztés

```bash
# Külső Home Assistant és ArangoDB használata
cp .env.dev.example .env
```

**Szerkesztendő értékek:**

- `HA_URL=http://192.168.1.128:8123`
- `ARANGO_URL=http://192.168.1.105:8529`
- `HA_TOKEN=your_actual_token`

### 🐳 Containerized fejlesztés

```bash
# Docker Compose szolgáltatások használata
cp .env.containerized.example .env
```

**Automatikus értékek:**

- `HA_URL=http://homeassistant:8123`
- `ARANGO_URL=http://arangodb:8529`

### 🚀 Production deployment

```bash
# Production környezet
cp .env.example .env
```

**Biztonsági szempontok:**

- Erős jelszavak
- Valódi API kulcsok
- Megfelelő hálózati beállítások

## 📋 Változók szétválasztása

### ✅ `.env` fájlban legyen:

```bash
# Érzékeny adatok
GEMINI_API_KEY=secret_key
HA_TOKEN=long_lived_token
ADMIN_TOKEN=secure_token

# Környezetfüggő beállítások
HA_URL=http://192.168.1.128:8123
ARANGO_URL=http://192.168.1.105:8529
LOG_LEVEL=DEBUG

# Runtime paraméterek
HTTP_TIMEOUT=60
INGEST_BATCH_SIZE=10
```

### ✅ `devcontainer.json`-ban legyen:

```json
{
  "settings": {
    "python.defaultInterpreterPath": "/usr/local/bin/python",
    "editor.formatOnSave": true
  },
  "extensions": ["ms-python.python", "ms-python.vscode-pylance"]
}
```

### ❌ Kerülendő `devcontainer.json`-ban:

```json
// NE tedd ide - inkább .env-be!
"terminal.integrated.env.linux": {
  "ARANGO_URL": "http://192.168.1.105:8529",
  "HASS_URL": "http://192.168.1.128:8123"
}
```

## 🔄 Migrációs lépések

### 1. Válaszd ki a megfelelő template-et

```bash
# Home lab setup
cp .env.dev.example .env

# Containerized setup
cp .env.containerized.example .env

# Production setup
cp .env.example .env
```

### 2. Szerkeszd meg a .env fájlt

```bash
nano .env
# vagy
code .env
```

### 3. Ellenőrizd a devcontainer beállításokat

- A devcontainer fájlok már nem tartalmaznak hardcoded URL-eket
- Minden konfiguráció .env-ből jön

## 🛡️ Biztonsági best practice-ek

### Git kezelés

```bash
# .env fájl hozzáadása .gitignore-hoz (már benne van)
echo ".env" >> .gitignore

# Csak example fájlok kerüljenek git-be
git add .env.*.example
```

### Érzékeny adatok

- **Soha ne** commitolj valódi API kulcsokat
- Használj erős, egyedi jelszavakat
- Rendszeresen rotáld az API kulcsokat

### Környezetek szétválasztása

- **Dev**: `LOG_LEVEL=DEBUG`, gyenge jelszavak OK
- **Staging**: Valódi adatok, de test környezet
- **Prod**: Minden éles, maximális biztonság

## 🚨 Troubleshooting

### "Service not found" hibák

```bash
# Ellenőrizd a .env fájlt
cat .env | grep URL

# Docker network ellenőrzés
docker network ls
docker-compose ps
```

### Devcontainer nem látja a változókat

```bash
# Devcontainer rebuild
Ctrl+Shift+P -> "Dev Containers: Rebuild Container"

# .env fájl ellenőrzés
ls -la .env
```

### API kapcsolódási hibák

```bash
# URL-ek tesztelése
curl -I $HA_URL
curl -I $ARANGO_URL

# Token ellenőrzés
echo $HA_TOKEN | wc -c  # Hossz ellenőrzés
```
