#!/bin/bash
# HA Configuration Advisor wrapper script

cd "$(dirname "$0")/.."

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Run the advisor with all arguments passed through
PYTHONPATH=. python3 scripts/ha_config_advisor.py "$@"