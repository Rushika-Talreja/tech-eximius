// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

contract ERC4626CleanVault {
    IERC20 public immutable asset;
    uint256 public totalAssets;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;

    // Virtual shares and assets offset to prevent donation/inflation attacks
    uint256 private constant VIRTUAL_OFFSET = 1;

    constructor(IERC20 _asset) {
        asset = _asset;
        totalAssets = 100;
        totalSupply = 50;
    }

    function convertToShares(uint256 assets) public view returns (uint256) {
        return (assets * (totalSupply + VIRTUAL_OFFSET)) / (totalAssets + VIRTUAL_OFFSET);
    }

    function convertToAssets(uint256 shares) public view returns (uint256) {
        return (shares * (totalAssets + VIRTUAL_OFFSET)) / (totalSupply + VIRTUAL_OFFSET);
    }

    function previewDeposit(uint256 assets) public view returns (uint256) {
        // Standard compliant: rounds down
        return (assets * (totalSupply + VIRTUAL_OFFSET)) / (totalAssets + VIRTUAL_OFFSET);
    }

    function previewRedeem(uint256 shares) public view returns (uint256) {
        // Standard compliant: rounds down
        return (shares * (totalAssets + VIRTUAL_OFFSET)) / (totalSupply + VIRTUAL_OFFSET);
    }

    function deposit(uint256 assets, address receiver) external returns (uint256 shares) {
        shares = previewDeposit(assets);
        totalAssets += assets;
        totalSupply += shares;
        balanceOf[receiver] += shares;
    }

    function withdraw(uint256 assets, address receiver, address owner) external returns (uint256 shares) {
        // Rounds up on withdraw
        shares = (assets * (totalSupply + VIRTUAL_OFFSET) + (totalAssets + VIRTUAL_OFFSET - 1)) / (totalAssets + VIRTUAL_OFFSET);
        require(balanceOf[owner] >= shares, "INSUFFICIENT_SHARES");
        balanceOf[owner] -= shares;
        totalSupply -= shares;
        totalAssets -= assets;
    }

    function redeem(uint256 shares, address receiver, address owner) external returns (uint256 assets) {
        assets = previewRedeem(shares);
        require(balanceOf[owner] >= shares, "INSUFFICIENT_SHARES");
        balanceOf[owner] -= shares;
        totalSupply -= shares;
        totalAssets -= assets;
    }
}

