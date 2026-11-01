// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface ILendingPosition {
    function isSolvent(address user) external view returns (bool);
    function liquidate(address user, uint256 debtToCover) external returns (bool);
}

contract LendingHealthyLiquidationInvariant {
    ILendingPosition public target;

    constructor(address _target) {
        target = ILendingPosition(_target);
    }

    function checkLiquidationRevertsOnHealthy(address healthyUser, uint256 amount) external {
        if (target.isSolvent(healthyUser)) {
            try target.liquidate(healthyUser, amount) {
                revert("INVARIANT_VIOLATION: liquidation succeeded against a solvent/healthy position");
            } catch {
                // Correct behavior: liquidation should revert
            }
        }
    }
}

