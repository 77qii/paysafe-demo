"""
In-process Ethereum chain for the hosted build.

Locally the demo talks to a Hardhat node over JSON-RPC. A hosted environment
gives us a single HTTP port and no second process, so this module boots an
eth-tester (py-evm) chain inside the app process and deploys the same compiled
contracts, from contracts.json, that Hardhat produced. Everything downstream
keeps talking to a plain Web3 object and cannot tell the difference.

Activated only when PAYSAFE_HOSTED=1. Local runs never import this module.

The chain is built once per server process and shared by every browser session,
so the audience and the presenter look at the same live state. That is the point
of a demo link. Because the state is shared, a finished run stays finished until
someone rebuilds the chain: `reset()` throws the current chain away and deploys
a new pair of contracts, which is what the "Reset demo chain" button in the app
calls. The default PyEVM accounts are derived from a fixed test mnemonic, so
accounts[0..2] keep the same addresses after a reset and the roles stay stable.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from eth_tester import EthereumTester, PyEVMBackend
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

HERE = Path(__file__).resolve().parent
CONTRACTS_FILE = HERE / "contracts.json"

BLOCK_GAS_LIMIT = 30_000_000
DEPLOY_GAS = 8_000_000

_lock = threading.RLock()
_chain: dict = {"w3": None, "deployment": None}


def _deploy(w3, spec, name, args, sender):
    factory = w3.eth.contract(abi=spec[name]["abi"], bytecode=spec[name]["bytecode"])
    tx_hash = factory.constructor(*args).transact({"from": sender, "gas": DEPLOY_GAS})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
    return receipt["contractAddress"], receipt["blockNumber"]


def _build():
    """Boot the chain and deploy both contracts. Returns (w3, deployment)."""
    backend = PyEVMBackend(genesis_parameters={"gas_limit": BLOCK_GAS_LIMIT})
    w3 = Web3(EthereumTesterProvider(EthereumTester(backend)))

    accounts = w3.eth.accounts
    if len(accounts) < 3:
        raise RuntimeError("The in-process chain must expose at least 3 accounts.")
    regulator, merchant, consumer = accounts[0], accounts[1], accounts[2]

    spec = json.loads(CONTRACTS_FILE.read_text(encoding="utf-8"))

    registry_address, registry_block = _deploy(
        w3, spec, "MerchantRegistry", [regulator], regulator
    )
    vault_address, vault_block = _deploy(
        w3, spec, "PrepayVault", [registry_address], regulator
    )

    deployment = {
        "network": "in-process",
        "chainId": w3.eth.chain_id,
        "deployedAt": datetime.now(timezone.utc).isoformat(),
        "accounts": {
            "regulator": regulator,
            "merchant": merchant,
            "consumer": consumer,
        },
        "contracts": {
            "MerchantRegistry": {
                "address": registry_address,
                "blockNumber": registry_block,
                "abi": spec["MerchantRegistry"]["abi"],
            },
            "PrepayVault": {
                "address": vault_address,
                "blockNumber": vault_block,
                "abi": spec["PrepayVault"]["abi"],
            },
        },
    }
    return w3, deployment


def _ensure():
    with _lock:
        if _chain["w3"] is None:
            _chain["w3"], _chain["deployment"] = _build()
        return _chain["w3"], _chain["deployment"]


def reset() -> dict:
    """Discard the current chain and return a freshly deployed, empty one.

    Every session that is open right now keeps rendering from its own copy of
    the old Web3 object until it reruns; the caller is responsible for clearing
    Streamlit's caches and rerunning the page.
    """
    with _lock:
        w3, deployment = _build()
        _chain["w3"], _chain["deployment"] = w3, deployment
        return deployment


def shared_web3() -> Web3:
    return _ensure()[0]


def shared_deployment() -> dict:
    return _ensure()[1]
