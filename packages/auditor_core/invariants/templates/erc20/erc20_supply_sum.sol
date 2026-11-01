// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC20Minimal {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
}

contract ERC20SupplySumInvariant {
    IERC20Minimal public target;
    address[] public knownAccounts;

    constructor(address _target, address[] memory _accounts) {
        target = IERC20Minimal(_target);
        knownAccounts = _accounts;
    }

    function invariant_totalSupplyMatchesTrackedBalances() public view {
        uint256 sum = 0;
        for (uint256 i = 0; i < knownAccounts.length; i++) {
            sum += target.balanceOf(knownAccounts[i]);
        }
        require(target.totalSupply() >= sum, "INVARIANT_VIOLATION: totalSupply less than sum of balances");
    }
}

