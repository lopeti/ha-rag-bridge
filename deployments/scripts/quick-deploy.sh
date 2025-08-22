#!/bin/bash

# =================================================================
# HA-RAG Smart Deploy - Gyors fejlesztés -> éles telepítés
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

# Configuration
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-$HOME/ha-rag-core}"
COMPOSE_FILE="docker-compose.core.yml"

echo "🚀 HA-RAG Smart Deploy"
echo "======================"
echo "Forrás: $SOURCE_DIR"
echo "Cél: $TARGET_DIR"
echo ""

# Gyors validáció
if [ ! -f "$SOURCE_DIR/$COMPOSE_FILE" ]; then
    print_error "$COMPOSE_FILE nem található!"
    exit 1
fi

# Backup az előző verziót ha létezik
if [ -d "$TARGET_DIR" ] && [ "$(ls -A $TARGET_DIR 2>/dev/null)" ]; then
    BACKUP_DIR="${TARGET_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
    print_step "Backup készítése: $BACKUP_DIR"
    cp -r "$TARGET_DIR" "$BACKUP_DIR"
    print_success "Backup kész"
fi

# Szinkronizálás - csak a szükséges fájlokat
print_step "Fájlok másolása..."
mkdir -p "$TARGET_DIR"

# Kötelező fájlok listája
REQUIRED_FILES=(
    "$COMPOSE_FILE"
    "Dockerfile" 
    "pyproject.toml"
    "poetry.lock"
)

# Opcionális fájlok 
OPTIONAL_FILES=(
    ".env.core"
    "litellm_config.yaml"
    "litellm_ha_rag_hooks.py"
)

# Könyvtárak
DIRECTORIES=(
    "app"
    "scripts" 
    "ha_rag_bridge"
    "docker"
)

# Kötelező fájlok másolása
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$SOURCE_DIR/$file" ]; then
        cp "$SOURCE_DIR/$file" "$TARGET_DIR/"
        print_success "✓ $file"
    else
        print_error "✗ $file HIÁNYZIK!"
        exit 1
    fi
done

# Opcionális fájlok
for file in "${OPTIONAL_FILES[@]}"; do
    if [ -f "$SOURCE_DIR/$file" ]; then
        cp "$SOURCE_DIR/$file" "$TARGET_DIR/"
        print_success "✓ $file"
    else
        print_info "○ $file (opcionális)"
    fi
done

# Könyvtárak másolása
for dir in "${DIRECTORIES[@]}"; do
    if [ -d "$SOURCE_DIR/$dir" ]; then
        cp -r "$SOURCE_DIR/$dir" "$TARGET_DIR/"
        print_success "✓ $dir/"
    else
        print_info "○ $dir/ (nem található)"
    fi
done

# .env kezelés
if [ -f "$TARGET_DIR/.env.core" ]; then
    cp "$TARGET_DIR/.env.core" "$TARGET_DIR/.env"
    print_success ".env létrehozva .env.core-ból"
fi

# Git info mentése verziókövetéshez
if [ -d "$SOURCE_DIR/.git" ]; then
    cd "$SOURCE_DIR"
    echo "# Verzió információ" > "$TARGET_DIR/VERSION.txt"
    echo "Commit: $(git rev-parse HEAD)" >> "$TARGET_DIR/VERSION.txt"
    echo "Branch: $(git branch --show-current)" >> "$TARGET_DIR/VERSION.txt"
    echo "Dátum: $(date)" >> "$TARGET_DIR/VERSION.txt"
    echo "Forrás: $SOURCE_DIR" >> "$TARGET_DIR/VERSION.txt"
    print_success "Verzió információ mentve"
fi

print_step "Deploy eszközök..."
cd "$TARGET_DIR"

# Smart deploy tools creation
cat > build.sh << 'EOF'
#!/bin/bash
echo "🔨 Building HA-RAG image..."
docker compose -f docker-compose.core.yml build --no-cache
echo "✅ Image rebuilt successfully"
EOF

cat > start.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting HA-RAG stack..."
# Build first (if code changed)
docker compose -f docker-compose.core.yml build
docker compose -f docker-compose.core.yml up -d
echo "✅ Stack started - Ports: 8000 (bridge), 4001 (litellm)"
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
docker compose -f docker-compose.core.yml build
docker compose -f docker-compose.core.yml up -d
echo "✅ Stack restarted successfully"
EOF

cat > logs.sh << 'EOF'
#!/bin/bash
docker compose -f docker-compose.core.yml logs -f
EOF

cat > status.sh << 'EOF'
#!/bin/bash
echo "📊 HA-RAG Stack status:"
docker compose -f docker-compose.core.yml ps
echo ""
echo "🌐 Services:"
echo "• HA-RAG Bridge: http://localhost:8000"
echo "• LiteLLM: http://localhost:4001"
echo ""
echo "🏷️  Image info:"
docker images | grep -E "(ha-rag|litellm)" | head -5
EOF

cat > update.sh << 'EOF'
#!/bin/bash
echo "🔄 Updating HA-RAG stack..."
./stop.sh
# Update external images (e.g. litellm)
docker compose -f docker-compose.core.yml pull litellm
# Rebuild our image
docker compose -f docker-compose.core.yml build --no-cache ha-rag-bridge
./start.sh
EOF

cat > clean.sh << 'EOF'
#!/bin/bash
echo "🧹 Cleaning HA-RAG Docker resources..."
./stop.sh
docker compose -f docker-compose.core.yml down --rmi local --volumes
echo "✅ All cleaned up (images, volumes)"
EOF

chmod +x *.sh
print_success "Deploy eszközök létrehozva (build.sh, start.sh, stop.sh, restart.sh, logs.sh, status.sh, update.sh, clean.sh)"

echo ""
print_success "🎉 Deploy kész!"
echo ""
echo "📁 Cél könyvtár: ${YELLOW}$TARGET_DIR${NC}"
echo ""
echo "⚡ Gyors parancsok:"
echo "   ${YELLOW}cd $TARGET_DIR${NC}"
echo "   ${YELLOW}./start.sh${NC}    # Indítás (auto-build)"
echo "   ${YELLOW}./stop.sh${NC}     # Leállítás"  
echo "   ${YELLOW}./restart.sh${NC}  # Újraindítás (rebuild)"
echo "   ${YELLOW}./logs.sh${NC}     # Logok"
echo "   ${YELLOW}./status.sh${NC}   # Állapot + images"
echo "   ${YELLOW}./update.sh${NC}   # Teljes frissítés"
echo "   ${YELLOW}./build.sh${NC}    # Csak újraépítés"
echo "   ${YELLOW}./clean.sh${NC}    # Teljes tisztítás"
echo ""
echo "🔧 Konfiguráció szerkesztése:"
echo "   ${YELLOW}nano .env${NC}"
echo ""

# Automatikus indítás opció
read -p "Indítsam most a stack-et? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_step "Stack indítása..."
    ./start.sh
    echo ""
    print_success "Stack fut! Nézd meg: ./status.sh"
fi