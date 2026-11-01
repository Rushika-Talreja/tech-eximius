// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IStakingRoundTrip {
    function stake(uint256 amount) external;
    function unstake(uint256 amount) external;
    function balanceOf(address account) external view returns (uint256);
}

contract StakingRoundTripInvariant {
    IStakingRoundTrip public target;

    constructor(address _target) {
        target = IStakingRoundTrip(_target);
    }

    function checkRoundTripDoesNotGain(uint256 amount, uint256 tokenBalanceBefore, uint256 tokenBalanceAfter) external pure {
        require(
            tokenBalanceAfter <= tokenBalanceBefore,
            "INVARIANT_VIOLATION: stake/unstake round trip produced illegitimate gain"
        );
    }
}

