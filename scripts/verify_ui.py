"""
End-to-end verification of the Streamlit demo.

This drives the real app script (frontend/app.py) through Streamlit's AppTest
harness, clicking the same buttons a presenter would click, against the live
local Hardhat node. Every step asserts the on-screen text.

Prerequisites:
    npx hardhat node                                   # terminal 1
    npx hardhat run scripts/deploy.js --network localhost   # terminal 2
    python scripts/verify_ui.py                        # terminal 3 (fresh chain)

Run this on a freshly deployed chain: it expects no merchant registered yet.
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

    # ---------------------------------------------------------------- step 1
    at.radio[0].set_value("Regulator").run()
    at = click(at, "Register Merchant")
    check("step 1 merchant registered", any("Merchant registered" in s.value for s in at.success),
          str([s.value for s in at.success]))

    # ---------------------------------------------------------------- step 2
    at.radio[0].set_value("Consumer").run()
    at = click(at, "Buy Package")
    check("step 2 package purchased", any("Package purchased" in s.value for s in at.success),
          str([s.value for s in at.success]))
    body = texts(at)
    check("step 2 shows HK$6,000 protected", "HK$6,000" in body)

    # ---------------------------------------------------------------- step 3
    for i in range(3):
        at = click(at, "Use One Session")
        check(f"step 3 session {i + 1} completed",
              any("Session completed successfully." in s.value for s in at.success),
              str([s.value for s in at.success]))
        check(f"step 3 session {i + 1} names the released amount",
              any("has been released to the merchant." in s.value for s in at.success),
              str([s.value for s in at.success]))
    body = texts(at)
    check("step 3 shows 3 / 12 sessions", "3 / 12" in body, body[:300])
    check("step 3 shows HK$1,500 released", "HK$1,500" in body)
    check("step 3 shows HK$4,500 protected", "HK$4,500" in body)

    # ---------------------------------------------------------------- step 4
    at.radio[0].set_value("Merchant").run()
    at = click(at, "Test Excess Withdrawal")
    err = " ".join(e.value for e in at.error)
    check("step 4 excess withdrawal rejected", "Reserve funds are locked." in err, err)
    check("step 4 explains why", "cannot withdraw unused consumer funds" in err, err)
    check("step 4 says Transaction Reverted", "Transaction Reverted" in err, err)

    # ---------------------------------------------------------------- step 5
    at = click(at, "Withdraw Available Funds")
    check("step 5 withdrawal succeeded",
          any("Withdrawal successful" in s.value for s in at.success),
          str([s.value for s in at.success]))

    # ---------------------------------------------------------------- step 6
    at.radio[0].set_value("Regulator").run()
    at = click(at, "Mark Merchant as Closed")
    check("step 6 merchant closed",
          any("marked as closed" in s.value for s in at.success),
          str([s.value for s in at.success]))

    # ---------------------------------------------------------------- step 7
    at = click(at, "Process Consumer Refund")
    ok = " ".join(s.value for s in at.success)
    check("step 7 refund succeeded", "refund processed successfully" in ok, ok)
    check("step 7 refund amount HK$4,500", "HK$4,500" in ok, ok)

    # ---------------------------------------------------------------- step 8
    at = click(at, "Process Consumer Refund")
    err = " ".join(e.value for e in at.error)
    check("step 8 double refund rejected", "Refund has already been processed." in err, err)

    # ---------------------------------------------------------------- log
    at.radio[0].set_value("Activity Log").run()
    log = " ".join(m.value for m in at.markdown)
    for expected in ["Merchant registered", "Package purchased", "Session #1 completed",
                     "Merchant withdrawal completed", "Merchant marked as closed",
                     "refunded to consumer"]:
        check(f"activity log contains '{expected}'", expected in log)

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
