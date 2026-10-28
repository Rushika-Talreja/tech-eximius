// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract CappedToken {
    address public owner;
    uint256 public constant MAX_SUPPLY = 1000000;
    uint256 public totalSupply;
    mapping(address => uint256) public balances;

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function mint(address to, uint256 amount) external onlyOwner {
        require(totalSupply + amount <= MAX_SUPPLY, "EXCEEDS_CAP");
        totalSupply += amount;
        balances[to] += amount;
    }
}

