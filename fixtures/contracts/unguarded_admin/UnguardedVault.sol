// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract UnguardedVault {
    uint256 public totalSupply;
    mapping(address => uint256) public balances;

    function mint(address to, uint256 amount) external {
        // Missing access control: anybody can mint!
        totalSupply += amount;
        balances[to] += amount;
    }
}

