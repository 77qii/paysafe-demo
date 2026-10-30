// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MerchantRegistry
 * @notice Keeps track of which merchants are licensed to accept PaySafe prepayments.
 *         Only the regulator (the account that deployed the contract) can license
 *         or revoke a merchant. No oracle, no external calls.
 */
contract MerchantRegistry {
    /// @notice The regulator account allowed to license / revoke merchants.
    address public regulator;

    mapping(address => bool) private _licensed;
    address[] private _merchantList;

    event MerchantRegistered(address indexed merchant, address indexed regulator);
    event MerchantRevoked(address indexed merchant, address indexed regulator);

    modifier onlyRegulator() {
        require(msg.sender == regulator, "Only the regulator can perform this action.");
        _;
    }

    constructor(address regulator_) {
        require(regulator_ != address(0), "Regulator address is required.");
        regulator = regulator_;
    }

    /**
     * @notice License a merchant so it can receive prepaid packages.
     */
    function registerMerchant(address merchant) external onlyRegulator {
        require(merchant != address(0), "Merchant address is required.");
        require(!_licensed[merchant], "Merchant is already licensed.");

        _licensed[merchant] = true;
        _merchantList.push(merchant);

        emit MerchantRegistered(merchant, msg.sender);
    }

    /**
     * @notice Revoke a merchant license. Existing packages are not modified.
     */
    function revokeMerchant(address merchant) external onlyRegulator {
        require(_licensed[merchant], "Merchant is not licensed.");

        _licensed[merchant] = false;

        emit MerchantRevoked(merchant, msg.sender);
    }

    /// @notice True if the merchant is currently licensed by the regulator.
    function isLicensed(address merchant) external view returns (bool) {
        return _licensed[merchant];
    }

    /// @notice Number of merchants that have ever been registered.
    function merchantCount() external view returns (uint256) {
        return _merchantList.length;
    }

    /// @notice Merchant address at a given index (registration order).
    function merchantAt(uint256 index) external view returns (address) {
        return _merchantList[index];
    }
}
