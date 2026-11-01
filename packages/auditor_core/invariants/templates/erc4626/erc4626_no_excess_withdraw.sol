// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC4626WithdrawCheck {
    function convertToAssets(uint256 shares) external view returns (uint256);
    function previewWithdraw(uint256 assets) external view returns (uint256);
}

contract ERC4626NoExcessWithdrawInvariant {
    IERC4626WithdrawCheck public target;

    constructor(address _target) {
        target = IERC4626WithdrawCheck(_target);
    }

    function checkWithdrawCoverage(uint256 assets) external view {
        if (assets == 0 || assets > 1e36) return;
        uint256 requiredShares = target.previewWithdraw(assets);
        uint256 redeemableAssets = target.convertToAssets(requiredShares);
        require(
            redeemableAssets >= assets,
            "INVARIANT_VIOLATION: user withdraws more than assets owned by shares"
        );
    }
}

