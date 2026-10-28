// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract CustomVault {
    address public governance;
    mapping(address => bool) public admins;
    address public oracle;
    uint256 public protocolFee;

    modifier onlyAdmin() {
        require(admins[msg.sender], "NOT_ADMIN");
        _;
    }

    modifier onlyGovernance() {
        require(msg.sender == governance, "NOT_GOVERNANCE");
        _;
    }

    constructor() {
        governance = msg.sender;
        admins[msg.sender] = true;
    }

    function setFee(uint256 newFee) external onlyAdmin {
        protocolFee = newFee;
    }

    function setOracle(address newOracle) external onlyGovernance {
        oracle = newOracle;
    }
}

