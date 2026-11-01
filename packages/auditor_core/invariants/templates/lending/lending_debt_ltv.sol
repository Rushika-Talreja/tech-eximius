// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface ILendingPool {
    function totalBorrows() external view returns (uint256);
    function totalCollateralValue() external view returns (uint256);
    function maxLTVBps() external view returns (uint256); // in basis points, e.g. 8000 = 80%
}

contract LendingDebtLTVInvariant {
    ILendingPool public target;

    constructor(address _target) {
        target = ILendingPool(_target);
    }

    function checkDebtLTV() external view {
        uint256 maxDebt = (target.totalCollateralValue() * target.maxLTVBps()) / 10000;
        require(
            target.totalBorrows() <= maxDebt,
            "INVARIANT_VIOLATION: total debt exceeds maximum collateral LTV limit"
        );
    }
}

