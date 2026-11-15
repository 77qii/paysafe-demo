"""
End-to-end verification of the Streamlit demo.

This drives the real app script (frontend/app.py) through Streamlit's AppTest
harness, clicking the same buttons a presenter would click, against whichever
backend the app picks (local Hardhat node, or the in-process chain when
PAYSAFE_HOSTED=1).

Prerequisites:
    npx hardhat node                          # terminal 1, only for the local run
    python scripts/verify_ui.py               # terminal 2

The first thing the harness does is press "Reset demo chain", so it no longer
matters what state the chain was left in: the run starts from zero every time.
"""

import os
import re
import sys
from pathlib import Path

# The UI asks for a second click before destructive actions. This harness
# clicks once per step, so it opts out. The demo keeps the protection on.
os.environ["PAYSAFE_NO_CONFIRM"] = "1"

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "frontend" / "app.py")

passed = []
failed = []


def check(name, condition, detail=""):
    if condition:
        passed.append(name)
        print(f"  PASS  {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL  {name}  {detail}")


def click(at, label):
    """Click the button with the given label in the main area and rerun."""
    for b in at.button:
        if b.label == label:
            if b.disabled:
                raise AssertionError(f"Button '{label}' is disabled")
            b.click()
            return at.run()
    raise AssertionError(f"Button '{label}' not found. Have: {[b.label for b in at.button]}")


def texts(at):
    parts = [m.value for m in at.markdown]
    parts += [s.value for s in at.success]
    parts += [f"{m.label} {m.value}" for m in at.metric]
    return " ".join(parts)


def captions(at):
    return " ".join(c.value for c in at.caption)


def main():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()

    print("\nPaySafe - Streamlit UI verification")
    print("=" * 70)

    check("app renders without exception", not at.exception, str(at.exception))
    if at.exception:
        for e in at.exception:
            print("   ", e.value)
        sys.exit(1)

    # ---------------------------------------------------------------- reset
    # Self-contained run: whatever the previous demo left behind is discarded.
    at = click(at, "Reset demo chain")
    check("reset deploys a fresh chain",
          any("Demo reset." in s.value for s in at.success),
          str([s.value for s in at.success]))

    at.radio[0].set_value("Home").run()
    home = " ".join(i.value for i in at.info) + texts(at)
    check("reset returns Home to Step 1", "Test Unlicensed Purchase" in home, home[:300])

    # ---------------------------------------------------------------- step 1
    at.radio[0].set_value("Consumer").run()
    at = click(at, "Test Unlicensed Purchase")
    err = " ".join(e.value for e in at.error)
    check("step 1 unlicensed purchase rejected", "Merchant is not licensed." in err, err)
    check("step 1 says Transaction Reverted", "Transaction Reverted" in err, err)

    # ---------------------------------------------------------------- step 2
    at.radio[0].set_value("Regulator").run()
    at = click(at, "Register Merchant")
    check("step 2 merchant registered", any("Merchant registered" in s.value for s in at.success),
          str([s.value for s in at.success]))

    # ---------------------------------------------------------------- step 3
    at.radio[0].set_value("Consumer").run()
    at = click(at, "Buy Package")
    check("step 3 package purchased", any("Package purchased" in s.value for s in at.success),
          str([s.value for s in at.success]))
    body = texts(at)
    check("step 3 shows HK$6,000 protected", "HK$6,000" in body)

    # ---------------------------------------------------------------- step 4
    for i in range(3):
        at = click(at, "Use One Session")
        check(f"step 4 session {i + 1} completed",
              any("Session completed successfully." in s.value for s in at.success),
              str([s.value for s in at.success]))
        check(f"step 4 session {i + 1} names the released amount",
              any("has been released to the merchant." in s.value for s in at.success),
              str([s.value for s in at.success]))
    body = texts(at)
    check("step 4 shows 3 / 12 sessions", "3 / 12" in body, body[:300])
    check("step 4 shows HK$1,500 released", "HK$1,500" in body)
    check("step 4 shows HK$4,500 protected", "HK$4,500" in body)

    # ---------------------------------------------------------------- step 5
    at.radio[0].set_value("Merchant").run()
    at = click(at, "Test Excess Withdrawal")
    err = " ".join(e.value for e in at.error)
    check("step 5 excess withdrawal rejected", "Reserve funds are locked." in err, err)
    check("step 5 explains why", "cannot withdraw unused consumer funds" in err, err)
    check("step 5 says Transaction Reverted", "Transaction Reverted" in err, err)

    # ---------------------------------------------------------------- step 6
    at = click(at, "Withdraw Available Funds")
    check("step 6 withdrawal succeeded",
          any("Withdrawal successful" in s.value for s in at.success),
          str([s.value for s in at.success]))
    # The disabled caption must agree with "Withdrawn Amount HK$1,500" above it.
    caps = captions(at)
    check("step 6 button explains the money was taken out",
          "has already been withdrawn" in caps, caps[:400])
    check("step 6 does not claim nothing was released",
          "Nothing has been released yet" not in caps, caps[:400])

    # ---------------------------------------------------------------- step 7
    at.radio[0].set_value("Regulator").run()
    at = click(at, "Mark Merchant as Closed")
    check("step 7 merchant closed",
          any("marked as closed" in s.value for s in at.success),
          str([s.value for s in at.success]))

    # ---------------------------------------------------------------- step 8
    at = click(at, "Process Consumer Refund")
    ok = " ".join(s.value for s in at.success)
    check("step 8 refund succeeded", "refund processed successfully" in ok, ok)
    check("step 8 refund amount HK$4,500", "HK$4,500" in ok, ok)
    body = texts(at)
    check("step 8 bar shows the refunded slice", "Refunded HK$4,500" in body, body[:400])
    check("step 8 caption accounts for the whole HK$6,000",
          "went back to the consumer" in body and "vault is empty" in body, body[:600])

    # ---------------------------------------------------------------- step 9
    at = click(at, "Process Consumer Refund")
    err = " ".join(e.value for e in at.error)
    check("step 9 double refund rejected", "Refund has already been processed." in err, err)

    # ---------------------------------------------------------------- log
    at.radio[0].set_value("Activity Log").run()
    log = " ".join(m.value for m in at.markdown)
    for expected in ["Merchant registered", "Package purchased", "Session #1 completed",
                     "Merchant withdrawal completed", "Merchant marked as closed",
                     "refunded to consumer"]:
        check(f"activity log contains '{expected}'", expected in log)

    # Roles and addresses: a regulator event must not wear the counterparty's
    # wallet, and every row must expose a transaction hash.
    check("log names the regulator's counterparty", "Regulator → Merchant 0x" in log, log[:400])
    check("log refund row points at the consumer", "Regulator → Consumer 0x" in log)
    check("log never labels a bare address as Regulator", "Regulator 0x" not in log, log[:400])
    check("log rows carry a transaction hash", log.count("Tx 0x") >= 8, str(log.count("Tx 0x")))

    # The demo ends on this page, so the newest event has to be at the top.
    log_rows = [m.value for m in at.markdown if 'class="ps-log"' in m.value]
    blocks = [int(b) for b in re.findall(r"Block #(\d+)", " ".join(log_rows))]
    check("activity log is newest first", blocks == sorted(blocks, reverse=True), str(blocks))
    check("activity log top row is the latest event",
          "refunded to consumer" in log_rows[0], log_rows[0][:200])

    print("=" * 70)
    print(f"{len(passed)} passed, {len(failed)} failed")
    if failed:
        for name, detail in failed:
            print(" FAILED:", name, "|", detail[:300])
        sys.exit(1)


if __name__ == "__main__":
    main()
