// scripts/export_contracts.js
// Regenerates frontend/contracts.json from the compiled Hardhat artifacts.
//
// The hosted build (frontend/chain_host.py) deploys the contracts from this file
// instead of talking to a Hardhat node, so it goes stale silently whenever a
// contract changes. Run this after `npx hardhat compile`.
//
// Usage:  npx hardhat run scripts/export_contracts.js

const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

const NAMES = ["MerchantRegistry", "PrepayVault"];

async function main() {
  const spec = {};

  for (const name of NAMES) {
    const artifact = await hre.artifacts.readArtifact(name);
    if (!artifact.bytecode || artifact.bytecode === "0x") {
      throw new Error(`${name} has no bytecode — did the compile succeed?`);
    }
    spec[name] = { abi: artifact.abi, bytecode: artifact.bytecode };
  }

  const outFile = path.join(__dirname, "..", "frontend", "contracts.json");
  fs.writeFileSync(outFile, JSON.stringify(spec, null, 2) + "\n");

  for (const name of NAMES) {
    console.log(
      `${name.padEnd(18)} abi ${String(spec[name].abi.length).padStart(3)} entries, ` +
        `bytecode ${spec[name].bytecode.length} chars`
    );
  }
  console.log("written to:", outFile);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
