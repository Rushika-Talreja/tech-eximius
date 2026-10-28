// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ReentrancyClassic
 * @notice Classic vulnerable vault with state change after external call.
 */
contract ReentrancyClassic {
    mapping(address => uint256) public userBalances;

    event Deposited(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);

    function deposit() external payable {
        userBalances[msg.sender] += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    // Vulnerable: external ether transfer before state update
    function withdrawBalance() external {
        uint256 balance = userBalances[msg.sender];
        require(balance > 0, "NO_FUNDS");

        (bool success, ) = msg.sender.call{value: balance}("");
        require(success, "ETH_TRANSFER_FAILED");

        userBalances[msg.sender] = 0;
        emit Withdrawn(msg.sender, balance);
    }
}

