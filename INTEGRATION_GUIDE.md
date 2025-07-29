# Home Assistant RAG Bridge LiteLLM Integráció

Ez a dokumentáció leírja, hogyan integrálhatod a Home Assistant RAG Bridge-et a LiteLLM proxyn keresztül, hogy optimalizált promptokat készíts a jekalmin/extended_openai_conversation Home Assistant integrációhoz.

## Architektúra áttekintés

A rendszer a következő komponensekből áll:

1. **Home Assistant** - Smart home platform a eszközök és automatizálások kezeléséhez
2. **HA-RAG Bridge** - FastAPI alkalmazás, amely kérdések alapján releváns Home Assistant entitásokat keres
3. **ArangoDB** - Vektoros adatbázis a Home Assistant entitások és metaadatok tárolásához
4. **LiteLLM** - Proxy, amely egységes interfészt biztosít különböző LLM szolgáltatókhoz
5. **Ollama** - Lokális LLM modell futtatás (opcionális)
6. **extended_openai_conversation** - Home Assistant integráció LLM-ekkel való beszélgetéshez

Az adatfolyam a következő:

```
Felhasználó kérdés → Home Assistant → extended_openai_conversation → LiteLLM proxy
                                                                  ↓
           Válasz ← Home Assistant ← extended_openai_conversation ← LiteLLM proxy
                                                                  ↑
                         HA-RAG Bridge → ArangoDB (Entitás keresés)
```

## Előfeltételek

- Működő Home Assistant telepítés
- Docker és Docker Compose
- Long-Lived Access Token a Home Assistanthoz
- [jekalmin/extended_openai_conversation](https://github.com/jekalmin/extended_openai_conversation) telepítve a Home Assistantban

## Telepítés

### 1. Rendszer indítása Docker Compose-zal

```bash
# Állítsd be a HASS_TOKEN környezeti változót
export HASS_TOKEN="your_long_lived_access_token"

# Indítsd el a teljes rendszert
docker-compose -f docker-compose.full-stack.yml up -d
```

### 2. Inicializáld az ArangoDB-t és a grafikont

```bash
# Futtatd az inicializációs szkriptet
docker exec -it ha-rag-bridge python -m scripts.init_arango
```

### 3. Entitások importálása Home Assistantból

```bash
# Futtatd az ingesztálási szkriptet
docker exec -it ha-rag-bridge python -m scripts.ingest_entities
```

## Home Assistant konfiguráció

### extended_openai_conversation konfiguráció

Add hozzá a következő konfigurációt a `configuration.yaml` fájlhoz:

```yaml
extended_openai_conversation:
  - id: ha_rag_assistant
    name: Home Assistant RAG Assistant
    prompt: |-
      You are a helpful home assistant AI. You can answer questions and control the home.

      Use the given context about home devices to provide accurate information.

      {{HA_RAG_ENTITIES}}

      If there's a way to help using the available devices, suggest how to do it.
    api_key: !secret openai_api_key
    api_endpoint: "http://litellm:4000/v1" # A LiteLLM proxy címe
    temperature: 0.7
    max_tokens: 1000
    model: gpt-3.5-turbo # Ezt a LiteLLM átirányítja
    functions:
      # A HASS szolgáltatások definiálása
      - name: homeassistant.toggle
        description: Toggle a Home Assistant entity on or off
        parameters:
          type: object
          properties:
            entity_id:
              type: string
              description: The entity_id to toggle
          required:
            - entity_id
```

## LiteLLM Hook működése

A rendszer két fő LiteLLM hookot használ:

1. **Pre-processor hook** (`litellm_pre_processor`):

   - Azonosítja a rendszerüzenetekben a `{{HA_RAG_ENTITIES}}` placeholdert
   - Kivonja a felhasználói kérdést
   - Meghívja a HA-RAG Bridge API-t a releváns entitások lekéréséhez
   - Beilleszti a formázott entitáslistát a placeholder helyére

2. **Post-processor hook** (`litellm_post_processor`):
   - Ellenőrzi, hogy a válasz tartalmaz-e tool hívásokat
   - Azonosítja a Home Assistant műveleteket (pl. light.turn_on)
   - Továbbítja ezeket a műveleteket a HA-RAG Bridge API-nak végrehajtásra
   - Hozzáadja a végrehajtási eredményeket a válaszhoz

## Hibaelhárítás

### 1. Ellenőrizd a szolgáltatások működését

```bash
# Ellenőrizd, hogy minden konténer fut-e
docker-compose -f docker-compose.full-stack.yml ps

# Nézd meg a HA-RAG Bridge logokat
docker-compose -f docker-compose.full-stack.yml logs ha-rag-bridge

# Nézd meg a LiteLLM logokat
docker-compose -f docker-compose.full-stack.yml logs litellm
```

### 2. API elérhetőség tesztelése

```bash
# HA-RAG Bridge API tesztelése
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Kapcsold be a nappali lámpát", "top_k": 5}'

# LiteLLM proxy tesztelése
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "system", "content": "Segíts nekem. {{HA_RAG_ENTITIES}}"},
      {"role": "user", "content": "Kapcsold be a nappali lámpát"}
    ]
  }'
```

## Összegzés

Ezzel a konfigurációval a Home Assistant RAG Bridge optimalizálja a promptokat, hogy csak a kérdéshez releváns entitásokat tartalmazzák. A teljes rendszer Docker Compose-zal telepíthető és skálázható. A LiteLLM proxynak köszönhetően rugalmasan váltható a használt LLM szolgáltató, miközben egységes interface-en keresztül érhető el.
