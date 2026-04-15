#!/usr/bin/env python3

import json
import time
from web3 import Web3
from solcx import compile_source, install_solc

# Install Solidity compiler (once, with error handling)
try:
    install_solc('0.8.0')
    print("✅ solc 0.8.0 installed successfully.")
except Exception as e:
    print(f"⚠️  solc install warning (non-fatal): {e}")

CONTRACT_SOURCE = '''
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract CyberLogger {
    event CyberEvent(
        uint256 timestamp,
        string eventType,
        string attackerIP,
        string iotDevice,
        string details,
        string txHash
    );

    function logEvent(
        string memory eventType,
        string memory attackerIP,
        string memory iotDevice,
        string memory details
    ) public {
        emit CyberEvent(block.timestamp, eventType, attackerIP, iotDevice, details, "");
    }
}
'''

print("🔨 Compiling CyberLogger.sol...")

# FIX: Pass solc_version explicitly so solcx knows which compiler to use
compiled_sol = compile_source(
    CONTRACT_SOURCE,
    output_values=['abi', 'bin'],
    solc_version='0.8.0'          # <-- This was the missing piece
)
contract_interface = compiled_sol['<stdin>:CyberLogger']

# Connect to local Ganache
w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))

if not w3.is_connected():
    print("❌ Cannot connect to Ganache at http://localhost:8545")
    print("   → Make sure ganache-blockchain container is Up")
    exit(1)

w3.eth.default_account = w3.eth.accounts[0]

print("🚀 Deploying contract to Ganache...")
CyberLogger = w3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bin'])
tx_hash = CyberLogger.constructor().transact()
tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

contract_address = tx_receipt.contractAddress
print(f"✅ CyberLogger deployed successfully!")
print(f"📍 Contract Address: {contract_address}")

# Save address for simulator + dashboard
with open('/tmp/contract_address.txt', 'w') as f:
    f.write(contract_address)

print("💾 Contract address saved to /tmp/contract_address.txt")
