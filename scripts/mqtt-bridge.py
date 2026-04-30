#!/usr/bin/env python3
"""
Cyber-Twin Router — MQTT to Blockchain Bridge
scripts/mqtt-bridge.py  v1.0

Subscribes to the MQTT broker and logs every hardware IoT event
(from NodeMCU boards) directly to the Ganache blockchain,
so they appear live on the dashboard at localhost:5000
"""

import sys, os, json, time

# ── Auto-activate project venv ────────────────────────────────────────────────
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_venv_py = os.path.join(_root, ".venv", "bin", "python3")
if os.path.exists(_venv_py) and sys.executable != _venv_py and "VIRTUAL_ENV" not in os.environ:
    print(f"Re-launching inside venv...")
    os.execv(_venv_py, [_venv_py] + sys.argv)

try:
    import paho.mqtt.client as mqtt
    from web3 import Web3
except ImportError as e:
    print(f"ERROR: {e}\nRun: source .venv/bin/activate first")
    sys.exit(1)

# ── Config (override via env vars) ───────────────────────────────────────────
MQTT_BROKER    = os.getenv("MQTT_BROKER",    "localhost")
MQTT_PORT      = int(os.getenv("MQTT_PORT",  "1883"))
MQTT_TOPIC     = os.getenv("MQTT_TOPIC",     "iot/#")        # subscribe to ALL iot topics
BLOCKCHAIN_URL = os.getenv("BLOCKCHAIN_URL", "http://localhost:8545")
CONTRACT_FILE  = "/tmp/contract_address.txt"

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
    }
]

# ── Web3 + PoA middleware ────────────────────────────────────────────────────
print("\n" + "="*55)
print("  Cyber-Twin Router — MQTT Bridge v1.0")
print("="*55)

w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_URL))

# Apply PoA middleware for Ganache (works with web3 v6 and v7)
try:
    from web3.middleware import ExtraDataToPOAMiddleware
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
except ImportError:
    try:
        from web3.middleware import geth_poa_middleware
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except ImportError:
        pass

if not w3.is_connected():
    print(f"ERROR: Cannot connect to Ganache at {BLOCKCHAIN_URL}")
    print("       Make sure containers are running: docker compose ps")
    sys.exit(1)

print(f"Blockchain : {BLOCKCHAIN_URL} (block #{w3.eth.block_number})")
w3.eth.default_account = w3.eth.accounts[0]
print(f"Account    : {w3.eth.accounts[0]}")

# ── Load contract ─────────────────────────────────────────────────────────────
if not os.path.exists(CONTRACT_FILE):
    print(f"\nERROR: Contract not deployed yet.")
    print("       Run first: python3 scripts/deploy_contract.py")
    sys.exit(1)

with open(CONTRACT_FILE) as f:
    addr = f.read().strip()

contract = w3.eth.contract(address=Web3.to_checksum_address(addr), abi=CONTRACT_ABI)
print(f"Contract   : {addr}")

# ── Event counter ─────────────────────────────────────────────────────────────
stats = {"received": 0, "logged": 0, "failed": 0}

def log_to_blockchain(event_type, attacker_ip, iot_device, details):
    """Send a transaction to the smart contract."""
    try:
        tx = contract.functions.logEvent(
            str(event_type)[:64],
            str(attacker_ip)[:64],
            str(iot_device)[:64],
            str(details)[:128]
        ).transact({"from": w3.eth.default_account, "gas": 300000})

        receipt = w3.eth.wait_for_transaction_receipt(tx, timeout=20)
        if receipt.status == 1:
            stats["logged"] += 1
            return True, receipt.blockNumber
        else:
            stats["failed"] += 1
            return False, None
    except Exception as e:
        stats["failed"] += 1
        print(f"   Blockchain error: {e}")
        return False, None

# ── MQTT callbacks ────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        client.subscribe(MQTT_TOPIC)
        print(f"\nMQTT       : connected to {MQTT_BROKER}:{MQTT_PORT}")
        print(f"Subscribed : {MQTT_TOPIC}")
        print("\nWaiting for NodeMCU events... (Ctrl+C to stop)\n" + "-"*55)
    else:
        print(f"MQTT connection failed: rc={rc}")

def on_message(client, userdata, msg):
    stats["received"] += 1
    topic   = msg.topic
    payload = msg.payload.decode("utf-8", errors="replace")

    print(f"\n[MSG #{stats['received']}] topic: {topic}")
    print(f"  payload: {payload[:120]}")

    # Parse JSON payload from NodeMCU firmware
    event_type  = "IoTEvent"
    attacker_ip = "unknown"
    iot_device  = "NodeMCU"
    details     = payload[:128]

    try:
        data = json.loads(payload)
        event_type  = data.get("attack",     data.get("eventType",  "IoTEvent"))
        attacker_ip = data.get("attackerIP", data.get("ip",         "unknown"))
        iot_device  = data.get("device",     data.get("iotDevice",  "NodeMCU"))
        temp        = data.get("temp")
        hum         = data.get("humidity")

        if temp is not None and hum is not None:
            details = f"Temp:{temp:.1f}C Humidity:{hum:.0f}% from {iot_device}"
        else:
            details = data.get("details", payload[:128])

    except (json.JSONDecodeError, KeyError, TypeError):
        # Fallback: use raw payload as details
        pass

    print(f"  event   : {event_type}")
    print(f"  device  : {iot_device}")
    print(f"  IP      : {attacker_ip}")
    print(f"  Logging to blockchain...")

    ok, block = log_to_blockchain(event_type, attacker_ip, iot_device, details)

    if ok:
        print(f"  Block #{block} confirmed  |  total logged: {stats['logged']}")
        print(f"  Dashboard will update within 5s → http://localhost:5000")
    else:
        print(f"  Blockchain log FAILED  |  failed count: {stats['failed']}")

def on_disconnect(client, userdata, rc, properties=None):
    if rc != 0:
        print(f"\nMQTT disconnected (rc={rc}) — reconnecting in 5s...")

# ── Start MQTT client ─────────────────────────────────────────────────────────
try:
    mqc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqc.on_connect    = on_connect
    mqc.on_message    = on_message
    mqc.on_disconnect = on_disconnect
    mqc.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    mqc.loop_forever()

except KeyboardInterrupt:
    print(f"\n\nBridge stopped.")
    print(f"Stats: received={stats['received']}  logged={stats['logged']}  failed={stats['failed']}")
    mqc.disconnect()

except ConnectionRefusedError:
    print(f"\nERROR: Cannot connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    print("       Is the mqtt-broker container running?")
    print("       docker compose ps")
    sys.exit(1)
