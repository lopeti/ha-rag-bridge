"""
LiteLLM példa konfigurációs fájl a Home Assistant RAG Bridge integrációval
"""

from litellm_ha_rag_hooks import ha_rag_hook_instance

model_list = [
    {
        "model_name": "gpt-3.5-turbo",
        "litellm_params": {"model": "ollama/llama2", "api_base": "http://ollama:11434"},
    },
    {
        "model_name": "gpt-4",
        "litellm_params": {
            "model": "ollama/mixtral",
            "api_base": "http://ollama:11434",
        },
    },
]

# Pre-processor és post-processor hookok konfigurálása
# Use the HARagHook instance directly for both pre- and post-call hooks
callbacks = ha_rag_hook_instance

# Környezeti változók a HA-RAG Bridge-hez
env = {
    "HA_RAG_API_URL": "http://ha-rag-bridge:8000",
    "HA_RAG_PLACEHOLDER": "{{HA_RAG_ENTITIES}}",
    "ENABLE_HA_TOOL_EXECUTION": "true",
}

# Proxy beállítások
proxy_config = {
    "model_list": model_list,
    "callbacks": callbacks,
    "environment_variables": env,
    "general_settings": {
        "drop_params": True,  # Eltávolítja a nem ismert paramétereket a modellek közötti átjárhatóság érdekében
        "add_function_to_prompt": True,  # A függvényhívásokat beilleszti a promptba, ha az alapul szolgáló modell nem támogatja
    },
}
