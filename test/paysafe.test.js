const { expect } = require("chai");
const { ethers } = require("hardhat");
const { loadFixture } = require("@nomicfoundation/hardhat-network-helpers");

const HKD = 10n ** 15n; // 1 HKD = 1e15 wei (demo unit)
const PACKAGE_PRICE = 6000n * HKD;
const PRICE_PER_SESSION = 500n * HKD;

describe("PaySafe", function () {
  async function deployFixture() {
    const [regulator, merchant, consumer, outsider] = await ethers.getSigners();

    const Registry = await ethers.getContractFactory("MerchantRegistry");
    const registry = await Registry.deploy(regulator.address);
    await registry.waitForDeployment();

    const Vault = await ethers.getContractFactory("PrepayVault");
    const vault = await Vault.deploy(await registry.getAddress());
    await vault.waitForDeployment();

    return { registry, vault, regulator, merchant, consumer, outsider };
  }

  async function purchasedFixture() {
    const base = await deployFixture();
    const { registry, vault, regulator, merchant, consumer } = base;

    await registry.connect(regulator).registerMerchant(merchant.address);
    await vault.connect(consumer).buyPackage(merchant.address, { value: PACKAGE_PRICE });

    const packageId = await vault.activePackageOf(consumer.address);
    return { ...base, packageId };
  }

  describe("MerchantRegistry", function () {
    it("lets the regulator license a merchant", async function () {
      const { registry, regulator, merchant } = await loadFixture(deployFixture);

      expect(await registry.isLicensed(merchant.address)).to.equal(false);
      await expect(registry.connect(regulator).registerMerchant(merchant.address))
        .to.emit(registry, "MerchantRegistered")
        .withArgs(merchant.address, regulator.address);

      expect(await registry.isLicensed(merchant.address)).to.equal(true);
      expect(await registry.merchantCount()).to.equal(1);
    });

    it("rejects registration from a non-regulator account", async function () {
      const { registry, outsider, merchant } = await loadFixture(deployFixture);

      await expect(
        registry.connect(outsider).registerMerchant(merchant.address)
      ).to.be.revertedWith("Only the regulator can perform this action.");
    });

    it("lets the regulator revoke a license", async function () {
      const { registry, regulator, merchant } = await loadFixture(deployFixture);

      await registry.connect(regulator).registerMerchant(merchant.address);
      await registry.connect(regulator).revokeMerchant(merchant.address);

      expect(await registry.isLicensed(merchant.address)).to.equal(false);
    });
  });

  describe("Package purchase", function () {
    it("stores correct state after buying a package", async function () {
      const { vault, packageId } = await loadFixture(purchasedFixture);

      const p = await vault.getPackage(packageId);
      expect(p.totalPaid).to.equal(PACKAGE_PRICE);
      expect(p.sessionsUsed).to.equal(0);
      expect(p.releasedAmount).to.equal(0);
      expect(p.withdrawnAmount).to.equal(0);
      expect(p.closed).to.equal(false);
      expect(p.refunded).to.equal(false);

      expect(await vault.protectedBalance(packageId)).to.equal(PACKAGE_PRICE);
      expect(await vault.availableToWithdraw(packageId)).to.equal(0);
      expect(await ethers.provider.getBalance(await vault.getAddress())).to.equal(PACKAGE_PRICE);
    });

    it("rejects a package purchase from an unlicensed merchant (Failure Case 2)", async function () {
      const { vault, consumer, outsider } = await loadFixture(deployFixture);

      await expect(
        vault.connect(consumer).buyPackage(outsider.address, { value: PACKAGE_PRICE })
      ).to.be.revertedWith("Merchant is not licensed.");
    });

    it("rejects an incorrect payment amount", async function () {
      const { registry, vault, regulator, merchant, consumer } = await loadFixture(deployFixture);

      await registry.connect(regulator).registerMerchant(merchant.address);

      await expect(
        vault.connect(consumer).buyPackage(merchant.address, { value: PRICE_PER_SESSION })
      ).to.be.revertedWith("Incorrect payment amount.");
    });
  });

  describe("Session usage", function () {
    it("releases HK$500 per session", async function () {
      const { vault, consumer, packageId } = await loadFixture(purchasedFixture);

      await expect(vault.connect(consumer).useSession(packageId))
        .to.emit(vault, "SessionCompleted")
        .withArgs(packageId, 1, PRICE_PER_SESSION, PACKAGE_PRICE - PRICE_PER_SESSION);

      const p = await vault.getPackage(packageId);
      expect(p.sessionsUsed).to.equal(1);
      expect(p.releasedAmount).to.equal(PRICE_PER_SESSION);
    });

    it("releases exactly HK$1,500 after three sessions", async function () {
      const { vault, consumer, packageId } = await loadFixture(purchasedFixture);

      for (let i = 0; i < 3; i++) {
        await vault.connect(consumer).useSession(packageId);
      }

      const p = await vault.getPackage(packageId);
      expect(p.sessionsUsed).to.equal(3);
      expect(p.releasedAmount).to.equal(1500n * HKD);
      expect(await vault.protectedBalance(packageId)).to.equal(4500n * HKD);
      expect(await vault.availableToWithdraw(packageId)).to.equal(1500n * HKD);
    });

    it("does not move funds out of the vault when a session is used", async function () {
      const { vault, consumer, packageId } = await loadFixture(purchasedFixture);

      await vault.connect(consumer).useSession(packageId);

      expect(await ethers.provider.getBalance(await vault.getAddress())).to.equal(PACKAGE_PRICE);
    });

    it("only lets the consumer record a session", async function () {
      const { vault, merchant, packageId } = await loadFixture(purchasedFixture);

      await expect(
        vault.connect(merchant).useSession(packageId)
      ).to.be.revertedWith("Only the consumer can use a session.");
    });

    it("cannot exceed 12 sessions", async function () {
      const { vault, consumer, packageId } = await loadFixture(purchasedFixture);

      for (let i = 0; i < 12; i++) {
        await vault.connect(consumer).useSession(packageId);
      }

      await expect(
        vault.connect(consumer).useSession(packageId)
      ).to.be.revertedWith("All sessions have been used.");

      const p = await vault.getPackage(packageId);
      expect(p.sessionsUsed).to.equal(12);
      expect(p.releasedAmount).to.equal(PACKAGE_PRICE);
    });
  });

  describe("Merchant withdrawal", function () {
    it("lets the merchant withdraw the released amount only", async function () {
      const { vault, consumer, merchant, packageId } = await loadFixture(purchasedFixture);

      for (let i = 0; i < 3; i++) {
        await vault.connect(consumer).useSession(packageId);
      }

      const before = await ethers.provider.getBalance(merchant.address);
      const tx = await vault.connect(merchant).withdrawReleasedAmount(packageId, 1500n * HKD);
      const receipt = await tx.wait();
      const after = await ethers.provider.getBalance(merchant.address);
      const gasCost = receipt.gasUsed * receipt.gasPrice;

      // The merchant receives exactly HK$1,500 and pays gas for the withdrawal itself.
      expect(after - before).to.equal(1500n * HKD - gasCost);

      const p = await vault.getPackage(packageId);
      expect(p.withdrawnAmount).to.equal(1500n * HKD);
      expect(await vault.availableToWithdraw(packageId)).to.equal(0);
      expect(await ethers.provider.getBalance(await vault.getAddress())).to.equal(4500n * HKD);
    });

    it("rejects an excess withdrawal (Failure Case 1)", async function () {
      const { vault, consumer, merchant, packageId } = await loadFixture(purchasedFixture);

      for (let i = 0; i < 3; i++) {
        await vault.connect(consumer).useSession(packageId);
      }

      await expect(
        vault.connect(merchant).withdrawReleasedAmount(packageId, 4500n * HKD)
      ).to.be.revertedWith("Reserve funds are locked.");

      await expect(
        vault.connect(merchant).withdrawReleasedAmount(packageId, 1501n * HKD)
      ).to.be.revertedWith("Reserve funds are locked.");
    });

    it("rejects a withdrawal from a non-merchant account", async function () {
      const { vault, consumer, outsider, packageId } = await loadFixture(purchasedFixture);

      await vault.connect(consumer).useSession(packageId);

      await expect(
        vault.connect(outsider).withdrawReleasedAmount(packageId, PRICE_PER_SESSION)
      ).to.be.revertedWith("Only the merchant can withdraw.");
    });
  });

  describe("Closure and refund", function () {
    async function closedFixture() {
      const base = await loadFixture(purchasedFixture);
      const { vault, consumer, regulator, packageId } = base;

      for (let i = 0; i < 3; i++) {
        await vault.connect(consumer).useSession(packageId);
      }
      await vault.connect(regulator).markClosed(packageId);

      return base;
    }

    it("lets only the regulator close the merchant", async function () {
      const { vault, consumer, packageId } = await loadFixture(purchasedFixture);

      await expect(
        vault.connect(consumer).markClosed(packageId)
      ).to.be.revertedWith("Only the regulator can close the merchant.");
    });

    it("marks the merchant as closed", async function () {
      const { vault, regulator, merchant, packageId } = await loadFixture(purchasedFixture);

      await expect(vault.connect(regulator).markClosed(packageId))
        .to.emit(vault, "MerchantMarkedClosed")
        .withArgs(packageId, merchant.address);

      const p = await vault.getPackage(packageId);
      expect(p.closed).to.equal(true);
    });

    it("blocks further sessions once closed", async function () {
      const { vault, consumer, packageId } = await loadFixture(closedFixture);

      await expect(
        vault.connect(consumer).useSession(packageId)
      ).to.be.revertedWith("Merchant is closed. No further sessions allowed.");
    });

    it("cannot refund before the merchant is closed", async function () {
      const { vault, regulator, packageId } = await loadFixture(purchasedFixture);

      await expect(
        vault.connect(regulator).refundUnusedBalance(packageId)
      ).to.be.revertedWith("Merchant is not closed yet.");
    });

    it("refunds exactly the unused balance", async function () {
      const { vault, regulator, consumer, packageId } = await loadFixture(closedFixture);

      expect(await vault.previewRefund(packageId)).to.equal(4500n * HKD);

      const before = await ethers.provider.getBalance(consumer.address);
      await expect(vault.connect(regulator).refundUnusedBalance(packageId))
        .to.emit(vault, "RefundProcessed")
        .withArgs(packageId, consumer.address, 4500n * HKD);
      const after = await ethers.provider.getBalance(consumer.address);

      expect(after - before).to.equal(4500n * HKD);
      expect(await vault.protectedBalance(packageId)).to.equal(0);

      const p = await vault.getPackage(packageId);
      expect(p.refunded).to.equal(true);
    });

    it("rejects a second refund (Failure Case 3)", async function () {
      const { vault, regulator, packageId } = await loadFixture(closedFixture);

      await vault.connect(regulator).refundUnusedBalance(packageId);

      await expect(
        vault.connect(regulator).refundUnusedBalance(packageId)
      ).to.be.revertedWith("Refund has already been processed.");
    });

    it("refunds nothing extra when the merchant already withdrew", async function () {
      const { vault, regulator, consumer, merchant, packageId } = await loadFixture(purchasedFixture);

      for (let i = 0; i < 3; i++) {
        await vault.connect(consumer).useSession(packageId);
      }
      await vault.connect(merchant).withdrawReleasedAmount(packageId, 1500n * HKD);
      await vault.connect(regulator).markClosed(packageId);

      const before = await ethers.provider.getBalance(consumer.address);
      await vault.connect(regulator).refundUnusedBalance(packageId);
      const after = await ethers.provider.getBalance(consumer.address);

      expect(after - before).to.equal(4500n * HKD);
      expect(await ethers.provider.getBalance(await vault.getAddress())).to.equal(0);
    });
  });
});
