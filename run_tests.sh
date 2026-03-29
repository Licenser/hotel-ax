#!/bin/bash
# Script to run Hotel-AX integration tests

set -e

echo "=== Hotel-AX Test Runner ==="

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements-dev.txt

# Run tests
echo ""
echo "Running tests..."
pytest -v

echo ""
echo "Tests complete!"
