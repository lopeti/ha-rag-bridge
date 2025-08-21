# Home Assistant RAG Bridge + LiteLLM Integráció: Használati Példa

Ez a dokumentum részletesen bemutatja a Home Assistant RAG Bridge és LiteLLM integráció használatát egy tipikus felhasználási folyamaton keresztül.

## 1. Telepítés és konfigurálás

Feltételezzük, hogy már telepítetted a rendszert a `INTEGRATION_GUIDE.md` dokumentumban leírtak szerint.

### 1.1 Szükséges komponensek

- Futó Home Assistant (pl. http://homeassistant:8123)
- Telepített `jekalmin/extended_openai_conversation` integráció
- Futó HA-RAG Bridge API (pl. http://ha-rag-bridge:8000)
- Futó LiteLLM proxy (pl. http://litellm:4000)
- Futó ArangoDB, feltöltve a Home Assistant entitásokkal

## 2. Használati példa: Nappali megvilágítás vezérlése

### 2.1 A felhasználó kérdést tesz fel a Home Assistant beszélgetés felületén

```
Felhasználó: Kapcsold be a nappali lámpát és állítsd 50%-ra a fényerőt
```

### 2.2 Home Assistant feldolgozás

1. A `extended_openai_conversation` integráció fogadja a kérdést
2. Összeállítja a promptot a konfigurációban megadott sablon alapján, beleértve a `{{HA_RAG_ENTITIES}}` placeholdert
3. Elküldi a promptot a LiteLLM proxy-nak

### 2.3 LiteLLM pre-processzor hook

1. A `litellm_pre_processor` hook azonosítja a `{{HA_RAG_ENTITIES}}` placeholdert
2. Kivonja a felhasználói kérdést: "Kapcsold be a nappali lámpát és állítsd 50%-ra a fényerőt"
3. Meghívja a HA-RAG Bridge API-t:
   ```
   POST http://ha-rag-bridge:8000/api/query
   {
     "question": "Kapcsold be a nappali lámpát és állítsd 50%-ra a fényerőt",
     "top_k": 5
   }
   ```

### 2.4 HA-RAG Bridge feldolgozás

1. A HA-RAG Bridge kiszámítja a kérdés embedding vektorát
2. ArangoDB-ben keresést végez a legközelebbi entitásokra
3. Visszaadja a releváns entitásokat, pl.:
   ````json
   {
     "relevant_entities": [
       {
         "entity_id": "light.living_room_main",
         "name": "Nappali fő lámpa",
         "state": "off",
         "attributes": {
           "brightness": 128,
           "color_mode": "brightness",
           "supported_features": 32
         },
         "aliases": ["nappali lámpa", "fő világítás"]
       },
       {
         "entity_id": "light.living_room_ambient",
         "name": "Nappali hangulatvilágítás",
         "state": "off",
         "attributes": {
           "brightness": 64,
           "color_mode": "brightness",
           "supported_features": 32
         },
         "aliases": ["hangulatvilágítás", "háttérfény"]
       }
     ],
     "formatted_content": "Available Devices (relevant to your query):\n```csv\nentity_id,name,state,aliases\nlight.living_room_main,Nappali fő lámpa,off,nappali lámpa/fő világítás\nlight.living_room_ambient,Nappali hangulatvilágítás,off,hangulatvilágítás/háttérfény\n```"
   }
   ````

### 2.5 LiteLLM pre-processzor hook (folytatás)

1. A hook beilleszti a formázott entitás listát a placeholder helyére
2. A végső prompt, ami az LLM-nek megy:

   ````
   Te egy hasznos Home Assistant asszisztens vagy. Segíthetsz a felhasználónak a kérdéseivel és az okosotthon vezérlésével.

   Az alábbi kontextus tartalmazza az otthoni eszközök információit:

   Available Devices (relevant to your query):
   ```csv
   entity_id,name,state,aliases
   light.living_room_main,Nappali fő lámpa,off,nappali lámpa/fő világítás
   light.living_room_ambient,Nappali hangulatvilágítás,off,hangulatvilágítás/háttérfény
   ````

   Használd ezt az információt a pontos válaszokhoz.

   ```

   ```

### 2.6 LLM feldolgozás

1. Az LLM (Ollama, OpenAI, stb.) feldolgozza a kérdést a releváns entitásokkal
2. Generál egy választ, amely tartalmazza a szükséges műveleteket is:
   ```json
   {
     "choices": [
       {
         "message": {
           "content": "Rendben, bekapcsolom a nappali fő lámpát és beállítom 50%-os fényerőre. Egy pillanat.",
           "tool_calls": [
             {
               "id": "call_123",
               "function": {
                 "name": "light.turn_on",
                 "arguments": "{\"entity_id\":\"light.living_room_main\",\"brightness\":128}"
               },
               "type": "function"
             }
           ]
         }
       }
     ]
   }
   ```

### 2.7 LiteLLM post-processzor hook

1. A `litellm_post_processor` hook azonosítja a tool hívásokat
2. Észleli a "light.turn_on" hívást a "light.living_room_main" entitásra
3. Elküldi a HA-RAG Bridge API-nak végrehajtásra:
   ```
   POST http://ha-rag-bridge:8000/api/execute_tool
   {
     "tool_calls": [
       {
         "id": "call_123",
         "function": {
           "name": "light.turn_on",
           "arguments": "{\"entity_id\":\"light.living_room_main\",\"brightness\":128}"
         },
         "type": "function"
       }
     ]
   }
   ```

### 2.8 HA-RAG Bridge tool végrehajtás

1. A HA-RAG Bridge API feldolgozza a tool hívást
2. Meghívja a Home Assistant API-t a megfelelő szolgáltatás végrehajtásához:
   ```
   POST http://homeassistant:8123/api/services/light/turn_on
   {
     "entity_id": "light.living_room_main",
     "brightness": 128
   }
   ```
3. Visszaadja a végrehajtás eredményét:
   ```json
   {
     "tool_execution_results": [
       {
         "tool_call_id": "call_123",
         "result": "success",
         "entity_id": "light.living_room_main",
         "new_state": "on"
       }
     ]
   }
   ```

### 2.9 LiteLLM post-processzor hook (folytatás)

1. A hook hozzáadja a végrehajtási eredményeket a válaszhoz
2. A kibővített válasz visszakerül a Home Assistanthoz

### 2.10 Home Assistant megjelenítés

1. A Home Assistant megjeleníti a választ a felhasználónak
2. A nappali lámpa bekapcsol 50%-os fényerővel

## 3. Előnyök a hagyományos megközelítéshez képest

1. **Optimalizált prompt**: Csak a releváns entitások kerültek a promptba (2 lámpa a nappaliban), nem az összes eszköz
2. **Pontos végrehajtás**: Az LLM a megfelelő entitás ID-t használta a művelet végrehajtásához
3. **Zökkenőmentes felhasználói élmény**: A felhasználó egyszerű nyelven kommunikálhatott, a rendszer lefordította a szükséges technikai műveletekre

## 4. Alternatív forgatókönyvek

### 4.1 Állapot lekérdezés

```
Felhasználó: Mennyi a hőmérséklet a nappaliban?
```

A rendszer ugyanazokat a lépéseket követi, de ebben az esetben a HA-RAG Bridge a nappali hőmérséklet érzékelőket adja vissza, és az LLM nem generál tool hívást, csak egyszerűen visszaadja az aktuális hőmérsékletet a promptban kapott információk alapján.

### 4.2 Komplex automáció

```
Felhasználó: Állíts be egy esti jelenetet, ami lekapcsolja a konyhában a lámpákat, bekapcsolja a nappali hangulatvilágítást és 22 fokra állítja a hálószoba termosztátját
```

Ebben az esetben a HA-RAG Bridge több különböző típusú entitást ad vissza (lámpák, termosztát), és az LLM több tool hívást generál, amelyeket a rendszer sorban végrehajt.

## 5. Következtetés

Ez a példa bemutatja, hogyan működik együtt a teljes rendszer, hogy intelligens, kontextus-alapú válaszokat adjon a felhasználónak, és végrehajtsa a szükséges műveleteket. A RAG megközelítés jelentősen javítja a rendszer teljesítményét, mivel csak a releváns információkat küldi el az LLM-nek, csökkentve a prompt méretét és javítva a válaszok minőségét.
