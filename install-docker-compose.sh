#!/bin/bash

# =================================================================
# Docker Compose Installation Script for Debian/Ubuntu
# =================================================================

set -e

echo "🐳 Docker Compose Installation"
echo "=============================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() { echo -e "${BLUE}📋${NC} $1"; }
print_success() { echo -e "${GREEN}✅${NC} $1"; }
print_info() { echo -e "${YELLOW}ℹ${NC} $1"; }

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

print_success "Docker is installed"

# Check current Docker Compose status
print_step "Checking Docker Compose..."

if command -v docker-compose &> /dev/null; then
    VERSION=$(docker-compose --version)
    print_success "Docker Compose v1 is installed: $VERSION"
    exit 0
elif docker compose version &> /dev/null 2>&1; then
    VERSION=$(docker compose version)
    print_success "Docker Compose v2 is installed: $VERSION"
    exit 0
fi

print_info "Docker Compose not found. Installing..."

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    print_info "Detected OS: $OS"
else
    echo "❌ Cannot detect OS"
    exit 1
fi

# Install Docker Compose
case $OS in
    *"Ubuntu"*|*"Debian"*)
        print_step "Installing Docker Compose Plugin..."
        
        # Update package index
        sudo apt-get update
        
        # Install Docker Compose plugin
        sudo apt-get install -y docker-compose-plugin
        
        print_success "Docker Compose plugin installed"
        
        # Verify installation
        if docker compose version &> /dev/null; then
            VERSION=$(docker compose version)
            print_success "Installation successful: $VERSION"
        else
            echo "❌ Installation failed"
            exit 1
        fi
        ;;
        
    *)
        print_info "Unsupported OS. Manual installation required."
        echo ""
        echo "For other systems, install Docker Compose manually:"
        echo "https://docs.docker.com/compose/install/"
        ;;
esac

echo ""
print_success "Docker Compose is ready!"
echo ""
echo "You can now use:"
echo "• ${YELLOW}docker compose version${NC} - Check version"
echo "• ${YELLOW}docker compose up -d${NC} - Start services"
echo "• ${YELLOW}docker compose down${NC} - Stop services"
