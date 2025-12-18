#!/bin/bash
# Quick start script for CodeIntel research

echo "🔬 CodeIntel Search Quality Research"
echo "======================================"

# Check for .env file
if [ ! -f .env ]; then
    echo "⚠️  No .env file found!"
    echo "   Copy .env.example to .env and add your OPENAI_API_KEY"
    echo ""
    echo "   cp .env.example .env"
    echo "   # Then edit .env with your API key"
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found!"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install openai numpy python-dotenv --quiet

# Run the experiment
echo ""
echo "🚀 Running experiment..."
echo ""
python3 test_search_quality.py
