require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: { enabled: true, runs: 200 },
    },
  },
  networks: {
    hardhat: {
      chainId: 31337,
      // Fixed accounts so the demo script and the Streamlit UI always agree on roles.
      accounts: {
        count: 10,
        accountsBalance: "10000000000000000000000", // 10,000 ETH each
      },
    },
    localhost: {
      // Override with PAYSAFE_RPC to target a node on a different port,
      // e.g. PAYSAFE_RPC=http://127.0.0.1:8546 npx hardhat run scripts/deploy.js --network localhost
      url: process.env.PAYSAFE_RPC || "http://127.0.0.1:8545",
      chainId: 31337,
    },
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
};
