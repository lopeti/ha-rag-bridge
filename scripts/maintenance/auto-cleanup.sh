#!/bin/bash

# Automatikus Docker cleanup script
# Használat: ./scripts/auto-cleanup.sh [mild|aggressive|info]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

MODE=${1:-mild}

show_usage() {
    echo "Usage: $0 [mild|aggressive|info]"
    echo ""
    echo "Modes:"
    echo "  mild       - Clean only unused resources (safe)"
    echo "  aggressive - Clean ALL unused resources including images"
    echo "  info       - Show disk usage information only"
    echo ""
    exit 1
}

show_disk_info() {
    echo "💾 Current Docker disk usage:"
    docker system df
    echo ""
    echo "🖼️ Recent images:"
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.CreatedSince}}\t{{.Size}}" | head -15
}

mild_cleanup() {
    echo "🧹 Mild cleanup: Removing unused containers, networks, and dangling images..."
    
    # Remove stopped containers
    echo "Removing stopped containers..."
    docker container prune -f
    
    # Remove unused networks
    echo "Removing unused networks..."
    docker network prune -f
    
    # Remove dangling images only (not tagged images)
    echo "Removing dangling images..."
    docker image prune -f
    
    echo "✅ Mild cleanup completed!"
}

aggressive_cleanup() {
    echo "⚠️  AGGRESSIVE cleanup: This will remove ALL unused Docker resources!"
    echo "   - Unused images (including tagged ones not used by any container)"
    echo "   - Build cache"
    echo "   - Unused volumes"
    echo ""
    
    if [ -t 0 ]; then  # Check if running interactively
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Cancelled."
            exit 0
        fi
    fi
    
    echo "🧹 Starting aggressive cleanup..."
    
    # Clean everything
    docker system prune -a -f --volumes
    docker builder prune -f
    
    echo "✅ Aggressive cleanup completed!"
}

cleanup_dev_images() {
    echo "🧹 Cleaning ha-rag-bridge development images..."
    
    # Remove old ha-rag-bridge images
    OLD_IMAGES=$(docker images ha-rag-bridge* --format "{{.ID}}" | tail -n +3)
    if [ ! -z "$OLD_IMAGES" ]; then
        echo "Removing old ha-rag-bridge images..."
        echo "$OLD_IMAGES" | xargs docker rmi -f
    fi
    
    # Remove <none> images
    NONE_IMAGES=$(docker images --filter "dangling=true" --format "{{.ID}}")
    if [ ! -z "$NONE_IMAGES" ]; then
        echo "Removing <none> images..."
        echo "$NONE_IMAGES" | xargs docker rmi -f
    fi
    
    echo "✅ Development images cleaned!"
}

case "$MODE" in
    info)
        show_disk_info
        ;;
    mild)
        show_disk_info
        echo ""
        mild_cleanup
        cleanup_dev_images
        echo ""
        show_disk_info
        ;;
    aggressive)
        show_disk_info
        echo ""
        aggressive_cleanup
        echo ""
        show_disk_info
        ;;
    *)
        echo "Unknown mode: $MODE"
        show_usage
        ;;
esac