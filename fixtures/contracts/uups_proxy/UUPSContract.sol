// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

abstract contract UUPSUpgradeable {
    function upgradeToAndCall(address newImplementation, bytes memory data) external payable {
        _authorizeUpgrade(newImplementation);
    }

    function _authorizeUpgrade(address newImplementation) internal virtual;
}

contract MyUUPS is UUPSUpgradeable {
    address public owner;

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {
        // Upgrade auth check
    }
}

