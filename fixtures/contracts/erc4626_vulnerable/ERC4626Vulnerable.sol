// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

contract ERC4626VulnerableVault {
    IERC20 public immutable asset;
    uint256 public totalAssets;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;

    constructor(IERC20 _asset) {
        asset = _asset;
        // Initial state simulating non-empty vault
        totalAssets = 100;
        totalSupply = 50;
    }

    function convertToShares(uint256 assets) public view returns (uint256) {
        if (totalAssets == 0 || totalSupply == 0) return assets;
        return (assets * totalSupply) / totalAssets;
    }

    function convertToAssets(uint256 shares) public view returns (uint256) {
        if (totalSupply == 0) return shares;
        return (shares * totalAssets) / totalSupply;
    }

    function previewDeposit(uint256 assets) public view returns (uint256) {
        if (totalAssets == 0 || totalSupply == 0) return assets;
        // Erroneous rounding up on previewDeposit
        return (assets * totalSupply + (totalAssets - 1)) / totalAssets;
    }

    function previewRedeem(uint256 shares) public view returns (uint256) {
        if (totalSupply == 0) return shares;
        // Erroneous rounding up on previewRedeem allows previewRedeem(previewDeposit(x)) > x
        return (shares * totalAssets + (totalSupply - 1)) / totalSupply;
    }

    function deposit(uint256 assets, address receiver) external returns (uint256 shares) {
        shares = previewDeposit(assets);
        totalAssets += assets;
        totalSupply += shares;
        balanceOf[receiver] += shares;
    }

    function withdraw(uint256 assets, address receiver, address owner) external returns (uint256 shares) {
        shares = convertToShares(assets);
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

