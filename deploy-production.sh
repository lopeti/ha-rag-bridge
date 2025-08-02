#!/bin/bash

# =================================================================
# HA-RAG Bridge Production Deployment Script
# =================================================================
# This script helps deploy the production stack to your host machine

set -e

echo "🚀 HA-RAG Bridge Production Deployment"
echo "======================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${BLUE}📋${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed or not in PATH"
    exit 1
fi

print_success "Docker and Docker Compose are available"

# Get deployment directory
DEPLOY_DIR="${1:-$HOME/ha-rag-production}"
echo ""
print_step "Deployment directory: $DEPLOY_DIR"

# Create deployment directory
mkdir -p "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

print_success "Created deployment directory: $DEPLOY_DIR"

# Copy necessary files
print_step "Copying production files..."

# Files to copy from the project
FILES_TO_COPY=(
    "docker-compose.prod.yml"
    "litellm_config.py"
    "litellm_ha_rag_hooks.py"
    ".env.prod"
    "migrate-volumes.sh"
    "README-production.md"
)

for file in "${FILES_TO_COPY[@]}"; do
    if [ -f "/app/$file" ]; then
        cp "/app/$file" .
        print_success "Copied $file"
    else
        print_warning "File not found: $file"
    fi
done

# Rename .env.prod to .env
if [ -f ".env.prod" ]; then
    cp .env.prod .env
    print_success "Created .env from .env.prod"
fi

# Make scripts executable
chmod +x migrate-volumes.sh 2>/dev/null || true

print_step "Files copied successfully!"
echo ""

# Show next steps
echo "📋 Next Steps:"
echo "=============="
echo ""
echo "1. Review and edit the .env file:"
echo "   ${YELLOW}nano .env${NC}"
echo ""
echo "2. (Optional) Migrate existing volumes:"
echo "   ${YELLOW}./migrate-volumes.sh${NC}"
echo ""
echo "3. Start the production stack:"
echo "   ${YELLOW}docker-compose -f docker-compose.prod.yml up -d${NC}"
echo ""
echo "4. View logs:"
echo "   ${YELLOW}docker-compose -f docker-compose.prod.yml logs -f${NC}"
echo ""
echo "5. Check status:"
echo "   ${YELLOW}docker-compose -f docker-compose.prod.yml ps${NC}"
echo ""

# Show service URLs
echo "🌐 Service URLs:"
echo "==============="
echo "• Open WebUI:     http://localhost:3000"
echo "• HA-RAG Bridge:  http://localhost:8001"
echo "• ArangoDB:       http://localhost:8529"
echo "• LiteLLM:        http://localhost:4000"
echo "• MindsDB:        http://localhost:47334"
echo "• Jupyter:        http://localhost:8888"
echo ""

# Check for existing Portainer volumes
print_step "Checking for existing volumes..."
EXISTING_VOLUMES=$(docker volume ls --format "{{.Name}}" | grep -E "(ollama|arangodb|openwebui|mindsdb|jupyter)" || true)

if [ -n "$EXISTING_VOLUMES" ]; then
    print_warning "Found existing volumes that might be from Portainer:"
    echo "$EXISTING_VOLUMES"
    echo ""
    echo "Consider running: ${YELLOW}./migrate-volumes.sh${NC}"
else
    print_success "No conflicting volumes found"
fi

echo ""
print_success "Deployment preparation complete!"
echo ""
echo "📁 Deployment directory: ${GREEN}$DEPLOY_DIR${NC}"
echo "🔧 Edit configuration: ${YELLOW}cd $DEPLOY_DIR && nano .env${NC}"
echo "🚀 Start services: ${YELLOW}cd $DEPLOY_DIR && docker-compose -f docker-compose.prod.yml up -d${NC}"
