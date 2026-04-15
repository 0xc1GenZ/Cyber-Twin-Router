pragma solidity ^0.8.20;

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
        // Emit the event with real data
        emit CyberEvent(
            block.timestamp,
            eventType,
            attackerIP,
            iotDevice,
            details,
            "0x" // txHash is filled by the simulator after the tx
        );
    }
}
