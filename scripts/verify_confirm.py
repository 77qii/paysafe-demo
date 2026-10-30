"""
Verifies the two-click confirmation gate on irreversible actions.

scripts/verify_ui.py sets PAYSAFE_NO_CONFIRM=1 so it can drive the business flow in one
click per step. That means the confirmation behaviour itself is never exercised there.
This script runs with confirmation ENABLED and asserts:

    one click  -> warning "Click ... once more to confirm", state unchanged
    two clicks -> transaction sent, state changed

It uses Revoke Merchant License because it is the only confirm-gated action that can be
undone (register the merchant again afterwards), so the chain is left as it was found.

Prerequisites: node running + contracts deployed (same as verify_ui.py).
"""

import json
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest
from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "frontend" / "app.py")
DEPLOYMENT = ROOT / "deployments" / "local.json"

passed, failed = [], []


def check(name, ok, detail=""):
    (passed if ok else failed).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  {detail}"))


def click(at, label):
    for b in at.button:
        if b.label == label:
            if b.disabled:
                raise AssertionError(f"'{label}' is disabled")
            b.click()
            return at.run()
    raise AssertionError(f"'{label}' not found. Have: {[b.label for b in at.button]}")


def licensed(registry, merchant) -> bool:
    return registry.functions.isLicensed(merchant).call()


def main():
    d = json.loads(DEPLOYMENT.read_text())
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
    registry = w3.eth.contract(
        address=Web3.to_checksum_address(d["contracts"]["MerchantRegistry"]["address"]),
        abi=d["contracts"]["MerchantRegistry"]["abi"],
    )
    merchant = w3.eth.accounts[1]

    print("\nPaySafe - confirmation gate verification")
    print("=" * 70)

    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.radio[0].set_value("Regulator").run()

    if not licensed(registry, merchant):
        at = click(at, "Register Merchant")
        check("setup: merchant licensed", licensed(registry, merchant))

    # ---- one click must NOT change anything -----------------------------
    at = click(at, "Revoke Merchant License")
    warnings = " ".join(w.value for w in at.warning)
    check("first click asks for confirmation", "once more to confirm" in warnings, warnings[:160])
    check("first click leaves the licence untouched", licensed(registry, merchant) is True)

    # ---- second click goes through --------------------------------------
    at = click(at, "Revoke Merchant License")
    check("second click revokes the licence", licensed(registry, merchant) is False)

    # ---- restore --------------------------------------------------------
    at = click(at, "Register Merchant")
    check("merchant re-registered (chain restored)", licensed(registry, merchant) is True)

    print("=" * 70)
    print(f"{len(passed)} passed, {len(failed)} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
