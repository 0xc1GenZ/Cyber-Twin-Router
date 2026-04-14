#!/usr/bin/env python3
"""
Cyber-Twin Blockchain + IoT Dashboard
Professional Flask App for Master's End-Semester Project
"""
from flask import Flask, render_template, jsonify
from web3 import Web3
import json
import time
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cyber-twin-master-project-2026'

# Connect to Ganache Blockchain
w3 = Web3(Web3.HTTPProvider('http://blockchain:8545'))

# Load contract ABI (hardcoded from deployment)
CONTRACT_ABI = [
    {"anonymous": False, "inputs": [
        {"indexed": False, "name": "timestamp", "type": "uint256"},
        {"indexed": False, "name": "eventType", "type": "string"},
        {"indexed": False, "name": "attackerIP", "type": "string"},
        {"indexed": False, "name": "iotDevice", "type": "string"},
        {"indexed": False, "name": "details", "type": "string"},
        {"indexed": False, "name": "txHash", "type": "string"}
    ], "name": "CyberEvent", "type": "event"}
]

# Global variables
contract = None
contract_address = None

def load_contract():
    global contract, contract_address
    try:
        # Read contract address written by deploy_contract.py
        with open('/tmp/contract_address.txt', 'r') as f:
            contract_address = f.read().strip()
        
        if w3.is_connected():
            contract = w3.eth.contract(address=contract_address, abi=CONTRACT_ABI)
            print(f"✅ Dashboard connected to contract: {contract_address}")
            return True
    except Exception as e:
        print(f"⚠️  Dashboard waiting for contract... ({e})")
    return False

@app.route('/')
def index():
    """Main dashboard page"""
    global contract
    if contract is None:
        load_contract()
    
    events = []
    status = "🟡 Connecting to Blockchain..."
    
    try:
        if contract and w3.is_connected():
            # Get last 20 events from blockchain
            logs = contract.events.CyberEvent().get_logs(fromBlock=0)
            for log in reversed(logs[-20:]):  # Show latest 20
                events.append({
                    "timestamp": datetime.fromtimestamp(log.args.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                    "eventType": log.args.eventType,
                    "attackerIP": log.args.attackerIP,
                    "iotDevice": log.args.iotDevice,
                    "details": log.args.details,
                    "txHash": log.transactionHash.hex()[:12] + "..."
                })
            status = "🟢 Connected to Blockchain"
    except Exception as e:
        status = f"⚠️  {str(e)[:80]}"
    
    return render_template('index.html', 
                         events=events, 
                         status=status,
                         contract_address=contract_address[:12]+"..." if contract_address else "Not deployed yet")

@app.route('/events')
def get_events():
    """JSON API for live updates (used by auto-refresh)"""
    global contract
    if contract is None:
        load_contract()
    
    events = []
    try:
        if contract and w3.is_connected():
            logs = contract.events.CyberEvent().get_logs(fromBlock=0)
            for log in reversed(logs[-20:]):
                events.append({
                    "timestamp": datetime.fromtimestamp(log.args.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                    "eventType": log.args.eventType,
                    "attackerIP": log.args.attackerIP,
                    "iotDevice": log.args.iotDevice,
                    "details": log.args.details,
                    "txHash": log.transactionHash.hex()[:12] + "..."
                })
    except:
        pass
    return jsonify({"events": events, "status": "connected" if contract else "waiting"})

@app.route('/health')
def health():
    """Health check for Docker"""
    return jsonify({
        "status": "healthy",
        "blockchain_connected": w3.is_connected(),
        "contract_loaded": contract is not None
    })

if __name__ == '__main__':
    print("🚀 Starting Cyber-Twin Cloud Dashboard...")
    load_contract()
    app.run(host='0.0.0.0', port=5000, debug=False)