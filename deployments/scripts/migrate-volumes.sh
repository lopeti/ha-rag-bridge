#!/bin/bash

# ===================================================================
# Volume Migration Script - Portainer Stack to Docker Compose
# ===================================================================
# This script helps migrate existing volumes from Portainer stack
# to Docker Compose format.

set -e

echo "🔄 HA-RAG Bridge Volume Migration Script"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

echo ""
echo "📋 Checking existing volumes..."
echo "================================"

# List existing volumes
echo "Current Docker volumes:"
docker volume ls --format "table {{.Name}}\t{{.Driver}}\t{{.CreatedAt}}"

echo ""
echo "🔍 Looking for existing volumes that might be from your Portainer stack..."

# Common volume patterns from Portainer stacks
VOLUME_MAPPINGS=(
    "ollama_data:ollama_data"
    "openwebui_data:openwebui_data" 
    "mindsdb_data:mindsdb_data"
    "arangodb_data:arangodb_data"
    "jupyter_data:jupyter_data"
    "ha_rag_logs:ha_rag_logs"
)

EXISTING_VOLUMES=()
MISSING_VOLUMES=()

for mapping in "${VOLUME_MAPPINGS[@]}"; do
    old_name="${mapping%%:*}"
    new_name="${mapping##*:}"
    
    if docker volume inspect "$old_name" >/dev/null 2>&1; then
        EXISTING_VOLUMES+=("$mapping")
        print_status "Found existing volume: $old_name"
    else
        MISSING_VOLUMES+=("$mapping") 
        print_warning "Volume not found: $old_name"
    fi
done

if [ ${#EXISTING_VOLUMES[@]} -eq 0 ]; then
    print_warning "No existing volumes found with expected names."
    echo ""
    echo "This might mean:"
    echo "1. Your Portainer stack used different volume names"
    echo "2. The volumes are already using the correct names"
    echo "3. This is a fresh installation"
    echo ""
    echo "You can:"
    echo "- Check 'docker volume ls' for your actual volume names"
    echo "- Modify the docker-compose.prod.yml to use external volumes"
    echo "- Start fresh with new volumes"
else
    echo ""
    echo "🔧 Migration Options"
    echo "==================="
    echo ""
    echo "Option 1: Use existing volumes as external volumes"
    echo "  - Modify docker-compose.prod.yml to reference existing volumes"
    echo "  - No data migration needed"
    echo "  - Recommended if volume names match"
    echo ""
    echo "Option 2: Copy data to new volumes" 
    echo "  - Create new volumes with compose project prefix"
    echo "  - Copy data from old to new volumes"
    echo "  - Keep old volumes as backup"
    echo ""
    
    read -p "Choose option (1 for external, 2 for copy, q to quit): " choice
    
    case $choice in
        1)
            echo ""
            print_status "Setting up external volumes..."
            
            # Create backup of docker-compose.prod.yml
            cp docker-compose.prod.yml docker-compose.prod.yml.backup
            print_status "Created backup: docker-compose.prod.yml.backup"
            
            # Modify the compose file to use external volumes
            for mapping in "${EXISTING_VOLUMES[@]}"; do
                old_name="${mapping%%:*}"
                
                # Add external: true to volume definition
                sed -i "s|^  ${old_name}:$|  ${old_name}:\n    external: true|g" docker-compose.prod.yml
                
                print_status "Configured $old_name as external volume"
            done
            
            print_status "External volume configuration complete!"
            echo ""
            echo "📝 Next steps:"
            echo "1. Review the modified docker-compose.prod.yml"
            echo "2. Copy .env.example to .env and fill in your values"
            echo "3. Run: docker-compose -f docker-compose.prod.yml up -d"
            ;;
            
        2)
            echo ""
            print_status "Setting up volume data copy..."
            
            # Get the compose project name
            PROJECT_NAME=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]//g')
            echo "Detected project name: $PROJECT_NAME"
            
            # Create new volumes and copy data
            for mapping in "${EXISTING_VOLUMES[@]}"; do
                old_name="${mapping%%:*}"
                new_name="${PROJECT_NAME}_${mapping##*:}"
                
                print_status "Copying $old_name -> $new_name"
                
                # Create new volume
                docker volume create "$new_name"
                
                # Copy data using a temporary container
                docker run --rm \
                    -v "$old_name":/source:ro \
                    -v "$new_name":/destination \
                    alpine:latest \
                    sh -c "cp -a /source/. /destination/"
                
                print_status "Copied data from $old_name to $new_name"
            done
            
            print_status "Volume data copy complete!"
            echo ""
            echo "📝 Next steps:"
            echo "1. Copy .env.example to .env and fill in your values"
            echo "2. Run: docker-compose -f docker-compose.prod.yml up -d"
            echo "3. Verify everything works, then you can remove old volumes if needed"
            ;;
            
        q|Q)
            echo "Migration cancelled."
            exit 0
            ;;
            
        *)
            print_error "Invalid option selected."
            exit 1
            ;;
    esac
fi

echo ""
echo "🎉 Migration script completed!"
echo ""
echo "📚 Additional Resources:"
echo "- View logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "- Stop services: docker-compose -f docker-compose.prod.yml down"
echo "- View volumes: docker volume ls"
echo "- Backup volumes: docker run --rm -v VOLUME_NAME:/data -v \$(pwd):/backup alpine tar czf /backup/VOLUME_NAME.tar.gz -C /data ."
