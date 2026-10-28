// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VaultBasic
 * @notice Simple ownable vault for testing privileged roles and blast scoring.
 */
contract VaultBasic {
    address public owner;
    uint256 public totalDeposits;
    mapping(address => uint256) public balances;
    bool public paused;

    event Deposit(address indexed user, uint256 amount);
    event Withdraw(address indexed user, uint256 amount);
    event Paused(bool isPaused);
    event EmergencyDrain(address indexed owner, uint256 amount);

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "PAUSED");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable whenNotPaused {
        require(msg.value > 0, "ZERO_DEPOSIT");
        balances[msg.sender] += msg.value;
        totalDeposits += msg.value;
        emit Deposit(msg.sender, msg.value);
    }

    function withdraw(uint256 amount) external whenNotPaused {
        require(balances[msg.sender] >= amount, "INSUFFICIENT_BALANCE");
        balances[msg.sender] -= amount;
        totalDeposits -= amount;
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "TRANSFER_FAILED");
        emit Withdraw(msg.sender, amount);
    }

    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
        emit Paused(_paused);
    }

    function emergencyDrain() external onlyOwner {
        uint256 balance = address(this).balance;
        (bool ok, ) = owner.call{value: balance}("");
        require(ok, "DRAIN_FAILED");
        emit EmergencyDrain(owner, balance);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "INVALID_ADDRESS");
        owner = newOwner;
    }
}

