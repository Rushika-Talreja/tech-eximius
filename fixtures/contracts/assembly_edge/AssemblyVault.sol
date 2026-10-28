// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract AssemblyVault {
    address public owner;
    uint256 public total;

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function executeAssembly(uint256 value) external onlyOwner {
        assembly {
            sstore(total.slot, value)
        }
    }
}

