// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract CyberLogger {
    event CyberEvent(
        uint256 timestamp,
        string eventType,
        string attackerIP,
        string iotDevice,
        string details
    );

    function logEvent(
        string memory eventType,
        string memory attackerIP,
        string memory iotDevice,
        string memory details
    ) public {
        emit CyberEvent(block.timestamp, eventType, attackerIP, iotDevice, details);
    }
}
