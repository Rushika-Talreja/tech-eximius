// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

abstract contract BaseAuth {
    address public admin;

    modifier onlyAdmin() {
        _requireAdmin();
        _;
    }

    function _requireAdmin() internal view {
        require(msg.sender == admin, "NOT_ADMIN");
    }
}

contract InheritedVault is BaseAuth {
    address public oracle;

    constructor() {
        admin = msg.sender;
    }

    function setOracle(address newOracle) external onlyAdmin {
        oracle = newOracle;
    }
}

