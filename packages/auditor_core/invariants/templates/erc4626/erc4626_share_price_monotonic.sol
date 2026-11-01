// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC4626SharePrice {
    function totalAssets() external view returns (uint256);
    function totalSupply() external view returns (uint256);
    function convertToAssets(uint256 shares) external view returns (uint256);
}

contract ERC4626SharePriceMonotonicInvariant {
    IERC4626SharePrice public target;
    uint256 public lastSharePrice;

    constructor(address _target) {
        target = IERC4626SharePrice(_target);
        lastSharePrice = target.convertToAssets(1e18);
    }

    function checkSharePriceMonotonic() external {
        uint256 currentPrice = target.convertToAssets(1e18);
        if (lastSharePrice > 0) {
            require(
                currentPrice >= lastSharePrice,
                "INVARIANT_VIOLATION: share price decreased during operation"
            );
        }
        lastSharePrice = currentPrice;
    }
}

