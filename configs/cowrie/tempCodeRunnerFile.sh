#!/bin/bash
# ================================================
# Cyber-Twin Router + IoT + Blockchain + Cloud
# deploy-all.sh — PROFESSIONAL FIXED v3.0
# ================================================

set -e

echo "🔍 Running pre-flight checks..."

# Ensure Python + pip
command -v python3 >/dev/null || { echo "❌ Python3 not found"; exit 1; }
command -v pip3 >/dev/null || sudo apt-get update && sudo apt-get install -y python3-pip

# Docker check
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker Desktop on Windows."
    exit 1
fi
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Start Docker Desktop."
    exit 1
fi

echo "✅ All pre-flight checks passed."

# Install Python dependencies (fixes paho-mqtt error)
echo "📦 Installing Python dependencies..."
python3 -m pip install --user paho-mqtt

echo "🧹 Cleaning up old containers..."
docker compose down --remove-orphans 2>/dev/null || true

echo "🚀 Starting full deployment (Router + IoT + Honeypot + Blockchain + Dashboard)..."
docker compose up -d --build

echo "⏳ Waiting for services to start..."
sleep 15

# Deploy smart contract (optional)
if [ -f "scripts/deploy_contract.py" ]; then
    echo "📦 Deploying CyberLogger smart contract..."
    python3 scripts/deploy_contract.py || echo "⚠️ Contract deployment skipped."
fi

echo ""
echo "=================================================="
echo "✅ DEPLOYMENT SUCCESSFUL!"
echo "=================================================="
echo "📊 Dashboard          → http://localhost:5000"
echo "🔐 Honeypot SSH       → localhost:2222 (admin / password123)"
echo "📡 MQTT Broker        → localhost:1883"
echo "🔗 Ganache Blockchain → http://localhost:8545"
echo ""
echo "Run attack demo inside WSL:"
echo "   python3 scripts/simulate-iot-attack.py"
echo "=================================================="