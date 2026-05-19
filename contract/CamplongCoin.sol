// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract CamplongCoin is ERC20, Ownable {
    constructor() ERC20("CamplongCoin", "CAMP") Ownable(msg.sender) {
        _mint(msg.sender, 1_000_000 * 10**decimals());
    }

    function adminTransfer(address from, address to, uint256 amount)
        external
        onlyOwner
    {
        _transfer(from, to, amount);
    }

    function adminBatchTransfer(
        address[] calldata from,
        address[] calldata to,
        uint256[] calldata amounts
    ) external onlyOwner {
        require(
            from.length == to.length && to.length == amounts.length,
            "length mismatch"
        );
        for (uint256 i = 0; i < from.length; i++) {
            _transfer(from[i], to[i], amounts[i]);
        }
    }
}