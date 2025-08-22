#!/bin/bash

# =================================================================
# HA-RAG Host Deploy - Deploy from outside devcontainer
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

echo "🚀 HA-RAG Host Deploy"
echo "===================="
echo "⚠️  Run this script OUTSIDE of devcontainer!"
echo ""

# Check if we're in a container
if [ -f /.dockerenv ]; then
    print_error "You're inside a container! Exit devcontainer first."
    echo ""
    echo "How to exit:"
    echo "1. Open Command Palette (Ctrl+Shift+P)"
    echo "2. Type: Dev Containers: Reopen Folder Locally" 
    echo "3. Then run: ./host-deploy.sh"
    exit 1
fi

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-$HOME/ha-rag-core-host}"
COMPOSE_FILE="docker-compose.core.yml"

print_step "Host deployment to: $TARGET_DIR"

# Backup existing if it exists
if [ -d "$TARGET_DIR" ] && [ "$(ls -A $TARGET_DIR 2>/dev/null)" ]; then
    BACKUP_DIR="${TARGET_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
    print_step "Creating backup: $BACKUP_DIR"
    cp -r "$TARGET_DIR" "$BACKUP_DIR"
    print_success "Backup created"
fi

# Create deployment directory
mkdir -p "$TARGET_DIR"

# Copy files
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

# Copy required files
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$file" ]; then
        cp "$PROJECT_DIR/$file" "$TARGET_DIR/"
        print_success "✓ $file"
    else
        print_error "✗ $file MISSING!"
        exit 1
    fi
done

# Copy optional files
for file in "${OPTIONAL_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$file" ]; then
        cp "$PROJECT_DIR/$file" "$TARGET_DIR/"
        print_success "✓ $file"
    else
        print_info "○ $file (optional)"
    fi
done

# Copy directories
for dir in "${DIRECTORIES[@]}"; do
    if [ -d "$PROJECT_DIR/$dir" ]; then
        cp -r "$PROJECT_DIR/$dir" "$TARGET_DIR/"
        print_success "✓ $dir/"
    else
        print_info "○ $dir/ (not found)"
    fi
done

# Create .env from .env.core
if [ -f "$TARGET_DIR/.env.core" ]; then
    cp "$TARGET_DIR/.env.core" "$TARGET_DIR/.env"
    print_success ".env created from .env.core"
fi

# Version info
if [ -d "$PROJECT_DIR/.git" ]; then
    cd "$PROJECT_DIR"
    echo "# Version info" > "$TARGET_DIR/VERSION.txt"
    echo "Commit: $(git rev-parse HEAD)" >> "$TARGET_DIR/VERSION.txt"
    echo "Branch: $(git branch --show-current)" >> "$TARGET_DIR/VERSION.txt"
    echo "Date: $(date)" >> "$TARGET_DIR/VERSION.txt"
    echo "Source: $PROJECT_DIR" >> "$TARGET_DIR/VERSION.txt"
    echo "Deploy: HOST-LEVEL" >> "$TARGET_DIR/VERSION.txt"
    print_success "Version info saved"
fi

cd "$TARGET_DIR"

# Create host-level management scripts
cat > start.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting HA-RAG stack on HOST Docker..."
# Stop any conflicting containers first
docker stop ha-rag-bridge ha-rag-litellm 2>/dev/null || true
docker rm ha-rag-bridge ha-rag-litellm 2>/dev/null || true
# Build and start
docker compose -f docker-compose.core.yml build
docker compose -f docker-compose.core.yml up -d
echo "✅ Stack started - Check Portainer!"
echo "• HA-RAG Bridge: http://localhost:8000"
echo "• LiteLLM: http://localhost:4001"
EOF

cat > stop.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping HA-RAG stack..."
docker compose -f docker-compose.core.yml down
EOF

cat > restart.sh << 'EOF'
#!/bin/bash
echo "🔄 Restarting HA-RAG stack..."
./stop.sh
docker compose -f docker-compose.core.yml build --no-cache
docker compose -f docker-compose.core.yml up -d
echo "✅ Stack restarted - visible in Portainer!"
EOF

cat > status.sh << 'EOF'
#!/bin/bash
echo "📊 HA-RAG Stack status (HOST Docker):"
docker compose -f docker-compose.core.yml ps
echo ""
echo "🌐 Services:"
echo "• HA-RAG Bridge: http://localhost:8000"
echo "• LiteLLM: http://localhost:4001"
echo ""
echo "🏷️  Images:"
docker images | grep -E "(ha-rag|litellm)" | head -5
EOF

cat > logs.sh << 'EOF'
#!/bin/bash
docker compose -f docker-compose.core.yml logs -f
EOF

chmod +x *.sh

print_success "Host deployment tools created"

echo ""
print_success "🎉 Host Deploy Complete!"
echo ""
echo "📁 Target: ${YELLOW}$TARGET_DIR${NC}"
echo ""
echo "⚡ Commands (run OUTSIDE devcontainer):"
echo "   ${YELLOW}cd $TARGET_DIR${NC}"
echo "   ${YELLOW}./start.sh${NC}     # Start on host Docker (Portainer will see it)"
echo "   ${YELLOW}./restart.sh${NC}   # Rebuild + restart"
echo "   ${YELLOW}./status.sh${NC}    # Check status"
echo ""
print_info "This will be visible in Portainer because it runs on host Docker!"