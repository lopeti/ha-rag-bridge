# HA-RAG Bridge integráció az Extended OpenAI Conversation-höz

Ez a dokumentáció leírja, hogyan lehet optimalizálni a [jekalmin/extended_openai_conversation](https://github.com/jekalmin/extended_openai_conversation) kezdeti promptját a `ha-rag-bridge` segítségével.

## Probléma

Az Extended OpenAI Conversation alapértelmezetten az összes Home Assistant entitást belefoglalja a promptba, ami:

1. Feleslegesen növeli a token felhasználást
2. Sok irreleváns információt ad az LLM-nek
3. Csökkenti a válaszok pontosságát, mivel az LLM "elvész" a sok entitás között

## Megoldás

A `ha-rag-bridge` egy Retrieval Augmented Generation (RAG) megközelítést használ a releváns entitások kiválasztására:

1. A felhasználó kérdésének beágyazása (embedding) készül
2. A kérdés vektorális hasonlóság alapján a legrelevánsabb entitások kiválasztásra kerülnek
3. Csak ezek a releváns entitások kerülnek be a promptba

## Implementációs lépések

### 1. Telepítés és beállítás

1. Telepítsd a `ha-rag-bridge`-et és futtatsd az entitás-adatok betöltését (`ingest` parancs)
2. Telepítsd az Extended OpenAI Conversation komponenst
3. Másold a `prompt_template_optimized.txt` fájlt a Home Assistant konfigurációs könyvtárába

### 2. Konfiguráció

#### Home Assistant konfiguráció

Add hozzá a következő konfigurációt a `configuration.yaml` fájlhoz:

```yaml
# HA-RAG Bridge integráció
shell_command:
  generate_rag_prompt: >-
    python3 /config/custom_scripts/generate_rag_prompt.py "{{ question }}" > /tmp/rag_prompt.txt

# A szenzor, ami a promptot olvassa
sensor:
  - platform: command_line
    name: "RAG Prompt Result"
    command: "cat /tmp/rag_prompt.txt"
    scan_interval: 5

input_text:
  rag_query:
    name: "RAG Query Input"
    initial: ""
    max: 255

  last_rag_prompt:
    name: "Last RAG Prompt"
    max: 5000

# Script a RAG prompt generálásához
script:
  ha_rag_prompt:
    alias: "Generate HA-RAG optimized prompt"
    sequence:
      - service: shell_command.generate_rag_prompt
        data:
          question: "{{ states('input_text.rag_query') }}"
      - delay:
          seconds: 1
      - service: input_text.set_value
        target:
          entity_id: input_text.last_rag_prompt
        data:
          value: "{{ states('sensor.rag_prompt_result') }}"
```

#### Extended OpenAI Conversation konfiguráció

Az Extended OpenAI Conversation beállításaiban add meg a következőt:

1. Nyisd meg a "Voice Assistants" beállításokat
2. Válaszd ki az Extended OpenAI Conversation-t
3. Kattints a "Configure" gombra
4. Az "Options" menüben módosítsd a kezdeti promptot (Prompt Template):
   - A YAML konfigurációs fájlban a következő beállítást add hozzá a `extended_openai_conversation` szakaszhoz:

```yaml
extended_openai_conversation:
  prompt_template: >
    {% set question = states('input_text.rag_query') %}
    {% set _ = service_data.update({"question": question}) %}
    {% set _ = state_attr('script.ha_rag_prompt', 'last_called') %}
    {{ states('input_text.last_rag_prompt') }}
```

### 3. Működés ellenőrzése

1. Indítsd újra a Home Assistant-ot
2. A `input_text.rag_query` entitásba írj be egy kérdést (pl. "Milyen állapotban van a nappali lámpa?")
3. A rendszer automatikusan meghívja a `script.ha_rag_prompt` szkriptet, ami a RAG rendszer segítségével kiválasztja a releváns entitásokat
4. A prompt megjelenik az `input_text.last_rag_prompt` entitásban
5. Az Extended OpenAI Conversation ezt a promptot használja majd a kérdés megválaszolására
6. Ellenőrizd a log fájlokat és a promptot, hogy megfelelően tartalmazza-e csak a releváns entitásokat

## Előnyök

- **Kisebb token felhasználás**: Csak a releváns entitások kerülnek a promptba
- **Gyorsabb válaszok**: Az LLM kevesebb információt kell, hogy feldolgozzon
- **Pontosabb válaszok**: Az LLM jobban tud fókuszálni a kérdés szempontjából fontos entitásokra
- **Dinamikus kontextus**: Minden kérdéshez a megfelelő entitások kerülnek kiválasztásra
