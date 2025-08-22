#!/bin/bash

# HA-RAG-Bridge Environment Switcher
# Usage: ./scripts/switch_env.sh [development|production|testing]

set -e

ENVIRONMENTS_DIR="config/environments"
TARGET_ENV=".env"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

show_help() {
    echo "HA-RAG-Bridge Environment Switcher"
    echo ""
    echo "Usage: $0 [environment]"
    echo ""
    echo "Available environments:"
    echo "  development  - Development config with debug enabled"
    echo "  production   - Production config with current working values"  
    echo "  testing      - Testing config with minimal/mock settings"
    echo ""
    echo "Examples:"
    echo "  $0 development"
    echo "  $0 production"
    echo ""
}

switch_environment() {
    local env_name="$1"
    local source_file="$ENVIRONMENTS_DIR/.env.$env_name"
    
    if [[ ! -f "$source_file" ]]; then
        echo -e "${RED}Error: Environment file '$source_file' not found${NC}"
        echo ""
        echo "Available environment files:"
        ls -1 "$ENVIRONMENTS_DIR"/.env.* | sed 's|.*/\.env\.||' | grep -v template
        exit 1
    fi
    
    # Backup existing .env if it exists
    if [[ -f "$TARGET_ENV" ]]; then
        cp "$TARGET_ENV" "$TARGET_ENV.backup.$(date +%Y%m%d_%H%M%S)"
        echo -e "${YELLOW}Backed up existing .env to $TARGET_ENV.backup.$(date +%Y%m%d_%H%M%S)${NC}"
    fi
    
    # Copy new environment
    cp "$source_file" "$TARGET_ENV"
    echo -e "${GREEN}Switched to '$env_name' environment${NC}"
    echo ""
    echo "Environment details:"
    echo "  Source: $source_file"
    echo "  Target: $TARGET_ENV"
    echo ""
    echo "Key settings:"
    grep -E "^(HA_URL|ARANGO_URL|EMBEDDING_BACKEND|LOG_LEVEL|DEBUG)=" "$TARGET_ENV" | sed 's/^/  /'
    echo ""
    echo -e "${YELLOW}Remember to restart containers:${NC}"
    echo "  docker compose down && docker compose up -d"
}

# Main logic
case "$1" in
    "development"|"dev")
        switch_environment "development"
        ;;
    "production"|"prod")
        switch_environment "production"
        ;;
    "testing"|"test")
        switch_environment "testing"
        ;;
    "help"|"-h"|"--help"|"")
        show_help
        ;;
    *)
        echo -e "${RED}Error: Unknown environment '$1'${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac