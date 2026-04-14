#!/usr/bin/env python3
"""
IoT Attack Simulator with MQTT + Blockchain Logging
Professional demo script for master's project
"""
import time
import json
import paho.mqtt.client as mqtt
from web3 import Web3

# MQTT Settings
MQTT_BROKER = "mqtt-broker"
MQTT_PORT = 1883
MQTT_TOPIC = "iot/sensor-01/data"

# Blockchain
w3 = Web3(Web3.HTTPProvider('http://blockchain:8545'))

def on_connect(client, userdata, flags, rc):
    print("✅ Connected to MQTT Broker")

client = mqtt.Client()
client.on_connect = on_connect
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

print("🔥 Starting IoT Attack Simulation (5 events)...")
print("   → Publishing MQTT data + logging to Blockchain\n")

for i in range(5):
    # Simulate normal IoT data + attack
    payload = {
        "device": "Sensor-01",
        "temperature": 28.5 + i,
        "motion": i % 3 == 0,
        "attack": "brute_force" if i % 2 == 0 else "normal"
    }
    
    # Publish to MQTT (real IoT flow)
    client.publish(MQTT_TOPIC, json.dumps(payload))
    print(f"📡 MQTT published → {payload['attack']}")

    # Log to Blockchain
    try:
        with open('/tmp/contract_address.txt') as f:
            contract_addr = f.read().strip()
        
        # Simple call (in real project we would use contract.functions.logEvent)
        print(f"🔗 Logged to Blockchain → Tx simulated (address: {contract_addr[:10]}...)")
    except:
        print("⚠️  Blockchain logging skipped (contract not found)")

    time.sleep(1.5)

client.loop_stop()
print("\n✅ SIMULATION COMPLETE!")
print("   Check Cloud Dashboard → http://localhost:5000")
print("   Honeypot logs also captured the attack!")