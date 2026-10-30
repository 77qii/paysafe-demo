// scripts/demo_cli.js
// Runs the complete PaySafe business flow on an in-process Hardhat network,
// with NO user interface. This is the "Phase 2" verification script.
//
// Usage:  npx hardhat run scripts/demo_cli.js

const hre = require("hardhat");

const HKD = 10n ** 15n; // 1 HKD = 1e15 wei (demo unit)
const hkd = (wei) => "HK$" + (wei / HKD).toLocaleString("en-US");
const line = (c = "-") => console.log(c.repeat(72));

function revertReason(error) {
  const msg = error.shortMessage || error.message || String(error);
  const reason = msg.match(/reason string '([^']+)'/);
  if (reason) return reason[1];
  const m = msg.match(/reverted[^:]*:\s*(.+)$/);
  return (m ? m[1] : msg).trim();
}

async function main() {
  const [regulator, merchant, consumer, outsider] = await hre.ethers.getSigners();

  console.log("");
  console.log("PaySafe - Blockchain-Based Prepaid Consumer Protection");
  console.log("Command-line verification of the full business flow");
  line("=");

  // ---------------------------------------------------------------- setup
  const Registry = await hre.ethers.getContractFactory("MerchantRegistry");
  const registry = await Registry.deploy(regulator.address);
  await registry.waitForDeployment();

  const Vault = await hre.ethers.getContractFactory("PrepayVault");
  const vault = await Vault.deploy(await registry.getAddress());
  await vault.waitForDeployment();

  console.log("MerchantRegistry:", await registry.getAddress());
  console.log("PrepayVault     :", await vault.getAddress());
  line();

  // ------------------------------------------- Failure Case 2: unlicensed
  console.log("STEP 0  Failure Case 2 - unlicensed merchant");
  try {
    await vault.connect(consumer).buyPackage(merchant.address, {
      value: await vault.PACKAGE_PRICE(),
    });
    console.log("  UNEXPECTED: purchase went through.");
  } catch (e) {
    console.log("  Transaction Failed");
    console.log("  " + revertReason(e));
  }
  line();

  // ------------------------------------------------- STEP 1 registration
  console.log("STEP 1  Regulator registers the merchant");
  await (await registry.connect(regulator).registerMerchant(merchant.address)).wait();
  console.log("  Merchant License:", (await registry.isLicensed(merchant.address)) ? "Licensed" : "Not Licensed");
  line();

  // ------------------------------------------------- STEP 2 buy package
  console.log("STEP 2  Consumer buys the 12-session package");
  const packagePrice = await vault.PACKAGE_PRICE();
  await (await vault.connect(consumer).buyPackage(merchant.address, { value: packagePrice })).wait();

  const packageId = await vault.activePackageOf(consumer.address);
  let p = await vault.getPackage(packageId);
  console.log("  Total Paid         :", hkd(p.totalPaid));
  console.log("  Sessions Used      :", p.sessionsUsed.toString(), "/ 12");
  console.log("  Released to Merchant:", hkd(p.releasedAmount));
  console.log("  Protected Balance  :", hkd(await vault.protectedBalance(packageId)));
  line();

  // ------------------------------------------------- STEP 3 three sessions
  console.log("STEP 3  Consumer completes three sessions");
  for (let i = 1; i <= 3; i++) {
    await (await vault.connect(consumer).useSession(packageId)).wait();
    p = await vault.getPackage(packageId);
    console.log(
      `  Session #${i} completed -> used ${p.sessionsUsed}/12, released ${hkd(p.releasedAmount)}, protected ${hkd(
        await vault.protectedBalance(packageId)
      )}`
    );
  }
  line();

  // ------------------------------------- STEP 4 Failure Case 1: excess withdrawal
  console.log("STEP 4  Failure Case 1 - merchant tries to withdraw more than released");
  const available = await vault.availableToWithdraw(packageId);
  try {
    await (
      await vault.connect(merchant).withdrawReleasedAmount(packageId, available + 500n * HKD)
    ).wait();
    console.log("  UNEXPECTED: excess withdrawal succeeded.");
  } catch (e) {
    console.log("  Transaction Failed");
    console.log("  " + revertReason(e));
    console.log("  The merchant cannot withdraw unused consumer funds.");
  }
  line();

  // ------------------------------------------------- STEP 5 normal withdrawal
  console.log("STEP 5  Merchant withdraws the released amount");
  await (await vault.connect(merchant).withdrawReleasedAmount(packageId, available)).wait();
  p = await vault.getPackage(packageId);
  console.log("  Withdrawal successful.");
  console.log("  Amount            :", hkd(p.withdrawnAmount));
  console.log("  Available to Withdraw:", hkd(await vault.availableToWithdraw(packageId)));
  console.log("  Protected Balance :", hkd(await vault.protectedBalance(packageId)));
  line();

  // ------------------------------------------------- STEP 6 merchant closed
  console.log("STEP 6  Regulator marks the merchant as closed");
  await (await vault.connect(regulator).markClosed(packageId)).wait();
  p = await vault.getPackage(packageId);
  console.log("  Merchant Status:", p.closed ? "Closed" : "Active");
  line();

  // ------------------------------------------------- STEP 7 refund
  console.log("STEP 7  Regulator processes the consumer refund");
  const refundPreview = await vault.previewRefund(packageId);
  await (await vault.connect(regulator).refundUnusedBalance(packageId)).wait();
  p = await vault.getPackage(packageId);
  console.log("  Refund successful.");
  console.log("  Refund Amount:", hkd(refundPreview));
  console.log("  Refunded flag:", p.refunded);
  line();

  // ---------------------------------------- STEP 8 Failure Case 3: double refund
  console.log("STEP 8  Failure Case 3 - second refund attempt");
  try {
    await (await vault.connect(regulator).refundUnusedBalance(packageId)).wait();
    console.log("  UNEXPECTED: second refund succeeded.");
  } catch (e) {
    console.log("  Transaction Failed");
    console.log("  " + revertReason(e));
  }
  line("=");
  console.log("All steps executed. Vault balance left:", hkd(await hre.ethers.provider.getBalance(await vault.getAddress())));
  console.log("");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
