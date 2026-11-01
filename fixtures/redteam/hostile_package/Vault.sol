// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract SafeVault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }
}

