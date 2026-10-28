// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract BrokenVault {
    uint256 public balance;

    function invalidLogic() external {
        // Undeclared identifier and syntax failure
        undeclaredVariable = 42 + NonExistentType;
    }
}

