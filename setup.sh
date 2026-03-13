#!/bin/bash
# Setup script for Slackbot HR Ops

set -e

echo "Setting up Slackbot HR Ops..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create logs directory
mkdir -p logs

# Copy .env.example if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "========================================"
    echo "IMPORTANT: Please edit .env file with your credentials before running the bot!"
    echo "========================================"
    echo ""
fi

# Make scripts executable
chmod +x run.sh

# Verify symlink to hr_automation
if [ ! -L "hr_automation" ]; then
    echo "Creating symlink to hr_automation..."
    ln -s ~/Documents/Claude\ Project/Google\ Workspace\ Automation/hr-automation hr_automation
fi

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your credentials"
echo "2. Run: ./run.sh"
echo ""
