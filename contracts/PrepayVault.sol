// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./MerchantRegistry.sol";

/**
 * @title PrepayVault
 * @notice Holds prepaid consumer funds in escrow and releases them to the merchant
 *         one session at a time.
 *
 * Core idea:
 *   - The consumer pays the full package price into this contract.
 *   - Nothing is transferred to the merchant at purchase time.
 *   - Every `useSession()` call only *marks* HK$500 as released (bookkeeping).
 *   - The merchant can withdraw at most `releasedAmount - withdrawnAmount`.
 *   - If the regulator closes the merchant, the consumer gets back
 *     `totalPaid - releasedAmount`.
 *
 * Demo unit convention (simulation only, no real HKD is involved):
 *   1 HKD  = 1e15 wei
 *   Package = 12 sessions * HK$500 = HK$6,000 = 6e18 wei (6 ETH on the local chain)
 */
contract PrepayVault {
    // ---------------------------------------------------------------------
    // Fixed business parameters (single package, per project scope)
    // ---------------------------------------------------------------------
    uint256 public constant HKD = 1e15; // 1 HKD expressed in wei
    uint256 public constant SESSIONS_PER_PACKAGE = 12;
    uint256 public constant PRICE_PER_SESSION = 500 * HKD;
    uint256 public constant PACKAGE_PRICE = SESSIONS_PER_PACKAGE * PRICE_PER_SESSION; // 6e18 wei

    struct Package {
        address consumer;
        address merchant;
        uint256 totalPaid;
        uint256 sessionsUsed;
        uint256 releasedAmount;
        uint256 withdrawnAmount;
        bool closed;
        bool refunded;
    }

    MerchantRegistry public immutable registry;
    address public regulator;

    uint256 public nextPackageId = 1;
    mapping(uint256 => Package) private _packages;

    /// @notice Convenience pointer: consumer => id of the package they bought last.
    mapping(address => uint256) public activePackageOf;

    // ---------------------------------------------------------------------
    // Events (the Streamlit activity log is built from these)
    // ---------------------------------------------------------------------
    event PackagePurchased(
        uint256 indexed packageId,
        address indexed consumer,
        address indexed merchant,
        uint256 amount
    );
    event SessionCompleted(
        uint256 indexed packageId,
        uint256 sessionNumber,
        uint256 releasedAmount,
        uint256 protectedBalance
    );
    event FundsWithdrawn(
        uint256 indexed packageId,
        address indexed merchant,
        uint256 amount,
        uint256 remainingAvailable
    );
    event MerchantMarkedClosed(uint256 indexed packageId, address indexed merchant);
    event RefundProcessed(
        uint256 indexed packageId,
        address indexed consumer,
        uint256 amount
    );

    modifier packageExists(uint256 packageId) {
        require(packageId != 0 && packageId < nextPackageId, "Package not found.");
        _;
    }

    constructor(address registry_) {
        require(registry_ != address(0), "Registry address is required.");
        registry = MerchantRegistry(registry_);
        regulator = MerchantRegistry(registry_).regulator();
    }

    // ---------------------------------------------------------------------
    // Consumer actions
    // ---------------------------------------------------------------------

    /**
     * @notice Buy the 12-session package. The full price stays inside this contract.
     * @param merchant Licensed merchant that will deliver the service.
     */
    function buyPackage(address merchant) external payable returns (uint256 packageId) {
        require(registry.isLicensed(merchant), "Merchant is not licensed.");
        require(msg.value == PACKAGE_PRICE, "Incorrect payment amount.");

        packageId = nextPackageId++;

        Package storage p = _packages[packageId];
        p.consumer = msg.sender;
        p.merchant = merchant;
        p.totalPaid = msg.value;
        p.sessionsUsed = 0;
        p.releasedAmount = 0;
        p.withdrawnAmount = 0;
        p.closed = false;
        p.refunded = false;

        activePackageOf[msg.sender] = packageId;

        emit PackagePurchased(packageId, msg.sender, merchant, msg.value);
    }

    /**
     * @notice Complete one service session. Releases HK$500 to the merchant's
     *         withdrawable balance (bookkeeping only, no transfer here).
     */
    function useSession(uint256 packageId) external packageExists(packageId) {
        Package storage p = _packages[packageId];

        require(msg.sender == p.consumer, "Only the consumer can use a session.");
        require(!p.refunded, "Package has already been refunded.");
        require(!p.closed, "Merchant is closed. No further sessions allowed.");
        require(p.sessionsUsed < SESSIONS_PER_PACKAGE, "All sessions have been used.");

        p.sessionsUsed += 1;
        p.releasedAmount += PRICE_PER_SESSION;

        emit SessionCompleted(
            packageId,
            p.sessionsUsed,
            p.releasedAmount,
            p.totalPaid - p.releasedAmount
        );
    }

    // ---------------------------------------------------------------------
    // Merchant actions
    // ---------------------------------------------------------------------

    /**
     * @notice Withdraw already released funds.
     * @dev The explicit `amount` parameter is what makes the "excess withdrawal"
     *      failure path demonstrable: anything above the released amount reverts.
     */
    function withdrawReleasedAmount(uint256 packageId, uint256 amount)
        external
        packageExists(packageId)
    {
        Package storage p = _packages[packageId];

        require(msg.sender == p.merchant, "Only the merchant can withdraw.");
        require(amount > 0, "Withdrawal amount must be greater than zero.");

        uint256 available = p.releasedAmount - p.withdrawnAmount;
        require(amount <= available, "Reserve funds are locked.");

        p.withdrawnAmount += amount;

        (bool ok, ) = payable(p.merchant).call{value: amount}("");
        require(ok, "Transfer to merchant failed.");

        emit FundsWithdrawn(packageId, p.merchant, amount, available - amount);
    }

    // ---------------------------------------------------------------------
    // Regulator actions
    // ---------------------------------------------------------------------

    /**
     * @notice Mark the merchant as closed for this package, opening the refund path.
     */
    function markClosed(uint256 packageId) external packageExists(packageId) {
        Package storage p = _packages[packageId];

        require(msg.sender == regulator, "Only the regulator can close the merchant.");
        require(!p.closed, "Merchant is already marked as closed.");

        p.closed = true;

        emit MerchantMarkedClosed(packageId, p.merchant);
    }

    /**
     * @notice Refund every still-escrowed HKD to the consumer.
     * @dev Can only run once; the second attempt reverts.
     */
    function refundUnusedBalance(uint256 packageId) external packageExists(packageId) {
        Package storage p = _packages[packageId];

        require(msg.sender == regulator, "Only the regulator can process a refund.");
        require(p.closed, "Merchant is not closed yet.");
        require(!p.refunded, "Refund has already been processed.");

        uint256 refundAmount = p.totalPaid - p.releasedAmount;
        require(refundAmount > 0, "Nothing left to refund.");
        require(address(this).balance >= refundAmount, "Insufficient vault balance.");

        p.refunded = true;

        (bool ok, ) = payable(p.consumer).call{value: refundAmount}("");
        require(ok, "Refund transfer failed.");

        emit RefundProcessed(packageId, p.consumer, refundAmount);
    }

    // ---------------------------------------------------------------------
    // Views (used by the CLI, the tests and the Streamlit dashboard)
    // ---------------------------------------------------------------------

    function getPackage(uint256 packageId)
        external
        view
        packageExists(packageId)
        returns (Package memory)
    {
        return _packages[packageId];
    }

    function packageCount() external view returns (uint256) {
        return nextPackageId - 1;
    }

    /// @notice Funds the merchant is allowed to withdraw right now.
    function availableToWithdraw(uint256 packageId)
        external
        view
        packageExists(packageId)
        returns (uint256)
    {
        Package storage p = _packages[packageId];
        return p.releasedAmount - p.withdrawnAmount;
    }

    /// @notice Consumer money still protected inside the vault.
    function protectedBalance(uint256 packageId)
        public
        view
        packageExists(packageId)
        returns (uint256)
    {
        Package storage p = _packages[packageId];
        if (p.refunded) return 0;
        return p.totalPaid - p.releasedAmount;
    }

    /// @notice Amount that would be refunded if the merchant were closed now.
    function previewRefund(uint256 packageId)
        external
        view
        packageExists(packageId)
        returns (uint256)
    {
        Package storage p = _packages[packageId];
        return p.totalPaid - p.releasedAmount;
    }
}
