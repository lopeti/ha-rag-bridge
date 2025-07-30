#!/bin/bash

# Helper script to switch between development and home environments
# Instead of modifying files directly, this script shows the commands to run

if [ "$1" == "home" ]; then
  echo "==== Home Environment Configuration ===="
  echo "To temporarily use the home environment configuration, run this command:"
  echo ""
  echo "  cp .devcontainer/devcontainer.json.home .devcontainer/devcontainer.json"
  echo ""
  echo "Note: This will modify a file tracked by git. Don't commit this change."
  echo "After using, you may want to run 'git restore .devcontainer/devcontainer.json'"
  echo "Then rebuild the container to use the home environment."

elif [ "$1" == "dev" ]; then
  echo "==== Development Environment Configuration ===="
  echo "To temporarily use the development environment configuration, run this command:"
  echo ""
  echo "  cp .devcontainer/devcontainer.json.dev .devcontainer/devcontainer.json"
  echo ""
  echo "Note: This will modify a file tracked by git. Don't commit this change."
  echo "After using, you may want to run 'git restore .devcontainer/devcontainer.json'"
  echo "Then rebuild the container to use the development environment."

elif [ "$1" == "apply-home" ]; then
  echo "Switching to home environment..."
  cp .devcontainer/devcontainer.json.home .devcontainer/devcontainer.json
  echo "Done! Remember this is a temporary change. Don't commit it to git."
  echo "Rebuild the container to use the home environment."

elif [ "$1" == "apply-dev" ]; then
  echo "Switching to development environment..."
  cp .devcontainer/devcontainer.json.dev .devcontainer/devcontainer.json
  echo "Done! Remember this is a temporary change. Don't commit it to git."
  echo "Rebuild the container to use the development environment."

else
  echo "Usage: $0 [home|dev|apply-home|apply-dev]"
  echo ""
  echo "Without 'apply-' prefix, the script only shows instructions."
  echo "With 'apply-' prefix, the script actually makes the changes."
  echo ""
  echo "  home       - Show instructions for using external Home Assistant and ArangoDB"
  echo "  dev        - Show instructions for using local Docker containers"
  echo "  apply-home - Actually apply the home environment configuration"
  echo "  apply-dev  - Actually apply the development environment configuration"
  exit 1
fi
