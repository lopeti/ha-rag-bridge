#!/bin/bash

# Home Assistant RAG Bridge + LiteLLM Integráció telepítési szkript
# Ez a szkript létrehozza a megfelelő könyvtárstruktúrát és fájlokat az integrációhoz

set -e

# Könyvtárak létrehozása
echo "Könyvtárak létrehozása..."
mkdir -p ha-rag-bridge/app
mkdir -p ha-rag-bridge/config

# Fájlok másolása
echo "Fájlok másolása..."
cp docker-compose.full-stack.yml ha-rag-bridge/
cp litellm_ha_rag_hooks.py ha-rag-bridge/app/
cp litellm_config.py ha-rag-bridge/app/
cp test_integration.py ha-rag-bridge/app/
cp Makefile.integration ha-rag-bridge/Makefile
cp INTEGRATION_GUIDE.md ha-rag-bridge/
cp USAGE_EXAMPLE.md ha-rag-bridge/

# Home Assistant konfiguráció létrehozása
cat > ha-rag-bridge/config/configuration.yaml << EOL
# Home Assistant konfiguráció a HA-RAG Bridge + LiteLLM integrációhoz

# Alapbeállítások
default_config:

# Http beállítások
http:
  server_port: 8123
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.16.0.0/12

# Eseménynaplózás
logger:
  default: info
  logs:
    homeassistant.components.conversation: debug
    custom_components.extended_openai_conversation: debug

# Extended OpenAI Conversation integráció
extended_openai_conversation:
  - id: ha_rag_assistant
    name: Home Assistant RAG Assistant
    prompt: |-
      You are a helpful home assistant AI. You can answer questions and control the home.
      
      Use the given context about home devices to provide accurate information.
      
      {{HA_RAG_ENTITIES}}
      
      If there's a way to help using the available devices, suggest how to do it.
    api_key: !secret openai_api_key
    api_endpoint: "http://litellm:4000/v1"
    temperature: 0.7
    max_tokens: 1000
    model: gpt-3.5-turbo
    functions:
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
      - name: light.turn_on
        description: Turn on a light
        parameters:
          type: object
          properties:
            entity_id:
              type: string
              description: The entity_id of the light to turn on
            brightness:
              type: integer
              description: The brightness value (0-255)
          required:
            - entity_id
EOL

# Secrets fájl létrehozása
cat > ha-rag-bridge/config/secrets.yaml << EOL
# Home Assistant secrets

# OpenAI API kulcs - ezt cseréld ki a sajátodra
openai_api_key: sk-your-api-key

# Egyéb titkok
EOL

# .env fájl létrehozása
cat > ha-rag-bridge/.env << EOL
# Környezeti változók a Home Assistant RAG Bridge + LiteLLM integrációhoz

# Home Assistant Long-Lived Access Token
# Ezt cseréld ki a sajátodra: Profil > Long-Lived Access Tokens > Create Token
HASS_TOKEN=your_long_lived_access_token_here
EOL

# Használati útmutató
echo ""
echo "Home Assistant RAG Bridge + LiteLLM Integráció telepítése sikeresen befejeződött!"
echo ""
echo "A következő lépések:"
echo "1. Lépj be a ha-rag-bridge könyvtárba: cd ha-rag-bridge"
echo "2. Szerkeszd a következő fájlokat a saját környezetedhez:"
echo "   - .env - Add meg a HASS_TOKEN értékét"
echo "   - config/secrets.yaml - Add meg az openai_api_key értékét"
echo "3. Indítsd el a rendszert: make up"
echo "4. Inicializáld az adatbázist: make init-db"
echo "5. Importáld az entitásokat: make ingest"
echo ""
echo "További információkért olvasd el az INTEGRATION_GUIDE.md fájlt."
echo ""
