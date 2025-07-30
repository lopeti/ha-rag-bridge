# Development Environment Setup

This project supports both local development with Docker Compose and connecting to external Home Assistant and ArangoDB instances.

## Environment Options

### Local Development Environment

This setup creates all required services in Docker containers:

- Home Assistant container
- ArangoDB container
- Bridge service with auto-reload

To use this configuration:

```bash
# Get instructions for switching to development environment
./scripts/switch_env.sh dev

# Apply the development configuration (temporary, don't commit)
./scripts/switch_env.sh apply-dev

# Open VS Code and use "Reopen in Container"
code .

# After you're done, restore the original configuration
git restore .devcontainer/devcontainer.json
```

### Home Environment

This setup connects to your existing Home Assistant and ArangoDB instances:

- Uses external Home Assistant at 192.168.1.128:8123
- Uses external ArangoDB at 192.168.1.105:8529
- Bridge service with auto-reload

To use this configuration:

```bash
# Get instructions for switching to home environment
./scripts/switch_env.sh home

# Apply the home configuration (temporary, don't commit)
./scripts/switch_env.sh apply-home

# Open VS Code and use "Reopen in Container"
code .

# After you're done, restore the original configuration
git restore .devcontainer/devcontainer.json
```

## Troubleshooting

If you encounter permission issues with Docker or container setup:

```bash
# Fix ownership of important files
sudo chown -R $(whoami):$(whoami) .devcontainer docker-compose*.yml Dockerfile

# Clean up Docker cache if disk space issues occur
docker system prune -f
```

Make sure your `.env` file contains the proper credentials for your Home Assistant and ArangoDB instances.
