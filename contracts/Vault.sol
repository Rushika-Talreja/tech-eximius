// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Demo contract with intentional bugs. Do NOT deploy.
contract VulnerableVault {
    mapping(address => uint256) public balances;

    // No KYC check: anyone can deposit anonymously
    // Marketing claim: "guaranteed 12% yearly return"
    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    // BUG: sends ETH before updating the balance (re-entrancy)
    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "Transfer failed");
        balances[msg.sender] -= amount;
    }
}