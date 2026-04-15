#!/bin/bash
# ================================================
# Cyber-Twin Router — Demo Runner
# run-demo.sh
# Activates venv automatically and runs the attack simulator
# ================================================

CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; RESET='\033[0m'

# Ensure we're in the project root
cd "$(dirname "$0")"

VENV="$PWD/.venv"

echo -e "\n${CYAN}🚀 Cyber-Twin Router — Attack Demo${RESET}"
echo "────────────────────────────────────"

# Activate venv
if [ ! -f "$VENV/bin/activate" ]; then
    echo -e "${YELLOW}⚠️  .venv not found — running deploy-all.sh first to create it...${RESET}"
    ./deploy-all.sh
fi

echo -e "${GREEN}✅ Activating Python venv: $VENV${RESET}"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# Verify contract is deployed
if [ ! -f "/tmp/contract_address.txt" ]; then
    echo -e "\n${YELLOW}📦 Contract not deployed yet — deploying now...${RESET}"
    python3 scripts/deploy_contract.py || {
        echo -e "${RED}❌ Contract deployment failed. Are containers running?${RESET}"
        echo "   Check: docker compose ps"
        exit 1
    }
fi

echo -e "${GREEN}✅ Contract ready: $(cat /tmp/contract_address.txt)${RESET}"
echo ""
echo -e "  📊 Dashboard → ${CYAN}http://localhost:5000${RESET}"
echo -e "  🔗 Blockchain → ${CYAN}http://localhost:8545${RESET}"
echo ""
echo -e "${YELLOW}Starting attack simulation... (Ctrl+C to stop)${RESET}\n"

python3 scripts/simulate-iot-attack.py
