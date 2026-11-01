// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC20Transfer {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
}

contract ERC20TransferInvariant {
    IERC20Transfer public target;

    constructor(address _target) {
        target = IERC20Transfer(_target);
    }

    function checkTransferSenderBalance(address sender, address recipient, uint256 amount) external {
        uint256 senderBefore = target.balanceOf(sender);
        try target.transfer(recipient, amount) returns (bool success) {
            if (success && sender != recipient && amount > 0) {
                uint256 senderAfter = target.balanceOf(sender);
                require(senderAfter <= senderBefore, "INVARIANT_VIOLATION: transfer increased sender balance");
            }
        } catch {}
    }
}

