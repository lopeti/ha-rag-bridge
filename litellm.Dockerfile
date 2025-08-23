FROM ghcr.io/berriai/litellm:main-latest

# Copy config and hooks from new locations after refactor
COPY config/litellm/litellm_config.yaml /app/config.yaml
COPY config/litellm/hooks/litellm_ha_rag_hooks_phase3.py /app/litellm_ha_rag_hooks_phase3.py

# Verify files are copied correctly
RUN ls -la /app/config.yaml /app/litellm_ha_rag_hooks_phase3.py