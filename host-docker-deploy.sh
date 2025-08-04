#!/bin/bash

# =================================================================
# HA-RAG Docker Socket Deploy - Deploy using host Docker from container
# =================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'  
RED='\033[0;31m'
NC='\033[0m'

print_step() { echo -e "${BLUE}🔧${NC} $1"; }
print_success() { echo -e "${GREEN}✅${NC} $1"; }
print_info() { echo -e "${YELLOW}ℹ${NC} $1"; }
print_error() { echo -e "${RED}❌${NC} $1"; }

echo "🚀 HA-RAG Host Docker Deploy"
echo "==========================="

# Check if we can access host Docker socket
if [ ! -S /var/run/docker.sock ]; then
    print_error "Cannot access host Docker socket!"
    echo ""
    echo "Solutions:"
    echo "1. Use ./host-deploy.sh from outside devcontainer, OR"
    echo "2. Mount Docker socket in devcontainer.json:"
    echo '   "mounts": ["source=/var/run/docker.sock,target=/var/run/docker.sock,type=bind"]'
    exit 1
fi

# Test host Docker access
print_step "Testing host Docker access..."
HOST_CONTAINERS=$(docker ps --format "table {{.Names}}" | grep -E "(portainer|ollama|arangodb)" | wc -l)

if [ "$HOST_CONTAINERS" -gt 0 ]; then
    print_success "✅ Can access host Docker (found $HOST_CONTAINERS host containers)"
else
    print_error "❌ Cannot see host containers. Are you sure Docker socket is mounted?"
    exit 1
fi

# Configuration
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-/tmp/ha-rag-host-deploy}"
COMPOSE_FILE="docker-compose.core.yml"

print_step "Deploying to host Docker via socket: $TARGET_DIR"

# Create temporary deployment directory
mkdir -p "$TARGET_DIR"

# Copy files (same as quick-deploy.sh but for host Docker)
print_step "Copying files..."

# Required files
REQUIRED_FILES=(
    "$COMPOSE_FILE"
    "Dockerfile" 
    "pyproject.toml"
    "poetry.lock"
)

# Optional files 
OPTIONAL_FILES=(
    ".env.core"
    "litellm_config.yaml"
    "litellm_ha_rag_hooks.py"
)

# Directories
DIRECTORIES=(
    "app"
    "scripts" 
    "ha_rag_bridge"
    "docker"
)

# Copy all files
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$SOURCE_DIR/$file" ]; then
        cp "$SOURCE_DIR/$file" "$TARGET_DIR/"
        print_success "✓ $file"
    else
        print_error "✗ $file MISSING!"
        exit 1
    fi
done

for file in "${OPTIONAL_FILES[@]}"; do
    if [ -f "$SOURCE_DIR/$file" ]; then
        cp "$SOURCE_DIR/$file" "$TARGET_DIR/"
        print_success "✓ $file"
    fi
done

for dir in "${DIRECTORIES[@]}"; do
    if [ -d "$SOURCE_DIR/$dir" ]; then
        cp -r "$SOURCE_DIR/$dir" "$TARGET_DIR/"
        print_success "✓ $dir/"
    fi
done

# Create .env
if [ -f "$TARGET_DIR/.env.core" ]; then
    cp "$TARGET_DIR/.env.core" "$TARGET_DIR/.env"
    print_success ".env created"
fi

cd "$TARGET_DIR"

# Stop any existing containers with same names on host
print_step "Stopping existing containers on host..."
docker stop ha-rag-bridge ha-rag-litellm 2>/dev/null || true
docker rm ha-rag-bridge ha-rag-litellm 2>/dev/null || true

# Build and deploy to host Docker
print_step "Building and starting on host Docker..."
docker compose -f docker-compose.core.yml build --no-cache
docker compose -f docker-compose.core.yml up -d

print_success "🎉 Deployed to HOST Docker!"
echo ""
echo "🔍 Check Portainer - you should see:"
echo "• ha-rag-bridge container"
echo "• ha-rag-litellm container"
echo ""
echo "🌐 Services:"
echo "• HA-RAG Bridge: http://localhost:8000"
echo "• LiteLLM: http://localhost:4001"
echo ""

# Show status
docker compose -f docker-compose.core.yml ps