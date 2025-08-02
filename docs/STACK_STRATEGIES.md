# 🎯 HA-RAG Stack Strategies

## 📊 Core vs Full Stack Comparison

| Komponens         | Core Stack | Full Stack | Indoklás                      |
| ----------------- | ---------- | ---------- | ----------------------------- |
| **ArangoDB**      | ✅ Benne   | ✅ Benne   | Kötelező - vektoros adatbázis |
| **HA-RAG Bridge** | ✅ Benne   | ✅ Benne   | Kötelező - fő alkalmazás      |
| **LiteLLM**       | ✅ Benne   | ✅ Benne   | Szükséges - custom hooks      |
| **Open WebUI**    | ❌ Külön   | ✅ Benne   | Stock verzió jó               |
| **Ollama**        | ❌ Külön   | ✅ Benne   | Stock verzió jó               |
| **MindsDB**       | ❌ Külön   | ✅ Benne   | Opcionális ML tool            |
| **Jupyter**       | ❌ Külön   | ✅ Benne   | Dev tool, nem prod            |
| **Gemini Proxy**  | ❌ Nincs   | ✅ Benne   | LiteLLM helyettesíti          |

## 🎯 HA-RAG Core Stack

### Tartalom:

- **ArangoDB** - Vektoros adatbázis
- **HA-RAG Bridge** - Core alkalmazás
- **LiteLLM** - API proxy custom hook-okkal

### Előnyök:

- ✅ **Egyszerű** - csak 3 szolgáltatás
- ✅ **Gyors** - kevesebb resource igény
- ✅ **Karbantartható** - kevesebb moving part
- ✅ **Modular** - többi komponens külön telepíthető
- ✅ **Stabil** - kevesebb dependency

### Portok:

- **8000** - HA-RAG Bridge API
- **8529** - ArangoDB
- **4000** - LiteLLM API

## 🚀 Deployment stratégiák

### 1. 🎯 Minimalist Core Approach

```bash
# Core stack indítása
docker-compose -f docker-compose.core.yml up -d

# Stock komponensek külön
docker run -d -p 3000:8080 --name open-webui ghcr.io/open-webui/open-webui:latest
docker run -d -p 11434:11434 --name ollama ollama/ollama:latest
```

**Előnyök:**

- Független frissítések
- Kisebb blast radius
- Egyszerű troubleshooting

### 2. 🌟 Hybrid Approach

```bash
# Core stack
docker-compose -f docker-compose.core.yml up -d

# UI stack külön compose-al
docker-compose -f docker-compose.ui.yml up -d
```

### 3. 🏗️ Full Stack Approach

```bash
# Minden egyben
docker-compose -f docker-compose.prod.yml up -d
```

## 🤔 Melyiket válaszd?

### Válaszd a **Core Stack-et** ha:

- ✅ Egyszerűségre törekszel
- ✅ Csak a RAG funkcionalitás kell
- ✅ Saját UI-od van
- ✅ Minimális resource használat
- ✅ Könnyű karbantartás

### Válaszd a **Full Stack-et** ha:

- ✅ Komplett megoldás kell
- ✅ Minden integrálva legyen
- ✅ Nem akarsz külön komponensekkel foglalkozni
- ✅ Fejlesztői eszközök kellenek

## 📦 Komponens érvelés

### 🔥 **Kötelező komponensek (Core)**

**ArangoDB**

- Egyedi vektoros indexelés
- Graph capabilities
- Multi-model adatbázis
- ❌ **Nem** helyettesíthető stock-al

**HA-RAG Bridge**

- Egyedi Home Assistant integráció
- Custom embedding pipeline
- Specific API endpoints
- ❌ **Nem** helyettesíthető stock-al

**LiteLLM**

- Custom HA-RAG hooks
- Specific routing logic
- Request preprocessing
- ❌ **Nem** helyettesíthető stock-al (hook miatt)

### 💚 **Opcionális komponensek (Stock OK)**

**Open WebUI**

- Standard LLM chat interface
- ✅ Stock verzió tökéletes
- Külön telepíthető

**Ollama**

- Standard LLM serving
- ✅ Stock verzió tökéletes
- Külön telepíthető

**MindsDB**

- ML database functionality
- ✅ Stock verzió tökéletes
- Opcionális

## 🛠️ Core Stack használata

### Indítás:

```bash
# Environment setup
cp .env.core .env

# Core stack indítása
docker-compose -f docker-compose.core.yml up -d

# Ellenőrzés
curl http://localhost:8000/health
curl http://localhost:4000/health
curl http://localhost:8529/_api/version
```

### Stock komponensek hozzáadása:

```bash
# Open WebUI (külön)
docker run -d \
  --name open-webui \
  -p 3000:8080 \
  -e OPENAI_API_BASE_URL=http://host.docker.internal:4000/v1 \
  -v open-webui:/app/backend/data \
  ghcr.io/open-webui/open-webui:latest

# Ollama (külön)
docker run -d \
  --name ollama \
  -p 11434:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama:latest
```

## 📋 Javasolt megközelítés

**🎯 Core Stack + Stock komponensek külön**

1. **HA-RAG Core** - docker-compose.core.yml
2. **Open WebUI** - stock Docker image
3. **Ollama** - stock Docker image
4. **Egyéb tools** - igény szerint külön

**Előnyök:**

- Könnyű karbantartás
- Független frissítések
- Kisebb komplexitás
- Jobb hibakeresés
- Moduláris architektúra
