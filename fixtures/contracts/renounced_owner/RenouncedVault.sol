// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract RenouncedVault {
    address public owner;
    bool public paused;

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    constructor() {
        owner = address(0);
    }

    function pause() external onlyOwner {
        paused = true;
    }
}

