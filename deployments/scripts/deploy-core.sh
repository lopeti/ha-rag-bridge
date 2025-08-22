#!/bin/bash

# =================================================================
# HA-RAG Core Stack Deployment
# =================================================================

set -e

echo "🎯 HA-RAG Core Stack Deployment"
echo "==============================="

# Colors
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
BLUE=$(tput setaf 4)
NC=$(tput sgr0)

print_step() { echo -e "${BLUE}📋${NC} $1"; }
print_success() { echo -e "${GREEN}✅${NC} $1"; }
print_info() { echo -e "${YELLOW}ℹ${NC} $1"; }

# Define APP_DIR
APP_DIR="${1:-$HOME/ha-rag-bridge}"
print_step "Using application directory: $APP_DIR"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found!"
    exit 1
fi

# Check Docker Compose (v1 or v2)
COMPOSE_CMD=""
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ Docker Compose not found!"
    echo "Install with: sudo apt-get update && sudo apt-get install docker-compose-plugin"
    exit 1
fi

print_success "Docker and Docker Compose ($COMPOSE_CMD) are available"

# Setup deployment directory
DEPLOY_DIR="${1:-$HOME/ha-rag-core}"
print_step "Setting up deployment directory: $DEPLOY_DIR"

mkdir -p "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

# Copy core files
print_step "Copying core stack files..."

if [ -f "$APP_DIR/docker-compose.core.yml" ]; then
    cp "$APP_DIR/docker-compose.core.yml" .
    print_success "Copied docker-compose.core.yml to $(pwd)"
else
    print_info "docker-compose.core.yml not found in $APP_DIR"
fi

if [ -f "$APP_DIR/.env.core" ]; then
    cp "$APP_DIR/.env.core" .env
    print_success "Created .env from .env.core in $(pwd)"
else
    print_info ".env.core not found in $APP_DIR"
fi

# Ensure litellm_config.yaml is copied as a file, not a directory
if [ -f "$APP_DIR/litellm_config.yaml" ]; then
    cp "$APP_DIR/litellm_config.yaml" "$DEPLOY_DIR/litellm_config.yaml"
    print_success "Copied litellm_config.yaml to $(pwd)"
else
    print_info "litellm_config.yaml not found in $APP_DIR"
fi

# Ensure litellm_ha_rag_hooks.py is copied as a file, not a directory
if [ -f "$APP_DIR/litellm_ha_rag_hooks.py" ]; then
    cp "$APP_DIR/litellm_ha_rag_hooks.py" "$DEPLOY_DIR/litellm_ha_rag_hooks.py"
    print_success "Copied litellm_ha_rag_hooks.py to $(pwd)"
else
    print_info "litellm_ha_rag_hooks.py not found in $APP_DIR"
fi

if [ -f "$APP_DIR/Dockerfile" ]; then
    cp "$APP_DIR/Dockerfile" .
    print_success "Copied Dockerfile to $(pwd)"
else
    print_info "Dockerfile not found in $APP_DIR"
fi

if [ -f "$APP_DIR/pyproject.toml" ]; then
    cp "$APP_DIR/pyproject.toml" .
    print_success "Copied pyproject.toml to $(pwd)"
else
    print_info "pyproject.toml not found in $APP_DIR"
fi

if [ -f "$APP_DIR/poetry.lock" ]; then
    cp "$APP_DIR/poetry.lock" .
    print_success "Copied poetry.lock to $(pwd)"
else
    print_info "poetry.lock not found in $APP_DIR"
fi

# Copy app directory
if [ -d "$APP_DIR/app" ]; then
    cp -r "$APP_DIR/app" .
    print_success "Copied app directory to $(pwd)"
else
    print_info "app directory not found in $APP_DIR"
fi

# Copy scripts directory
if [ -d "$APP_DIR/scripts" ]; then
    cp -r "$APP_DIR/scripts" .
    print_success "Copied scripts directory to $(pwd)"
else
    print_info "scripts directory not found in $APP_DIR"
fi

# Copy ha_rag_bridge directory
if [ -d "$APP_DIR/ha_rag_bridge" ]; then
    cp -r "$APP_DIR/ha_rag_bridge" .
    print_success "Copied ha_rag_bridge directory to $(pwd)"
else
    print_info "ha_rag_bridge directory not found in $APP_DIR"
fi

# Ensure docker directory exists
mkdir -p ./docker

# Copy uvicorn_log.ini file
if [ -f "$APP_DIR/docker/uvicorn_log.ini" ]; then
    cp "$APP_DIR/docker/uvicorn_log.ini" ./docker/
    print_success "Copied uvicorn_log.ini to $(pwd)/docker"
else
    print_info "uvicorn_log.ini not found in $APP_DIR/docker"
fi

echo ""
print_step "Core Stack Services:"
echo "===================="
echo "✅ HA-RAG Bridge  - Core application (localhost:8000)"  
echo "✅ LiteLLM        - API proxy (localhost:4001)"
echo ""

print_step "External Dependencies:"
echo "======================"
echo "📍 ArangoDB       - http://192.168.1.105:8529 (external)"
echo "📍 Home Assistant - http://192.168.1.128:8123 (external)"
echo "📍 InfluxDB       - http://192.168.1.128:8086 (optional)"
echo ""

print_step "Core Stack Ports:"
echo "================="
echo "• HA-RAG Bridge:  http://localhost:8000"
echo "• LiteLLM:        http://localhost:4001"
echo ""

print_info "Optional Stock Components (deploy separately):"
echo "=============================================="
echo "• Open WebUI:     ghcr.io/open-webui/open-webui:latest"
echo "• Ollama:         ollama/ollama:latest"
echo "• MindsDB:        mindsdb/mindsdb:latest"
echo ""

# Check for conflicts
print_step "Checking for port conflicts..."
if netstat -tuln 2>/dev/null | grep -q ":8000\|:4001"; then
    echo "⚠️  Some ports may be in use. Check for conflicts:"
    netstat -tuln 2>/dev/null | grep ":8000\|:4001" || true
    echo ""
fi

# Ready to deploy
echo "🚀 Ready to deploy!"
echo "=================="
echo ""
echo "Next steps:"
echo "0. Go to deployment directory: ${YELLOW}cd $DEPLOY_DIR${NC}"
echo "1. Review/edit .env file: ${YELLOW}nano .env${NC}"
echo "2. Start core stack: ${YELLOW}$COMPOSE_CMD -f docker-compose.core.yml up -d${NC}"
echo "3. Check status: ${YELLOW}$COMPOSE_CMD -f docker-compose.core.yml ps${NC}"
echo "4. View logs: ${YELLOW}$COMPOSE_CMD -f docker-compose.core.yml logs -f${NC}"
echo ""

echo "Optional stock components:"
echo "• Open WebUI: ${YELLOW}docker run -d --name open-webui -p 3000:8080 -e OPENAI_API_BASE_URL=http://host.docker.internal:4000/v1 ghcr.io/open-webui/open-webui:latest${NC}"
echo "• Ollama: ${YELLOW}docker run -d --name ollama -p 11434:11434 -v ollama:/root/.ollama ollama/ollama:latest${NC}"
echo ""

print_success "Core stack deployment prepared in: $DEPLOY_DIR"
