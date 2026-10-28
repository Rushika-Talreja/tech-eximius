// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

abstract contract Ownable2Step {
    address public owner;
    address public pendingOwner;

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        pendingOwner = newOwner;
    }

    function acceptOwnership() external {
        require(msg.sender == pendingOwner, "NOT_PENDING_OWNER");
        owner = pendingOwner;
        pendingOwner = address(0);
    }
}

contract TimelockedAdmin is Ownable2Step {
    uint256 public constant DELAY = 2 days;
    uint256 public queuedTime;
    address public oracle;

    constructor() {
        owner = msg.sender;
    }

    function queueChangeOracle() external onlyOwner {
        queuedTime = block.timestamp;
    }

    function setOracle(address newOracle) external onlyOwner {
        require(queuedTime > 0, "NOT_QUEUED");
        require(block.timestamp >= queuedTime + 2 days, "TIMELOCK_PENDING");
        oracle = newOracle;
        queuedTime = 0;
    }
}

