// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

contract SimpleVault {
    IERC20 public immutable asset;
    address public owner;
    uint256 public totalAssets;

    mapping(address => uint256) public balances;

    event Deposit(address indexed caller, address indexed owner, uint256 assets);
    event Withdraw(address indexed caller, address indexed receiver, address indexed owner, uint256 assets);

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    constructor(IERC20 _asset) {
        asset = _asset;
        owner = msg.sender;
    }

    function deposit(uint256 amount) external returns (bool) {
        require(amount > 0, "ZERO_DEPOSIT");
        require(asset.transferFrom(msg.sender, address(this), amount), "TRANSFER_FAILED");
        balances[msg.sender] += amount;
        totalAssets += amount;
        emit Deposit(msg.sender, msg.sender, amount);
        return true;
    }

    function withdraw(uint256 amount, address receiver) external returns (bool) {
        require(amount > 0, "ZERO_WITHDRAW");
        require(balances[msg.sender] >= amount, "INSUFFICIENT_BALANCE");
        balances[msg.sender] -= amount;
        totalAssets -= amount;
        require(asset.transfer(receiver, amount), "TRANSFER_FAILED");
        emit Withdraw(msg.sender, receiver, msg.sender, amount);
        return true;
    }

    function pauseVault() external onlyOwner {
        // Administrative action
    }

    function withdrawAll(address payable recipient) external onlyOwner {
        uint256 balance = address(this).balance;
        (bool ok, ) = recipient.call{value: balance}("");
        require(ok, "TRANSFER_FAILED");
    }

    function mint(address to, uint256 amount) external onlyOwner {
        balances[to] += amount;
        totalAssets += amount;
    }
}

