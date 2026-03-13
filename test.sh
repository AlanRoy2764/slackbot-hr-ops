#!/bin/bash
# Test script for Slackbot HR Ops

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Run tests with coverage
echo "Running tests..."
python -m pytest tests/ -v --tb=short "$@"
