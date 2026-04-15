#!/usr/bin/env python3

# ── Auto-activate project venv if not already in one ─────────────────────────
import sys, os

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)   # scripts/ is one level down
_venv_python = os.path.join(_project_root, ".venv", "bin", "python3")

if (os.path.exists(_venv_python)
        and sys.executable != _venv_python
        and "VIRTUAL_ENV" not in os.environ):
    print(f"🔁 Re-launching with venv python: {_venv_python}")
    os.execv(_venv_python, [_venv_python] + sys.argv)

# ── Normal imports (now guaranteed to be inside venv) ────────────────────────
try:
    import time, json, random
    import paho.mqtt.client as mqtt
    from web3 import Web3
except ImportError as e:
    print(f"\n❌ Import error: {e}")
    print("   Fix: Run from project root with venv active:")
    print("        source .venv/bin/activate")
    print("        python3 scripts/simulate-iot-attack.py")
    print("   Or use the wrapper:  ./run-demo.sh")
    sys.exit(1)

# ── Config ───────────────────────────────────────────────────────────────────
MQTT_BROKER    = os.getenv("MQTT_BROKER",    "localhost")
MQTT_PORT      = int(os.getenv("MQTT_PORT",  "1883"))
MQTT_TOPIC     = "iot/sensor-01/data"
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

ATTACK_SCENARIOS = [
    ("BruteForce",     "Router-SSH",       "Multiple failed SSH login attempts"),
    ("DDoS",           "Sensor-01",        "High-volume UDP flood on IoT device"),
    ("PortScan",       "Router-Honeypot",  "Nmap-style port scan detected"),
    ("MQTTInject",     "MQTT-Broker",      "Malicious payload injected into MQTT topic"),
    ("FirmwareTamper", "SmartMeter-02",    "Unauthorized firmware update attempt"),
    ("SQLInjection",   "Cloud-Dashboard",  "SQL injection attempt on dashboard API"),
    ("Ransomware",     "Router-Storage",   "Ransomware encryption started on attached storage"),
    ("MITM",           "IoT-Camera",       "Man-in-the-Middle attack on camera stream"),
    ("ZeroDayExploit", "FRR-Router",       "Zero-day exploit on FRRouting daemon"),
    ("DataExfil",      "Sensor-Cluster",   "Sensitive data exfiltration detected"),
    ("C2Beacon",       "Smart-Thermostat", "Command-and-control beacon to external IP"),
    ("CredHarvest",    "Router-WebUI",     "Credential harvesting via phishing overlay"),
]

def random_ip():
    """Generate a random-looking attacker IP."""
    prefixes = ["192.168", "10.0", "172.16", "203.0.113", "45.77", "198.51.100"]
    return f"{random.choice(prefixes)}.{random.randint(1,254)}.{random.randint(1,254)}"

# ── PoA Middleware (Ganache uses Proof-of-Authority) ─────────────────────────
def apply_poa_middleware(w3_instance):
    """Apply PoA middleware — handles both web3.py v6 and v7."""
    try:
        from web3.middleware import ExtraDataToPOAMiddleware   # web3 v7
        w3_instance.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        print("   PoA middleware applied (web3 v7)")
        return True
    except ImportError:
        pass
    try:
        from web3.middleware import geth_poa_middleware        # web3 v6
        w3_instance.middleware_onion.inject(geth_poa_middleware, layer=0)
        print("   PoA middleware applied (web3 v6)")
        return True
    except ImportError:
        pass
    print("   ⚠️  PoA middleware not available — continuing without it")
    return False

# ── Connect Blockchain ────────────────────────────────────────────────────────
print(f"\n{'='*55}")
print("  Cyber-Twin Router — IoT Attack Simulator v4.0")
print(f"{'='*55}\n")

print(f"🔗 Connecting to Ganache at {BLOCKCHAIN_URL} ...")
w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_URL))
apply_poa_middleware(w3)

if not w3.is_connected():
    print("❌ Cannot connect to Ganache.")
    print("   → Make sure containers are running: docker compose ps")
    print("   → Check Ganache port: curl -s http://localhost:8545")
    sys.exit(1)

print(f"✅ Blockchain connected  (chain id: {w3.eth.chain_id}, "
      f"block: #{w3.eth.block_number})")

accounts = w3.eth.accounts
if not accounts:
    print("❌ No accounts found in Ganache.")
    sys.exit(1)
w3.eth.default_account = accounts[0]
print(f"   Using account: {accounts[0]}")

# ── Load Contract ─────────────────────────────────────────────────────────────
if not os.path.exists(CONTRACT_FILE):
    print(f"\n❌ Contract address file not found: {CONTRACT_FILE}")
    print("   → Run first: python3 scripts/deploy_contract.py")
    print("   → Or from project root: source .venv/bin/activate && python3 scripts/deploy_contract.py")
    sys.exit(1)

with open(CONTRACT_FILE, 'r') as f:
    contract_address = f.read().strip()

if not contract_address or not contract_address.startswith("0x"):
    print(f"❌ Invalid contract address in {CONTRACT_FILE}: '{contract_address}'")
    sys.exit(1)

print(f"📍 Contract address: {contract_address}")
contract = w3.eth.contract(
    address=Web3.to_checksum_address(contract_address),
    abi=CONTRACT_ABI
)

# Verify contract is callable
try:
    # Try a dry-run call to confirm the contract exists on-chain
    contract.functions.logEvent("test", "0.0.0.0", "test", "test").call(
        {"from": w3.eth.default_account}
    )
    print("✅ Contract verified on-chain.")
except Exception as e:
    print(f"⚠️  Contract call check returned: {e}")
    print("   (This may be OK — proceeding with actual transactions)")

# ── Connect MQTT ──────────────────────────────────────────────────────────────
mqtt_connected = False

def on_connect(client, userdata, flags, rc, properties=None):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print("✅ MQTT connected.")
    else:
        print(f"⚠️  MQTT connection failed (rc={rc}) — blockchain logging will continue.")

try:
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_connect
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    time.sleep(1.5)
except Exception as e:
    print(f"⚠️  MQTT unavailable ({e}) — continuing with blockchain only.")
    mqtt_client = None

# ── Continuous Attack Loop ────────────────────────────────────────────────────
print(f"\n🚨 ATTACK SIMULATION RUNNING  (Ctrl+C to stop)")
print(f"   Dashboard → http://localhost:5000")
print("-" * 55)

attack_count = 0
success_count = 0

try:
    while True:
        attack_count += 1
        event_type, iot_device, details = random.choice(ATTACK_SCENARIOS)
        attacker_ip = random_ip()

        print(f"\n[{attack_count:03d}] {event_type:<16} from {attacker_ip}")
        print(f"       Device: {iot_device}")

        # 1. Publish to MQTT
        if mqtt_client and mqtt_connected:
            try:
                payload = json.dumps({
                    "device":     iot_device,
                    "attack":     event_type,
                    "attackerIP": attacker_ip,
                    "timestamp":  int(time.time())
                })
                result = mqtt_client.publish(MQTT_TOPIC, payload)
                result.wait_for_publish(timeout=2)
                print(f"   📡 MQTT published to {MQTT_TOPIC}")
            except Exception as e:
                print(f"   ⚠️  MQTT failed: {e}")
        else:
            print(f"   ⚠️  MQTT skipped (not connected)")

        # 2. Log to Blockchain
        try:
            tx_hash = contract.functions.logEvent(
                event_type,
                attacker_ip,
                iot_device,
                details
            ).transact({"from": w3.eth.default_account, "gas": 300000})

            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

            if receipt.status == 1:
                success_count += 1
                print(f"   🔗 Blockchain ✅  block #{receipt.blockNumber}  "
                      f"gas used: {receipt.gasUsed}  "
                      f"tx: {tx_hash.hex()[:14]}...")
            else:
                print(f"   🔗 Blockchain ❌  transaction REVERTED  "
                      f"tx: {tx_hash.hex()[:14]}...")

        except Exception as e:
            print(f"   🔗 Blockchain ❌  {type(e).__name__}: {e}")

        print(f"   ✦ Total: {attack_count} sent, {success_count} confirmed on-chain")
        time.sleep(random.uniform(2.0, 4.5))

except KeyboardInterrupt:
    print(f"\n\n⛔ Stopped by user.")
finally:
    if mqtt_client:
        mqtt_client.loop_stop()
    print(f"\n📊 Final: {attack_count} attacks, {success_count} blockchain-confirmed")
    print(f"   Refresh http://localhost:5000 to see all events")
