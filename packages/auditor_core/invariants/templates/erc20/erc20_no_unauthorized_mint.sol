// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC20MintCheck {
    function totalSupply() external view returns (uint256);
}

contract ERC20NoUnauthorizedMintInvariant {
    IERC20MintCheck public target;
    uint256 public initialSupply;

    constructor(address _target) {
        target = IERC20MintCheck(_target);
        initialSupply = target.totalSupply();
    }

    function checkSupplyCap(uint256 maxExpectedSupply) external view {
        require(target.totalSupply() <= maxExpectedSupply, "INVARIANT_VIOLATION: unauthorized supply inflation");
    }
}

