// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC4626Minimal {
    function asset() external view returns (address);
    function totalAssets() external view returns (uint256);
    function convertToShares(uint256 assets) external view returns (uint256);
    function convertToAssets(uint256 shares) external view returns (uint256);
    function previewDeposit(uint256 assets) external view returns (uint256);
    function previewRedeem(uint256 shares) external view returns (uint256);
}

contract ERC4626PreviewRedeemDepositInvariant {
    IERC4626Minimal public target;

    constructor(address _target) {
        target = IERC4626Minimal(_target);
    }

    function checkPreviewRedeemDeposit(uint256 assets) external view {
        if (assets == 0 || assets > 1e36) return;
        uint256 shares = target.previewDeposit(assets);
        uint256 redeemedAssets = target.previewRedeem(shares);
        require(
            redeemedAssets <= assets,
            "INVARIANT_VIOLATION: previewRedeem(previewDeposit(x)) > x allows risk-free asset extraction"
        );
    }
}

