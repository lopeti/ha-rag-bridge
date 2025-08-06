# Development Setup with Local LiteLLM

## Quick Start

1. **Start the development stack:**
   ```bash
   docker compose up -d
   ```

2. **Test the RAG hook integration:**
   ```bash
   python test_local_hook.py
   ```

## Services

- **Bridge (RAG API)**: http://localhost:8000
- **LiteLLM Proxy**: http://localhost:4000
- **ArangoDB UI**: http://localhost:8529 (if using dev.yml)

## Development Workflow

1. **Edit hook code**: Modify `litellm_ha_rag_hooks.py`
2. **Restart LiteLLM**: `docker compose restart litellm`  
3. **Test changes**: `python test_local_hook.py`

## LiteLLM Models Available

- `gemini-flash` - Gemini 2.5 Flash (fastest)
- `gemini-pro` - Gemini 2.5 Pro (premium)
- `mistral-7b` - Local Mistral 7B (self-hosted)

## Hook Configuration

The RAG hook is configured in:
- `litellm_config.yaml` - LiteLLM configuration
- `litellm_ha_rag_hooks.py` - Hook implementation
- `HA_RAG_API_URL=http://bridge:8000` - Bridge endpoint

## OpenWebUI Integration

To use with OpenWebUI:
- **Endpoint**: `http://localhost:4000/v1`
- **Model**: `gemini-flash` or any model from the list above
- **System Prompt**: Must include `{{HA_RAG_ENTITIES}}` placeholder