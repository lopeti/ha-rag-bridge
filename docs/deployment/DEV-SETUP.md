# Development Setup with Local LiteLLM

## 🚀 Recommended Development Workflows

### Option 1: DevContainer + Claude CLI (Enhanced)
**Best for:** Consistent Python environment, integrated debugging

1. **Setup:**
   ```bash
   # Open in VS Code DevContainer (F1 > "Dev Containers: Reopen in Container")
   # Claude CLI and sessions now persist across rebuilds
   ```

2. **Features:**
   - ✅ Docker socket access from DevContainer
   - ✅ Claude CLI session persistence 
   - ✅ Integrated debugging (port 5678)
   - ✅ All dependencies pre-installed

3. **Workflow:**
   ```bash
   # Inside DevContainer
   make dev-up              # Start services
   docker compose restart litellm  # Container management works!
   claude                   # Claude CLI with persistent sessions
   ```

### Option 2: Host-based Development (Immediate Solution)
**Best for:** Claude CLI stability, no container rebuilds needed

1. **Setup:**
   ```bash
   # On host machine
   poetry install
   poetry shell
   ```

2. **Services:**
   ```bash
   make dev-up              # Docker services
   # Code editing in VS Code (host)
   # Claude CLI on host terminal
   ```

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

## 🔧 DevContainer Enhancements

### New Features (After Container Rebuild)
- **Docker Socket Access**: Manage containers from inside DevContainer
- **Claude CLI Persistence**: Sessions survive container rebuilds via `~/.claude` mount
- **No More Manual Claude Installation**: Automatic setup preserved

### Troubleshooting
```bash
# If Docker commands don't work in DevContainer:
ls -la /var/run/docker.sock  # Should exist

# If Claude sessions lost:
ls -la ~/.claude             # Should be mounted from host

# Container rebuild required for these changes:
# F1 > "Dev Containers: Rebuild Container"
```

## 🧹 Docker Disk Space Management

### Problem: DevContainer Rebuilds Consume Disk Space
Frequent DevContainer rebuilds create many unused images, containers, and build cache layers.

### Quick Cleanup Commands
```bash
# Check disk usage
make docker-system-info

# Mild cleanup (safe - only unused resources)
make docker-cleanup

# Clean only development images  
make docker-clean-dev

# Aggressive cleanup (removes ALL unused resources)
make docker-prune
```

### Automated Cleanup Script
```bash
# Show disk usage only
./scripts/auto-cleanup.sh info

# Mild cleanup (recommended for regular use)
./scripts/auto-cleanup.sh mild

# Aggressive cleanup (when disk space is critical)
./scripts/auto-cleanup.sh aggressive
```

### Recommended Cleanup Strategy
1. **Weekly**: `make docker-cleanup` (safe cleanup)
2. **After major rebuilds**: `make docker-clean-dev` 
3. **When disk is >80% full**: `./scripts/auto-cleanup.sh aggressive`
4. **Before important work**: `make docker-system-info` (check status)

### Cleanup Details
- **docker-cleanup**: Removes unused containers, networks, dangling images
- **docker-clean-dev**: Removes old ha-rag-bridge images and `<none>` tags
- **docker-prune**: Full system prune including BuildKit cache (⚠️ aggressive)
- **auto-cleanup.sh**: Interactive script with safety prompts