#!/bin/bash

# =================================================================
# Portainer to Docker Compose Migration Script
# =================================================================

set -e

echo "🔄 Portainer → Docker Compose Migration"
echo "========================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() { echo -e "${BLUE}📋${NC} $1"; }
print_success() { echo -e "${GREEN}✅${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}❌${NC} $1"; }

# Check Docker
if ! docker info >/dev/null 2>&1; then
    print_error "Docker is not running!"
    exit 1
fi

echo ""
print_step "Analyzing current Portainer stack..."

# List current containers
echo "Current containers:"
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

echo ""
print_step "Analyzing volumes..."

# Expected volumes from your Portainer stack
PORTAINER_VOLUMES=(
    "ollama_data"
    "openwebui_data" 
    "mindsdb_data"
    "arangodb_data"
    "jupyter_data"
    "ha_rag_logs"
)

FOUND_VOLUMES=()
MISSING_VOLUMES=()

for vol in "${PORTAINER_VOLUMES[@]}"; do
    if docker volume inspect "$vol" >/dev/null 2>&1; then
        FOUND_VOLUMES+=("$vol")
        print_success "Found volume: $vol"
    else
        MISSING_VOLUMES+=("$vol")
        print_warning "Volume not found: $vol"
    fi
done

echo ""
echo "🎯 Migration Options:"
echo "===================="
echo ""
echo "1. 🔒 SAFE - Parallel test deployment"
echo "   • Keep Portainer stack running"
echo "   • Deploy Docker Compose on different ports"
echo "   • Test and compare"
echo "   • Switch when ready"
echo ""
echo "2. 🚀 QUICK - Direct replacement"
echo "   • Stop Portainer stack"
echo "   • Migrate volumes"
echo "   • Start Docker Compose stack"
echo ""
echo "3. 🔄 HYBRID - Rolling update"
echo "   • Migrate service by service"
echo "   • Keep data consistency"
echo ""

read -p "Choose migration strategy (1/2/3): " strategy

case $strategy in
    1)
        echo ""
        print_step "Setting up parallel test deployment..."
        
        # Create a test version of docker-compose with different ports
        if [ ! -f "docker-compose.prod.yml" ]; then
            print_error "docker-compose.prod.yml not found!"
            exit 1
        fi
        
        # Create test version with different ports
        sed 's/3000:8080/3001:8080/g; s/8001:8000/8002:8000/g; s/8529:8529/8530:8529/g; s/4000:4000/4001:4000/g; s/47334:47334/47335:47334/g; s/8888:8888/8889:8888/g' docker-compose.prod.yml > docker-compose.test.yml
        
        print_success "Created docker-compose.test.yml with test ports"
        
        echo ""
        echo "🧪 Test Deployment Commands:"
        echo "============================"
        echo "Start test stack:"
        echo "  ${YELLOW}docker-compose -f docker-compose.test.yml up -d${NC}"
        echo ""
        echo "Test URLs:"
        echo "  • Open WebUI:     http://localhost:3001"
        echo "  • HA-RAG Bridge:  http://localhost:8002" 
        echo "  • ArangoDB:       http://localhost:8530"
        echo "  • LiteLLM:        http://localhost:4001"
        echo "  • MindsDB:        http://localhost:47335"
        echo "  • Jupyter:        http://localhost:8889"
        echo ""
        echo "When satisfied with testing:"
        echo "1. Stop test: ${YELLOW}docker-compose -f docker-compose.test.yml down${NC}"
        echo "2. Stop Portainer stack in Portainer UI"
        echo "3. Start production: ${YELLOW}docker-compose -f docker-compose.prod.yml up -d${NC}"
        ;;
        
    2)
        echo ""
        print_warning "This will stop your current Portainer stack!"
        read -p "Are you sure? (y/N): " confirm
        
        if [[ $confirm =~ ^[Yy]$ ]]; then
            print_step "Getting Portainer stack name..."
            
            # Try to find stack containers
            STACK_CONTAINERS=$(docker ps --format "{{.Names}}" | head -10)
            
            echo "Detected containers:"
            echo "$STACK_CONTAINERS"
            echo ""
            
            read -p "Enter your Portainer stack name (or press Enter to manually stop): " stack_name
            
            if [ -n "$stack_name" ]; then
                print_step "Stopping Portainer stack: $stack_name"
                # This is tricky as Portainer doesn't use standard compose
                print_warning "Please stop the stack manually in Portainer UI, then press Enter"
                read -p "Press Enter when Portainer stack is stopped..."
            fi
            
            print_step "Starting Docker Compose stack..."
            if [ -f "docker-compose.prod.yml" ] && [ -f ".env" ]; then
                docker-compose -f docker-compose.prod.yml up -d
                print_success "Docker Compose stack started!"
            else
                print_error "Missing docker-compose.prod.yml or .env file"
            fi
        else
            echo "Migration cancelled."
        fi
        ;;
        
    3)
        echo ""
        print_step "Setting up hybrid migration..."
        print_warning "This is advanced - consider using option 1 instead"
        
        echo "Service migration order:"
        echo "1. ArangoDB (data layer)"
        echo "2. HA-RAG Bridge (core service)"  
        echo "3. LiteLLM (API layer)"
        echo "4. Ollama (if needed)"
        echo "5. Other services"
        
        print_warning "Manual process - requires careful port management"
        ;;
        
    *)
        print_error "Invalid option selected"
        exit 1
        ;;
esac

echo ""
print_step "Volume Management Tips:"
echo "======================="

if [ ${#FOUND_VOLUMES[@]} -gt 0 ]; then
    echo "✅ Found volumes (will be preserved):"
    for vol in "${FOUND_VOLUMES[@]}"; do
        echo "   • $vol"
        
        # Show volume size
        size=$(docker system df -v | grep "$vol" | awk '{print $3}' || echo "unknown")
        echo "     Size: $size"
    done
    
    echo ""
    echo "💾 Backup commands (run before migration):"
    for vol in "${FOUND_VOLUMES[@]}"; do
        echo "docker run --rm -v ${vol}:/data -v \$(pwd):/backup alpine tar czf /backup/${vol}-backup.tar.gz -C /data ."
    done
fi

echo ""
print_success "Migration planning complete!"
echo ""
echo "📋 Next Steps Summary:"
echo "====================="
echo "1. Review the migration strategy above"
echo "2. Backup important volumes if needed"
echo "3. Follow the chosen migration path"
echo "4. Monitor logs during transition"
echo "5. Verify all services are working"
