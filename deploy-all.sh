#!/bin/bash
# ================================================
# Cyber-Twin Router + IoT + Blockchain + Cloud
# deploy-all.sh — Professional Fixed v4.0
# ================================================

set -euo pipefail

# ── Colour helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}ℹ  $*${RESET}"; }
success() { echo -e "${GREEN}✅ $*${RESET}"; }
warn()    { echo -e "${YELLOW}⚠️  $*${RESET}"; }
error()   { echo -e "${RED}❌ $*${RESET}"; }

# ── 0. Export required compose variables ────────────────────────────────────
# FIX: SYS was unset, causing WARN in docker compose
export SYS="${SYS:-cyber-twin-router}"

# ── 1. Pre-flight checks ─────────────────────────────────────────────────────
echo -e "\n${BOLD}🔍 Running pre-flight checks...${RESET}"

# Python3
if ! command -v python3 &>/dev/null; then
    error "Python3 not found"; exit 1
fi

# pip3
if ! command -v pip3 &>/dev/null; then
    info "pip3 not found — installing..."
    sudo apt-get update -q && sudo apt-get install -y python3-pip
fi

# Docker
if ! command -v docker &>/dev/null; then
    error "Docker not found. Please install Docker Desktop on Windows."; exit 1
fi
if ! docker info &>/dev/null; then
    error "Docker is not running. Start Docker Desktop."; exit 1
fi

success "All pre-flight checks passed."

# ── 2. Ensure Mosquitto config exists ───────────────────────────────────────
# FIX: Missing mosquitto.conf causes mqtt-broker to fail silently
MOSQUITTO_CONF="./configs/mosquitto/mosquitto.conf"
if [ ! -f "$MOSQUITTO_CONF" ]; then
    warn "mosquitto.conf not found — creating default config..."
    mkdir -p ./configs/mosquitto
    cat > "$MOSQUITTO_CONF" <<'EOF'
# Mosquitto config — Cyber-Twin Router
listener 1883
allow_anonymous true

listener 9001
protocol websockets
allow_anonymous true

log_type all
log_dest stdout
EOF
    success "Created $MOSQUITTO_CONF"
fi

# ── 3. Install Python dependencies ──────────────────────────────────────────
echo -e "\n${BOLD}📦 Installing Python dependencies...${RESET}"
python3 -m pip install --user --break-system-packages paho-mqtt web3 requests 2>/dev/null \
    || python3 -m pip install --user paho-mqtt web3 requests
success "Python dependencies ready."

# ── 4. Clean up old containers ───────────────────────────────────────────────
echo -e "\n${BOLD}🧹 Cleaning up old containers...${RESET}"
docker compose down --remove-orphans 2>/dev/null || true
success "Cleanup complete."

# ── 5. Build + start all services ───────────────────────────────────────────
echo -e "\n${BOLD}🚀 Starting full deployment (Router + IoT + Honeypot + Blockchain + Dashboard)...${RESET}"
docker compose up -d --build

# ── 6. Wait for critical services (health-aware) ─────────────────────────────
echo -e "\n${BOLD}⏳ Waiting for services to become healthy...${RESET}"

wait_for_healthy() {
    local service="$1"
    local max_wait="${2:-90}"   # seconds
    local elapsed=0
    local interval=5

    info "Waiting for ${service}..."
    while [ $elapsed -lt $max_wait ]; do
        STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo "starting")
        if [ "$STATUS" = "healthy" ]; then
            success "${service} is healthy."
            return 0
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
        echo -ne "   ⏱  ${elapsed}s / ${max_wait}s — status: ${STATUS}\r"
    done
    echo ""
    error "${service} did not become healthy within ${max_wait}s."
    docker logs "$service" --tail 30
    return 1
}

wait_for_healthy "ganache-blockchain" 90
wait_for_healthy "mqtt-broker"        30

# ── 7. Deploy smart contract ─────────────────────────────────────────────────
if [ -f "scripts/deploy_contract.py" ]; then
    echo -e "\n${BOLD}📦 Deploying CyberLogger smart contract...${RESET}"
    python3 scripts/deploy_contract.py && success "Contract deployed." \
        || warn "Contract deployment skipped (non-fatal)."
fi

# ── 8. Final status ──────────────────────────────────────────────────────────
echo -e "\n${BOLD}📋 Container status:${RESET}"
docker compose ps

echo ""
echo -e "${BOLD}${GREEN}=================================================="
echo -e "  ✅  DEPLOYMENT SUCCESSFUL!"
echo -e "==================================================${RESET}"
echo -e "  📊 Dashboard          → ${CYAN}http://localhost:5000${RESET}"
echo -e "  🔐 Honeypot SSH       → ${CYAN}localhost:2222${RESET}  (admin / password123)"
echo -e "  📡 MQTT Broker        → ${CYAN}localhost:1883${RESET}"
echo -e "  🔗 Ganache Blockchain → ${CYAN}http://localhost:8545${RESET}"
echo -e "  🌐 Router FRR SSH     → ${CYAN}localhost:2200${RESET}  (was :22 — remapped to avoid WSL conflict)"
echo ""
echo -e "  Run attack demo inside WSL:"
echo -e "  ${YELLOW}python3 scripts/simulate-iot-attack.py${RESET}"
echo -e "${BOLD}${GREEN}==================================================${RESET}\n"
