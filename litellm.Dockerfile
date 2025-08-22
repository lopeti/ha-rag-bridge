FROM ghcr.io/berriai/litellm:main-latest

# Copy config and hooks directly into the container  
COPY litellm_config_phase3.yaml /app/config.yaml
COPY litellm_ha_rag_hooks_phase3.py /app/hooks.py

# Verify files are copied correctly
RUN ls -la /app/config.yaml /app/hooks.py