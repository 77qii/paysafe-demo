// scripts/deploy.js
// Deploys MerchantRegistry + PrepayVault to the local Hardhat node and writes
// the addresses + ABIs to deployments/local.json so the Streamlit app can use them.
//
// Usage:  npx hardhat run scripts/deploy.js --network localhost

const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

async function main() {
  const signers = await hre.ethers.getSigners();

  // Fixed role assignment for the demo.
  const regulator = signers[0];
  const merchant = signers[1];
  const consumer = signers[2];

  console.log("Deploying PaySafe contracts to:", hre.network.name);
  console.log("  Regulator :", regulator.address);
  console.log("  Merchant  :", merchant.address);
  console.log("  Consumer  :", consumer.address);

  const Registry = await hre.ethers.getContractFactory("MerchantRegistry");
  const registry = await Registry.deploy(regulator.address);
  await registry.waitForDeployment();

  const Vault = await hre.ethers.getContractFactory("PrepayVault");
  const vault = await Vault.deploy(await registry.getAddress());
  await vault.waitForDeployment();

  const registryAddress = await registry.getAddress();
  const vaultAddress = await vault.getAddress();

  const registryArtifact = await hre.artifacts.readArtifact("MerchantRegistry");
  const vaultArtifact = await hre.artifacts.readArtifact("PrepayVault");

  const deployment = {
    network: hre.network.name,
    chainId: Number((await hre.ethers.provider.getNetwork()).chainId),
    deployedAt: new Date().toISOString(),
    accounts: {
      regulator: regulator.address,
      merchant: merchant.address,
      consumer: consumer.address,
    },
    contracts: {
      MerchantRegistry: { address: registryAddress, abi: registryArtifact.abi },
      PrepayVault: { address: vaultAddress, abi: vaultArtifact.abi },
    },
  };

  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, "local.json");
  fs.writeFileSync(outFile, JSON.stringify(deployment, null, 2));

  console.log("");
  console.log("MerchantRegistry deployed to:", registryAddress);
  console.log("PrepayVault      deployed to:", vaultAddress);
  console.log("Deployment written to        :", outFile);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
