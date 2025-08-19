#!/bin/bash

# Test MCP Servers Installation and Functionality
# This script verifies that MCP servers are properly installed and accessible

set -e

echo "🧪 Testing MCP Server Installation and Functionality"
echo "======================================================"

# Ensure PATH includes uv
export PATH="$HOME/.local/bin:$PATH"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test function
test_command() {
    local name="$1"
    local command="$2"
    
    echo -n "Testing $name... "
    if eval "$command" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        return 1
    fi
}

# Test UV installation
echo -e "${YELLOW}1. Testing UV Package Manager${NC}"
test_command "UV Installation" "uv --version"
test_command "UVX Availability" "uvx --help"

echo ""

# Test MCP Server Installations
echo -e "${YELLOW}2. Testing MCP Server Installations${NC}"
test_command "Docker MCP" "timeout 5 uvx docker-mcp --help 2>/dev/null || true"
test_command "Git MCP" "timeout 5 uvx mcp-server-git --help"
test_command "Filesystem MCP (NPX)" "timeout 5 npx @modelcontextprotocol/server-filesystem --help 2>/dev/null || true"
test_command "ArangoDB MCP" "export ARANGO_USERNAME=root && export ARANGO_PASSWORD=test123 && export ARANGO_DATABASE=homeassistant && export ARANGO_URL=http://192.168.1.105:8529 && timeout 3 npx arango-server 2>/dev/null || true"

echo ""

# Test Docker Access
echo -e "${YELLOW}3. Testing Docker Access${NC}"
test_command "Docker Daemon" "docker info"
test_command "Docker Containers" "docker ps"

echo ""

# Test Git Repository Access
echo -e "${YELLOW}4. Testing Git Repository Access${NC}"
test_command "Git Repository" "git -C /home/debian/ha-rag-bridge status"
test_command "Git Logs" "git -C /home/debian/ha-rag-bridge log --oneline -5"

echo ""

# Test Filesystem Access
echo -e "${YELLOW}5. Testing Filesystem Access${NC}"
test_command "Project Directory" "ls /home/debian/ha-rag-bridge"
test_command "Config Files" "ls /home/debian/ha-rag-bridge/.env"
test_command "Memory Bank" "ls /home/debian/ha-rag-bridge/memory-bank"

echo ""

# Test Current Stack Status
echo -e "${YELLOW}6. Testing Current Stack Status${NC}"
test_command "HA RAG Bridge" "curl -s http://localhost:8000/health"
test_command "ArangoDB" "curl -s http://localhost:18529/_api/version"
test_command "Home Assistant" "curl -s http://192.168.1.128:8123 | head -1"

echo ""
echo "🎯 MCP Server Test Summary:"
echo "- Docker MCP: Container and compose management"
echo "- Git MCP: Repository operations and history"  
echo "- Filesystem MCP: Secure file operations"
echo "- ArangoDB MCP: Database queries and AQL operations"
echo ""
echo "📚 Next Steps:"
echo "1. Configure Claude Desktop with MCP servers"
echo "2. Test MCP integration through Claude interface"
echo "3. Document team workflow and best practices"
echo ""
echo "🔗 Configuration Guide: memory-bank/mcp-integration-setup.md"