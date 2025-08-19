# MCP (Model Context Protocol) Integration Setup

This document outlines the MCP servers installed and configured for the HA RAG Bridge development environment.

## Installed MCP Servers

### 1. Docker MCP Server ✅ INSTALLED
- **Repository**: https://github.com/QuantGeekDev/docker-mcp
- **Installation**: `uvx docker-mcp`
- **Capabilities**:
  - Container creation and instantiation
  - Docker Compose stack deployment
  - Container logs retrieval
  - Container listing and status monitoring
- **Usage Examples**:
  ```bash
  # Start Docker MCP server
  uvx docker-mcp
  ```

### 2. Git MCP Server ✅ INSTALLED  
- **Installation**: `uvx mcp-server-git`
- **Capabilities**:
  - Git repository operations
  - Commit history browsing
  - Branch management
  - Diff viewing
- **Usage Examples**:
  ```bash
  # Start Git MCP server for current repository
  uvx mcp-server-git --repository /home/debian/ha-rag-bridge
  ```

### 3. Filesystem MCP Server ✅ INSTALLED
- **Options**:
  - NPX version: `npx @modelcontextprotocol/server-filesystem`
  - Go version: https://github.com/mark3labs/mcp-filesystem-server
  - Docker version: Available but not yet configured
- **Capabilities**:
  - Secure file operations
  - Configuration file management
  - Directory tree generation
  - Search functionality

### 4. ArangoDB MCP Server ✅ INSTALLED
- **Repository**: https://github.com/ravenwits/mcp-server-arangodb
- **Installation**: `npx arango-server`
- **Capabilities**:
  - AQL query execution through natural language
  - Document insertion/updating/removal
  - Collection management and backup
  - Database schema exploration
- **Usage Examples**:
  ```bash
  # Start ArangoDB MCP server with credentials
  export ARANGO_USERNAME=root
  export ARANGO_PASSWORD=test123
  export ARANGO_DATABASE=homeassistant
  export ARANGO_URL=http://192.168.1.105:8529
  npx arango-server
  ```

## Claude Code Configuration

To enable MCP servers in Claude Code, the configuration needs to be added to the Claude Desktop configuration file.

### Development Configuration
```json
{
  "mcpServers": {
    "docker-mcp": {
      "command": "uvx", 
      "args": ["docker-mcp"]
    },
    "git-mcp": {
      "command": "uvx",
      "args": ["mcp-server-git", "--repository", "/home/debian/ha-rag-bridge"]
    },
    "filesystem-mcp": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/debian/ha-rag-bridge"]
    },
    "arangodb-mcp": {
      "command": "npx",
      "args": ["arango-server"],
      "env": {
        "ARANGO_USERNAME": "root",
        "ARANGO_PASSWORD": "test123", 
        "ARANGO_DATABASE": "homeassistant",
        "ARANGO_URL": "http://192.168.1.105:8529"
      }
    }
  }
}
```

## Benefits for Development Workflow

### Docker MCP Benefits
- **Container Management**: Start/stop containers through Claude
- **Compose Operations**: Deploy and manage docker-compose stacks
- **Log Analysis**: Retrieve and analyze container logs
- **Development Efficiency**: Reduce context switching between terminal and Claude

### Git MCP Benefits  
- **Repository Navigation**: Browse commit history and branches
- **Code Review**: Analyze diffs and changes
- **Branch Operations**: Create and manage branches through Claude
- **Integration**: Seamless git operations within Claude workflow

### Filesystem MCP Benefits
- **Config Management**: Edit .env, CLAUDE.md, config files
- **File Operations**: Safe file manipulation with path validation
- **Search Capabilities**: Find files and content across project
- **Project Navigation**: Generate directory trees and explore structure

## Security Considerations

- **Path Validation**: Filesystem MCP prevents directory traversal attacks
- **Docker Access**: Docker MCP requires proper Docker permissions
- **Repository Access**: Git MCP operates within specified repository boundaries
- **Controlled Access**: All MCP servers provide controlled, secure access to system resources

## Next Steps

1. ✅ Install Docker MCP server (`uvx docker-mcp`)
2. ✅ Install Git MCP server (`uvx mcp-server-git`)
3. 🔄 Configure Filesystem MCP server
4. 🔄 Test MCP integration with Claude Code
5. 🔄 Document team workflow and best practices

## Implementation Status

- **Docker MCP**: ✅ Successfully installed and tested
- **Git MCP**: ✅ Successfully installed and verified
- **Filesystem MCP**: 🔄 Multiple options available, needs selection
- **Claude Integration**: 🔄 Pending configuration
- **Team Documentation**: 🔄 In progress

## Team Benefits

With these MCP servers integrated:

1. **Unified Workflow**: Manage Docker, Git, and files through Claude
2. **Reduced Context Switching**: Fewer terminal operations needed
3. **Enhanced Productivity**: AI-assisted development operations
4. **Better Debugging**: Container log analysis through Claude
5. **Safer Operations**: Controlled access with built-in security features

## Environment Variables

Add to `.bashrc` or `.zshrc`:
```bash
export PATH="$HOME/.local/bin:$PATH"  # For uvx and uv commands
```

## Troubleshooting

- **UV Installation**: Use `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Path Issues**: Ensure `$HOME/.local/bin` is in PATH
- **Docker Permissions**: Verify Docker daemon access
- **Git Access**: Ensure repository read/write permissions