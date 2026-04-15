#!/usr/bin/env python3

from flask import Flask, render_template, jsonify
from web3 import Web3
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cyber-twin-master-project-2026'

BADGE_COLORS = {
    "BruteForce": "badge-red", "DDoS": "badge-red",
    "Ransomware": "badge-red", "ZeroDayExploit": "badge-red",
    "PortScan": "badge-orange", "FirmwareTamper": "badge-orange",
    "C2Beacon": "badge-orange", "MQTTInject": "badge-blue",
    "MITM": "badge-blue", "SQLInjection": "badge-purple",
    "CredHarvest": "badge-purple", "DataExfil": "badge-purple",
}

@app.template_filter('eventBadge')
def event_badge_filter(event_type):
    cls = BADGE_COLORS.get(event_type, "badge-green")
    return f'<span class="badge {cls}">{event_type}</span>'

GANACHE_URL   = os.getenv("BLOCKCHAIN_URL", "http://ganache-blockchain:8545")
CONTRACT_FILE = "/tmp/contract_address.txt"

CONTRACT_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "eventType",  "type": "string"},
            {"internalType": "string", "name": "attackerIP", "type": "string"},
            {"internalType": "string", "name": "iotDevice",  "type": "string"},
            {"internalType": "string", "name": "details",    "type": "string"}
        ],
        "name": "logEvent",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "internalType": "uint256", "name": "timestamp",  "type": "uint256"},
            {"indexed": False, "internalType": "string",  "name": "eventType",  "type": "string"},
            {"indexed": False, "internalType": "string",  "name": "attackerIP", "type": "string"},
            {"indexed": False, "internalType": "string",  "name": "iotDevice",  "type": "string"},
            {"indexed": False, "internalType": "string",  "name": "details",    "type": "string"},
            {"indexed": False, "internalType": "string",  "name": "txHash",     "type": "string"}
        ],
        "name": "CyberEvent",
        "type": "event"
    }
]

# ── Web3 setup with PoA middleware (required for Ganache) ─────────────────────
def make_w3():
    instance = Web3(Web3.HTTPProvider(GANACHE_URL, request_kwargs={"timeout": 10}))
    # Apply PoA middleware — Ganache uses Proof-of-Authority
    # Handles both web3.py v7 (ExtraDataToPOAMiddleware) and v6 (geth_poa_middleware)
    try:
        from web3.middleware import ExtraDataToPOAMiddleware
        instance.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    except ImportError:
        try:
            from web3.middleware import geth_poa_middleware
            instance.middleware_onion.inject(geth_poa_middleware, layer=0)
        except ImportError:
            pass
    return instance

w3 = make_w3()

def get_contract():
    """Load contract fresh on every call — picks up new deployments instantly."""
    try:
        if not w3.is_connected():
            return None, None, "Ganache unreachable"
        if not os.path.exists(CONTRACT_FILE):
            return None, None, f"Contract file missing: {CONTRACT_FILE}"
        with open(CONTRACT_FILE, 'r') as f:
            addr = f.read().strip()
        if not addr or not addr.startswith("0x"):
            return None, None, f"Invalid address in file: '{addr}'"
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(addr),
            abi=CONTRACT_ABI
        )
        return contract, addr, None
    except Exception as e:
        return None, None, str(e)

def fetch_events(contract, limit=100):
    """
    Fetch CyberEvent logs — robust across web3.py v6 and v7.
    FIX: Use eth_getLogs via w3.eth.get_logs as primary method,
         with contract event decoder as fallback.
         Avoids the toBlock='latest' string issue in web3 v7.
    """
    events = []
    errors = []

    # Method 1: Direct eth_getLogs + manual ABI decode (most compatible)
    try:
        latest_block = w3.eth.block_number
        raw_logs = w3.eth.get_logs({
            "fromBlock": 0,
            "toBlock":   latest_block,
            "address":   contract.address,
        })
        for raw in reversed(raw_logs[-limit:]):
            try:
                decoded = contract.events.CyberEvent().process_log(raw)
                a = decoded["args"]
                events.append({
                    "timestamp":  datetime.fromtimestamp(a["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "eventType":  a["eventType"],
                    "attackerIP": a["attackerIP"],
                    "iotDevice":  a["iotDevice"],
                    "details":    a["details"],
                    "txHash":     decoded["transactionHash"].hex()[:18] + "...",
                    "block":      decoded["blockNumber"],
                })
            except Exception as decode_err:
                errors.append(f"decode: {decode_err}")
        if events or not errors:
            return events, None
    except Exception as e:
        errors.append(f"get_logs: {e}")

    # Method 2: contract.events.CyberEvent.get_logs (web3 v6 style)
    try:
        latest_block = w3.eth.block_number
        logs = contract.events.CyberEvent.get_logs(
            fromBlock=0, toBlock=latest_block
        )
        for log in reversed(logs[-limit:]):
            a = log["args"]
            events.append({
                "timestamp":  datetime.fromtimestamp(a["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                "eventType":  a["eventType"],
                "attackerIP": a["attackerIP"],
                "iotDevice":  a["iotDevice"],
                "details":    a["details"],
                "txHash":     log["transactionHash"].hex()[:18] + "...",
                "block":      log["blockNumber"],
            })
        return events, None
    except Exception as e:
        errors.append(f"get_logs_v2: {e}")

    return [], "; ".join(errors) if errors else None

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    contract, addr, err = get_contract()
    events, fetch_err = fetch_events(contract) if contract else ([], None)

    if contract and w3.is_connected():
        status    = "Blockchain Connected • Real-time"
        addr_disp = addr[:14] + "..." if addr else "N/A"
        block_num = w3.eth.block_number
    else:
        status    = f"Connecting... ({err})" if err else "Connecting to Blockchain..."
        addr_disp = "Not deployed yet"
        block_num = 0

    return render_template('index.html',
        events=events,
        status=status,
        contract_address=addr_disp,
        block_number=block_num,
        event_count=len(events),
        fetch_error=fetch_err or ""
    )

@app.route('/events')
def get_events():
    """JSON API polled every 5s by the dashboard."""
    contract, addr, err = get_contract()
    events, fetch_err   = fetch_events(contract) if contract else ([], None)

    try:
        block_num = w3.eth.block_number if w3.is_connected() else 0
    except Exception:
        block_num = 0

    return jsonify({
        "events":       events,
        "status":       "connected" if contract else "waiting",
        "contract":     addr or "not deployed",
        "block_number": block_num,
        "event_count":  len(events),
        "error":        fetch_err or err or None,
    })

@app.route('/debug')
def debug():
    """Diagnostic endpoint — open in browser if dashboard shows no events."""
    contract, addr, err = get_contract()
    events, fetch_err   = fetch_events(contract) if contract else ([], None)

    try:
        block_num  = w3.eth.block_number if w3.is_connected() else 0
        accounts   = w3.eth.accounts[:3] if w3.is_connected() else []
        balance    = str(w3.eth.get_balance(accounts[0])) if accounts else "N/A"
    except Exception as diag_err:
        block_num, accounts, balance = 0, [], str(diag_err)

    return jsonify({
        "ganache_url":      GANACHE_URL,
        "connected":        w3.is_connected(),
        "block_number":     block_num,
        "accounts_found":   len(accounts),
        "sample_account":   accounts[0] if accounts else None,
        "account_balance":  balance,
        "contract_file":    CONTRACT_FILE,
        "contract_file_exists": os.path.exists(CONTRACT_FILE),
        "contract_address": addr,
        "contract_error":   err,
        "events_fetched":   len(events),
        "fetch_error":      fetch_err,
        "web3_version":     Web3.api,
    })

@app.route('/health')
def health():
    _, addr, _ = get_contract()
    return jsonify({
        "status":             "healthy",
        "blockchain_connected": w3.is_connected(),
        "contract_loaded":    addr is not None
    })

if __name__ == '__main__':
    print(f"🚀 Cyber-Twin Dashboard starting on :5000")
    print(f"   Ganache URL    : {GANACHE_URL}")
    print(f"   Contract file  : {CONTRACT_FILE}")
    app.run(host='0.0.0.0', port=5000, debug=False)
