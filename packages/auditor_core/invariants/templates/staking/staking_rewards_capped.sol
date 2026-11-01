// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IStakingPool {
    function totalRewardsDistributed() external view returns (uint256);
    function totalRewardsFunded() external view returns (uint256);
}

contract StakingRewardsCappedInvariant {
    IStakingPool public target;

    constructor(address _target) {
        target = IStakingPool(_target);
    }

    function checkRewardsCapped() external view {
        require(
            target.totalRewardsDistributed() <= target.totalRewardsFunded(),
            "INVARIANT_VIOLATION: rewards claimed exceed rewards funded"
        );
    }
}

