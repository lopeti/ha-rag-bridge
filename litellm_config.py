"""
LiteLLM példa konfigurációs fájl a Home Assistant RAG Bridge integrációval
"""

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
callbacks = [
    {
        "pre_call_hook": "litellm_ha_rag_hooks:litellm_pre_processor",
        "post_call_hook": "litellm_ha_rag_hooks:litellm_post_processor",
    }
]

# Környezeti változók a HA-RAG Bridge-hez
env = {
    "HA_RAG_API_URL": "http://ha-rag-bridge:8000/api",
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
