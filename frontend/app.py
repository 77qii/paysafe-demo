"""
PaySafe - Blockchain-Based Prepaid Consumer Protection
Streamlit front end for the FTEC5520A final project demo.

Connects to a local Hardhat node over JSON-RPC and drives the two contracts:
  - MerchantRegistry : merchant licensing (regulator only)
  - PrepayVault      : escrow, session release, withdrawal, closure, refund

Design notes
------------
* Top navigation, no sidebar: this is a product demo, not an admin console.
* One number, one place. The vault composition is drawn as a single bar.
* Every disabled button states why it cannot be pressed, and the primary
  button always points at the next step of the demo story.
* Every transaction reports its hash and block number, because "on-chain"
  is the claim the demo is making.
* Destructive actions ask for a second click; tests opt out with
  PAYSAFE_NO_CONFIRM=1.

Environment
-----------
    PAYSAFE_RPC         JSON-RPC endpoint           (default http://127.0.0.1:8545)
    PAYSAFE_DEPLOYMENT  path to the deployment json (default ../deployments/local.json)
    PAYSAFE_NO_CONFIRM  set to 1 to skip the confirm step (used by scripts/verify_ui.py)
    PAYSAFE_HOSTED      set to 1 to run an in-process chain instead of a local node
                        (used by the hosted demo, see frontend/chain_host.py)

All user-visible text is English.
"""

import json
import os
import re
from pathlib import Path

import streamlit as st
from web3 import Web3

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
RPC_URL = os.environ.get("PAYSAFE_RPC", "http://127.0.0.1:8545")
_DEFAULT_DEPLOYMENT = Path(__file__).resolve().parent.parent / "deployments" / "local.json"
DEPLOYMENT_FILE = Path(os.environ.get("PAYSAFE_DEPLOYMENT", str(_DEFAULT_DEPLOYMENT))).resolve()
NO_CONFIRM = os.environ.get("PAYSAFE_NO_CONFIRM") == "1"

# A hosted build has one HTTP port and no second process, so it runs an
# in-process chain instead of dialling a local Hardhat node. Everything below
# goes through _new_web3() / load_deployment(), so the two backends are
# interchangeable and no page code knows which one it is talking to.
#
# Two ways to land in hosted mode, because not every host lets you set env vars
# (Streamlit Community Cloud only exposes secrets):
#   1. PAYSAFE_HOSTED=1                      - used by the container build
#   2. no Hardhat deployment file on disk    - a fresh clone / cloud checkout
# The deployment file is gitignored, so it only exists on a machine that has
# actually run deploy.js against a local node.
_CHAIN_HOST = Path(__file__).resolve().parent / "chain_host.py"
HOSTED = os.environ.get("PAYSAFE_HOSTED") == "1" or (
    not DEPLOYMENT_FILE.exists() and _CHAIN_HOST.exists()
)
if HOSTED:
    import chain_host

HKD = 10**15  # 1 HKD = 1e15 wei (demo unit, matches PrepayVault.HKD)

PAGES = ["Home", "Consumer", "Merchant", "Regulator", "Activity Log"]

st.set_page_config(
    page_title="PaySafe",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --------------------------------------------------------------------------
# Styling (light theme)
# --------------------------------------------------------------------------
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1180px; }

      /* ---------- top navigation: horizontal radio styled as tabs ---------- */
      div[data-testid="stRadioGroup"] {
          flex-direction: row !important; flex-wrap: wrap;
          gap: 2px !important; align-items: stretch;
          border-bottom: 1px solid #e3e9f2; margin-bottom: 16px;
      }
      div[data-testid="stRadioGroup"] > div { margin: 0 !important; }
      div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"] {
          margin: 0 !important; padding: 9px 15px 10px;
          border-radius: 9px 9px 0 0; border-bottom: 2px solid transparent;
          cursor: pointer; transition: background .12s ease;
      }
      div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:hover { background: #f4f7fd; }
      div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"][data-selected="true"] {
          background: #eef3ff; border-bottom-color: #1d4ed8;
      }
      div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"] p {
          font-size: 0.94rem; font-weight: 600; color: #3d5573;
      }
      div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"][data-selected="true"] p {
          color: #1d4ed8 !important; font-weight: 700;
      }
      /* hide the radio dot, keep the label text */
      div[data-testid="stRadioGroup"] label[data-testid="stRadioOption"] > div > div:first-child {
          display: none !important;
      }
      /* the collapsed "Navigation" widget label */
      div[data-testid="stRadio"] > label[data-testid="stWidgetLabel"] { display: none; }

      /* ---------- hero ---------- */
      .ps-hero { background: linear-gradient(135deg, #f2f7ff 0%, #eef4ff 55%, #f7f9fc 100%);
                 border: 1px solid #dbe6f7; border-radius: 16px; padding: 24px 30px; margin-bottom: 20px; }
      .ps-hero .brand { font-size: 1.05rem; font-weight: 800; letter-spacing: -0.01em;
                        color: #1d4ed8; }
      .ps-hero .eyebrow { font-size: 0.74rem; letter-spacing: 0.12em; text-transform: uppercase;
                          color: #1d4ed8; font-weight: 700; }
      .ps-hero h1 { margin: 8px 0 0; font-size: 2rem; line-height: 1.25; letter-spacing: -0.025em;
                    color: #10233f; font-weight: 800; max-width: 22em; }
      .ps-hero p.sub { margin: 10px 0 0; font-size: 1rem; color: #33507a; line-height: 1.6; max-width: 46em; }
      .ps-hero p.tag { margin: 10px 0 0; font-size: 0.84rem; color: #5b6f8a; }

      /* ---------- page header ---------- */
      .ps-head { display: flex; align-items: flex-end; justify-content: space-between;
                 gap: 16px; padding-bottom: 12px; margin-bottom: 18px; border-bottom: 1px solid #e3e9f2; }
      .ps-head-t { font-size: 1.45rem; font-weight: 700; color: #10233f; letter-spacing: -0.01em; }
      .ps-head-s { font-size: 0.9rem; color: #5b6f8a; margin-top: 2px; }
      .ps-head-r { display: flex; align-items: center; gap: 10px; padding-bottom: 4px; }
      .ps-role { display: inline-block; padding: 3px 11px; border-radius: 999px; font-size: 0.74rem;
                 font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
                 background: #eef3ff; color: #1d4ed8; }

      /* ---------- status bar ---------- */
      .ps-status { display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
                   font-size: 0.82rem; color: #5b6f8a; margin-bottom: 2px; }
      .ps-status .live { display: inline-flex; align-items: center; gap: 7px; }
      .ps-status .live i { width: 7px; height: 7px; border-radius: 50%; background: #16a34a;
                           box-shadow: 0 0 0 3px rgba(22,163,74,.15); }
      .ps-status b { color: #22314a; font-weight: 600; font-variant-numeric: tabular-nums; }

      /* ---------- headline status cards ---------- */
      .ps-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 6px 0 20px; }
      .ps-sc { position: relative; background: #fff; border: 1px solid #e4e9f2; border-radius: 14px;
               padding: 18px 20px 16px; box-shadow: 0 1px 2px rgba(16,35,63,.04); overflow: hidden; }
      .ps-sc::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--acc); }
      .ps-sc .k2 { font-size: 0.73rem; letter-spacing: 0.08em; text-transform: uppercase;
                   color: #5b6f8a; font-weight: 700; }
      .ps-sc .v2 { font-size: 1.95rem; font-weight: 800; letter-spacing: -0.02em; color: #10233f;
                   margin: 6px 0 2px; font-variant-numeric: tabular-nums; }
      .ps-sc .h2s { font-size: 0.82rem; color: #5b6f8a; }

      /* ---------- key-value card ---------- */
      .ps-card { background: #fff; border: 1px solid #e4e9f2; border-radius: 14px; padding: 16px 20px;
                 box-shadow: 0 1px 2px rgba(16,35,63,.04); }
      .ps-row { display: flex; justify-content: space-between; align-items: center; padding: 7px 0;
                font-size: 0.95rem; color: #22314a; border-bottom: 1px dashed #eef1f6; }
      .ps-row:last-child { border-bottom: none; }
      .ps-row .k { color: #5b6f8a; }
      .ps-row .v { font-weight: 600; font-variant-numeric: tabular-nums; }

      /* ---------- pills ---------- */
      .ps-pill { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
      .ps-ok { background: #e7f7ee; color: #14764a; }
      .ps-off { background: #fdecec; color: #b42318; }
      .ps-wait { background: #fff6e5; color: #8a5a00; }
      .ps-idle { background: #eef1f6; color: #4a5f7a; }

      /* ---------- money bar ---------- */
      .ps-bar { height: 16px; border-radius: 8px; overflow: hidden; background: #eef1f6; margin: 4px 0 8px; }
      .ps-legend { display: flex; flex-wrap: wrap; gap: 18px; font-size: 0.82rem; color: #5b6f8a; }
      .ps-legend i { display: inline-block; width: 9px; height: 9px; border-radius: 2px;
                     margin-right: 6px; transform: translateY(-1px); }
      .ps-legend i.p { background: #1d4ed8; }
      .ps-legend i.a { background: #16a34a; }
      .ps-legend i.w { background: #94a3b8; }
      .ps-cap { font-size: 0.82rem; color: #5b6f8a; line-height: 1.6; margin: 6px 0 2px; }

      /* ---------- regulator stepper ---------- */
      .ps-steps { display: flex; flex-direction: column; gap: 8px; margin: 4px 0 18px; }
      .ps-step { display: flex; align-items: center; gap: 12px; padding: 11px 16px;
                 border: 1px solid #e4e9f2; border-radius: 11px; background: #fff; }
      .ps-step .num { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                      font-size: 0.74rem; color: #8a99ad; }
      .ps-step .txt { flex: 1; font-size: 0.94rem; color: #22314a; font-weight: 600; }
      .ps-step .st { font-size: 0.76rem; font-weight: 700; padding: 2px 10px; border-radius: 999px; }
      .ps-step.done { background: #f6fbf8; border-color: #cfe9da; }
      .ps-step.done .st { background: #e7f7ee; color: #14764a; }
      .ps-step.now { background: #f5f8ff; border-color: #c9d8f5; }
      .ps-step.now .st { background: #eef3ff; color: #1d4ed8; }
      .ps-step.wait { background: #fbfcfd; }
      .ps-step.wait .st { background: #eef1f6; color: #5b6f8a; }

      /* ---------- activity log ---------- */
      .ps-log { border-bottom: 1px solid #eef1f6; padding: 11px 2px; }
      .ps-log:last-child { border-bottom: none; }
      .ps-log-top { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
      .ps-ev { display: inline-block; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
               font-size: 0.76rem; font-weight: 700; color: #1d4ed8; background: #eef3ff;
               padding: 2px 8px; border-radius: 6px; }
      .ps-blk { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                font-size: 0.76rem; color: #5b6f8a; }
      .ps-actor { font-size: 0.8rem; color: #5b6f8a; }
      .ps-amt { margin-left: auto; font-size: 0.88rem; font-weight: 700; color: #22314a;
                font-variant-numeric: tabular-nums; }
      .ps-log-bot { font-size: 0.9rem; color: #22314a; margin-top: 4px; }
      .ps-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; }
      .ps-dot.reg { background: #1d4ed8; }
      .ps-dot.con { background: #16a34a; }
      .ps-dot.mer { background: #8a5a00; }

      div[data-testid="stMarkdownContainer"] table { width: 100%; }
      @media (max-width: 780px) {
        .ps-cards { grid-template-columns: 1fr; }
        .ps-hero h1 { font-size: 1.55rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def hkd(wei) -> str:
    """Format a wei amount as HKD, keeping cents when they are not zero."""
    wei = int(wei)
    whole, frac = divmod(wei, HKD)
    if frac == 0:
        return "HK${:,}".format(whole)
    return "HK${:,}.{:02d}".format(whole, frac * 100 // HKD)


def short(addr: str) -> str:
    return f"{addr[:6]}…{addr[-4:]}" if addr else "—"


def cap(text):
    """Caption that survives Streamlit's LaTeX pass (a pair of $ starts math mode)."""
    st.markdown(f'<div class="ps-cap">{text.replace("$", "&#36;")}</div>', unsafe_allow_html=True)


def extract_reason(err: Exception) -> str:
    """Pull the Solidity revert string out of a web3 exception."""
    msg = str(err)
    m = re.search(r"reason string '([^']+)'", msg)
    if m:
        return m.group(1)
    m = re.search(r"execution reverted:?\s*(.*)", msg)
    if m and m.group(1).strip():
        return m.group(1).strip().strip("'\"")
    m = re.search(r"revert\s+(.+)$", msg, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return "The transaction was rejected by the smart contract."


def _new_web3() -> Web3:
    """A Web3 for whichever backend this build runs on."""
    if HOSTED:
        return chain_host.shared_web3()
    return Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 10}))


@st.cache_resource(show_spinner=False)
def get_web3() -> Web3:
    return _new_web3()


def load_deployment():
    if HOSTED:
        return chain_host.shared_deployment()
    if not DEPLOYMENT_FILE.exists():
        return None
    with open(DEPLOYMENT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def connect():
    """Return (w3, registry, vault, accounts) or raise a RuntimeError."""
    w3 = get_web3()
    if not w3.is_connected():
        raise RuntimeError(
            f"Cannot reach the local blockchain at {RPC_URL}. "
            "Start it with:  npx hardhat node"
        )
    deployment = load_deployment()
    if deployment is None:
        raise RuntimeError(
            "Deployment file not found. Run:  npx hardhat run scripts/deploy.js --network localhost"
        )
    registry = w3.eth.contract(
        address=Web3.to_checksum_address(deployment["contracts"]["MerchantRegistry"]["address"]),
        abi=deployment["contracts"]["MerchantRegistry"]["abi"],
    )
    vault = w3.eth.contract(
        address=Web3.to_checksum_address(deployment["contracts"]["PrepayVault"]["address"]),
        abi=deployment["contracts"]["PrepayVault"]["abi"],
    )
    accounts = w3.eth.accounts
    if len(accounts) < 3:
        raise RuntimeError("The local node must expose at least 3 unlocked accounts.")
    return w3, registry, vault, accounts


def send(w3, fn, sender, ok_message, extra_error_note=None, value=None):
    """Send a transaction, remember the outcome, and rerun the page."""
    tx_params = {"from": sender}
    if value is not None:
        tx_params["value"] = value
    try:
        tx_params["gas"] = int(fn.estimate_gas(tx_params) * 1.2)
    except Exception:  # noqa: BLE001 - a reverting call cannot be estimated; fall back
        tx_params["gas"] = 500_000
    try:
        with st.spinner("Waiting for the transaction to be mined…"):
            tx_hash = fn.transact(tx_params)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        if receipt.get("status", 1) != 1:
            # Not every backend raises on a reverted transaction: some mine it
            # and only report status 0. Replay it as a call to recover the
            # contract's own reason, so the audience never sees a false success.
            replay_error = None
            try:
                fn.call(tx_params)
            except Exception as call_err:  # noqa: BLE001
                replay_error = call_err
            raise replay_error or RuntimeError(
                "execution reverted: the transaction reverted on chain"
            )
        st.session_state["flash"] = (
            "success",
            f"{ok_message}\n\n"
            f"Tx `{Web3.to_hex(tx_hash)[:22]}…` · block #{receipt['blockNumber']} · "
            f"gas {receipt['gasUsed']:,}",
        )
    except Exception as err:  # noqa: BLE001 - surface the revert reason to the audience
        reason = extract_reason(err)
        text = f"**Transaction Failed**\n\n**{reason}**"
        if extra_error_note:
            text += f"\n\n{extra_error_note}"
        st.session_state["flash"] = ("error", text)
    st.rerun()


def show_flash():
    """Called once per render so a message can never leak onto another page."""
    flash = st.session_state.pop("flash", None)
    if not flash:
        return
    kind, text = flash
    if kind == "success":
        st.success(text, icon="✅")
    else:
        st.error(text, icon="⛔")


def read_state(w3, registry, vault, accounts):
    """Read everything the UI needs in one place."""
    regulator, merchant, consumer = accounts[0], accounts[1], accounts[2]

    licensed = registry.functions.isLicensed(merchant).call()
    package_id = vault.functions.activePackageOf(consumer).call()

    state = {
        "regulator": regulator,
        "merchant": merchant,
        "consumer": consumer,
        "licensed": licensed,
        "package_id": package_id,
        "has_package": package_id != 0,
        "block": w3.eth.block_number,
        # Business parameters come from the contract, never from a local copy.
        "sessions_per_package": vault.functions.SESSIONS_PER_PACKAGE().call(),
        "price_per_session": vault.functions.PRICE_PER_SESSION().call(),
        "package_price": vault.functions.PACKAGE_PRICE().call(),
        # The number the whole demo hinges on.
        "vault_balance": w3.eth.get_balance(vault.address),
    }

    if package_id:
        p = vault.functions.getPackage(package_id).call()
        state.update(
            {
                "total_paid": p[2],
                "sessions_used": p[3],
                "released": p[4],
                "withdrawn": p[5],
                "closed": p[6],
                "refunded": p[7],
                "protected": vault.functions.protectedBalance(package_id).call(),
                "available": vault.functions.availableToWithdraw(package_id).call(),
                "refund_preview": vault.functions.previewRefund(package_id).call(),
            }
        )
    else:
        state.update(
            {
                "total_paid": 0,
                "sessions_used": 0,
                "released": 0,
                "withdrawn": 0,
                "closed": False,
                "refunded": False,
                "protected": 0,
                "available": 0,
                "refund_preview": 0,
            }
        )
    return state


def reserve_ratio(state) -> int:
    if not state["has_package"] or state["total_paid"] == 0:
        return 0
    if state["refunded"]:
        return 0
    return round(state["protected"] * 100 / state["total_paid"])


# --------------------------------------------------------------------------
# Activity log
# --------------------------------------------------------------------------
def _deployment_block(contract_name: str) -> int:
    d = load_deployment() or {}
    return int(d.get("contracts", {}).get(contract_name, {}).get("blockNumber") or 0)


@st.cache_data(ttl=3, show_spinner=False)
def event_rows(rpc_url, deployment_path, from_block, latest_block):
    """Return (rows, error). rows = [dict(block, event, kind, actor, amount, text), ...]"""
    try:
        # Same backend the rest of the page uses; rpc_url/deployment_path only
        # participate in the cache key on a local run.
        w3 = _new_web3()
        d = load_deployment()
        if d is None:
            return [], "Could not open the deployment file: no deployment found."
        registry = w3.eth.contract(
            address=Web3.to_checksum_address(d["contracts"]["MerchantRegistry"]["address"]),
            abi=d["contracts"]["MerchantRegistry"]["abi"],
        )
        vault = w3.eth.contract(
            address=Web3.to_checksum_address(d["contracts"]["PrepayVault"]["address"]),
            abi=d["contracts"]["PrepayVault"]["abi"],
        )
        per_session = vault.functions.PRICE_PER_SESSION().call()
    except Exception as err:  # noqa: BLE001
        return [], f"Could not open the deployment file: {err}"

    rows = []

    def scan(contract, name, kind, actor_role, amount_fn, text_fn):
        try:
            logs = contract.events[name].get_logs(
                from_block=from_block, to_block=latest_block
            )
        except Exception as err:  # noqa: BLE001 - report, never swallow
            rows.append(
                {"block": 0, "event": name, "kind": "err", "actor": "", "amount": "",
                 "text": f"Could not read {name}: {err}"}
            )
            return
        for log in logs:
            a = log["args"]
            addr = a.get("consumer") or a.get("merchant") or ""
            rows.append(
                {
                    "block": log["blockNumber"],
                    "event": name,
                    "kind": kind,
                    "actor": f"{actor_role} {short(addr)}" if addr else actor_role,
                    "amount": amount_fn(a),
                    "text": text_fn(a),
                }
            )

    scan(registry, "MerchantRegistered", "reg", "Regulator", lambda a: "—",
         lambda a: f"Merchant registered — {short(a['merchant'])} licensed by regulator")
    scan(registry, "MerchantRevoked", "reg", "Regulator", lambda a: "—",
         lambda a: f"Merchant license revoked — {short(a['merchant'])}")
    scan(vault, "PackagePurchased", "con", "Consumer", lambda a: hkd(a["amount"]),
         lambda a: f"Package purchased — {hkd(a['amount'])} locked in escrow (package #{a['packageId']})")
    scan(vault, "SessionCompleted", "con", "Consumer", lambda a: hkd(per_session),
         lambda a: f"Session #{a['sessionNumber']} completed — {hkd(per_session)} released, "
                   f"{hkd(a['protectedBalance'])} still protected")
    scan(vault, "FundsWithdrawn", "mer", "Merchant", lambda a: hkd(a["amount"]),
         lambda a: f"Merchant withdrawal completed — {hkd(a['amount'])} paid out")
    scan(vault, "MerchantMarkedClosed", "reg", "Regulator", lambda a: "—",
         lambda a: "Merchant marked as closed by regulator")
    scan(vault, "RefundProcessed", "reg", "Regulator", lambda a: hkd(a["amount"]),
         lambda a: f"{hkd(a['amount'])} refunded to consumer")

    rows.sort(key=lambda r: r["block"])
    return rows, None


# --------------------------------------------------------------------------
# Shared UI blocks
# --------------------------------------------------------------------------
def page_header(title, subtitle, role=None):
    role_html = f'<span class="ps-role">{role}</span>' if role else ""
    st.markdown(
        f"""
        <div class="ps-head">
          <div>
            <div class="ps-head-t">{title}</div>
            <div class="ps-head-s">{subtitle}</div>
          </div>
          <div class="ps-head-r">{role_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def pill(text, kind):
    return f'<span class="ps-pill {kind}">{text}</span>'


def license_pill(licensed):
    return pill("Licensed", "ps-ok") if licensed else pill("Not licensed", "ps-off")


def status_pill(closed, has_package):
    if not has_package:
        return pill("Not started", "ps-idle")
    return pill("Closed", "ps-wait") if closed else pill("Active", "ps-ok")


def card(rows):
    body = "".join(
        f'<div class="ps-row"><span class="k">{k}</span><span class="v">{v}</span></div>'
        for k, v in rows
    )
    st.markdown(f'<div class="ps-card">{body}</div>', unsafe_allow_html=True)


def status_cards(state):
    """The three numbers the whole demo is about."""
    total = state["sessions_per_package"]
    st.markdown(
        f"""
        <div class="ps-cards">
          <div class="ps-sc" style="--acc:#1d4ed8">
            <div class="k2">Protected Consumer Funds</div>
            <div class="v2">{hkd(state['protected'])}</div>
            <div class="h2s">still locked in the vault</div>
          </div>
          <div class="ps-sc" style="--acc:#16a34a">
            <div class="k2">Released to Merchant</div>
            <div class="v2">{hkd(state['released'])}</div>
            <div class="h2s">earned by completed sessions</div>
          </div>
          <div class="ps-sc" style="--acc:#8a5a00">
            <div class="k2">Sessions Used</div>
            <div class="v2">{state['sessions_used']} / {total}</div>
            <div class="h2s">{hkd(state['price_per_session'])} released per session</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def fund_bar(state, show_total=True):
    """Three-segment bar: protected / withdrawable / already paid out."""
    withdrawn = state["withdrawn"]
    available = state["available"]
    protected = state["protected"]
    total = withdrawn + available + protected
    if total <= 0:
        st.markdown('<div class="ps-bar"></div>', unsafe_allow_html=True)
        cap("No funds have entered the vault yet.")
        return

    # One gradient with hard stops: no sub-pixel seam between segments.
    stops, acc = [], 0.0
    for value, colour in ((protected, "#1d4ed8"), (available, "#16a34a"), (withdrawn, "#94a3b8")):
        if value <= 0:
            continue
        width = value * 100 / total
        stops.append(f"{colour} {acc:.3f}% {acc + width:.3f}%")
        acc += width
    st.markdown(
        f'<div class="ps-bar" style="background:linear-gradient(to right,{",".join(stops)})"></div>',
        unsafe_allow_html=True,
    )

    legend = [f'<span><i class="p"></i>Protected {hkd(protected)}</span>']
    if available > 0:
        legend.append(f'<span><i class="a"></i>Withdrawable {hkd(available)}</span>')
    if withdrawn > 0:
        legend.append(f'<span><i class="w"></i>Paid out {hkd(withdrawn)}</span>')
    st.markdown(f'<div class="ps-legend">{"".join(legend)}</div>', unsafe_allow_html=True)
    if show_total:
        cap(
            f"Total prepaid {hkd(state['total_paid'])} — the vault contract holds "
            f"{hkd(state['vault_balance'])}; the merchant can withdraw {hkd(available)} of it, "
            f"and the other {hkd(protected)} does not exist as a withdrawable balance."
        )


def action(label, reason=None, primary=False, key=None, confirm=False):
    """A button that always explains why it is unavailable."""
    disabled = reason is not None
    clicked = st.button(
        label,
        use_container_width=True,
        disabled=disabled,
        type="primary" if (primary and not disabled) else "secondary",
        help=reason,
        key=key,
    )
    if disabled and reason:
        st.caption(f"🔒 {reason}")
    if not clicked:
        return False
    if confirm and not NO_CONFIRM and st.session_state.get("confirm_on", True):
        if st.session_state.get("_confirm") != key:
            st.session_state["_confirm"] = key
            st.warning(
                f"Click **{label}** once more to confirm. "
                "This writes an irreversible on-chain state change."
            )
            return False
        st.session_state.pop("_confirm", None)
    return True


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
def page_home(state, w3, registry, vault, accounts):
    st.markdown(
        """
        <div class="ps-hero">
          <div class="brand">PaySafe</div>
          <div class="eyebrow">Blockchain-based prepaid consumer protection</div>
          <h1>Pay only for the services you actually receive.</h1>
          <p class="sub">Prepaid funds remain protected in a smart contract and are
             released to the merchant session by session.</p>
          <p class="tag">Protecting prepaid consumer funds through smart contract escrow.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    status_cards(state)

    if not state["has_package"]:
        st.info(
            "**Step 1** — Go to **Regulator** and register the merchant.  \n"
            "**Step 2** — Go to **Consumer** and buy the HK$6,000 package.  \n"
            "The money then sits in the vault contract, not in the merchant's account.",
            icon="👉",
        )
        st.write("")
        st.markdown("#### How the escrow works")
        st.markdown(
            f"""
1. The consumer pays {hkd(state['package_price'])} into the vault contract.
2. Nothing is transferred to the merchant at purchase time.
3. Each completed session releases {hkd(state['price_per_session'])} — bookkeeping only, still inside the vault.
4. The merchant may withdraw only what has been released.
5. If the regulator closes the merchant, the unused balance goes back to the consumer.
            """
        )
        return

    st.markdown("#### Where the money actually is")
    fund_bar(state)

    st.write("")
    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("#### Package")
        card(
            [
                ("Package", f"{state['sessions_per_package']}-Session Service Package"),
                ("Total Prepaid Amount", hkd(state["total_paid"])),
                ("Price per Session", hkd(state["price_per_session"])),
                ("Sessions Used", f"{state['sessions_used']} / {state['sessions_per_package']}"),
                ("Sessions Remaining", f"{state['sessions_per_package'] - state['sessions_used']}"),
            ]
        )
    with right:
        st.markdown("#### Merchant & consumer")
        card(
            [
                ("Merchant License", license_pill(state["licensed"])),
                ("Business Status", status_pill(state["closed"], state["has_package"])),
                ("Refund Processed", pill("Yes", "ps-ok") if state["refunded"] else pill("No", "ps-idle")),
                ("Reserve Ratio", f"{reserve_ratio(state)}%"),
            ]
        )

    with st.expander("3-minute demo route"):
        st.markdown(
            """
| Step | Page | Action |
|---|---|---|
| 1 | Regulator | Register Merchant |
| 2 | Consumer | Buy Package |
| 3 | Consumer | Use One Session × 3 |
| 4 | Merchant | Test Excess Withdrawal → must fail |
| 5 | Merchant | Withdraw Available Funds |
| 6 | Regulator | Mark Merchant as Closed |
| 7 | Regulator | Process Consumer Refund |
| 8 | Regulator | Process Consumer Refund again → must fail |
            """
        )


def page_consumer(state, w3, registry, vault, accounts):
    page_header(
        "Consumer",
        "You paid for 12 sessions. The money is held in escrow, not handed over.",
        role="Consumer",
    )

    can_buy = not state["has_package"] and state["licensed"]
    can_use = (
        state["has_package"]
        and not state["closed"]
        and not state["refunded"]
        and state["sessions_used"] < state["sessions_per_package"]
    )

    status_cards(state)

    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("#### Package")
        card(
            [
                ("Package", f"{state['sessions_per_package']}-Session Service Package"),
                ("Package Price", hkd(state["package_price"])),
                ("Price per Session", hkd(state["price_per_session"])),
                ("Sessions Used", f"{state['sessions_used']} / {state['sessions_per_package']}"),
                ("Sessions Remaining", f"{state['sessions_per_package'] - state['sessions_used']}"),
            ]
        )
    with right:
        st.markdown("#### Protection status")
        card(
            [
                ("Protected Balance", hkd(state["protected"])),
                ("Released to Merchant", hkd(state["released"])),
                ("Merchant Status", status_pill(state["closed"], state["has_package"])),
                ("Refund Processed", pill("Yes", "ps-ok") if state["refunded"] else pill("No", "ps-idle")),
                ("Package", f"#{state['package_id']}" if state["has_package"] else "—"),
            ]
        )

    st.write("")
    b1, b2, _ = st.columns([1, 1, 1.6])
    with b1:
        if action(
            "Buy Package",
            None if can_buy else (
                "The package has already been purchased."
                if state["has_package"]
                else "The merchant is not licensed yet — ask the regulator to register it first."
            ),
            primary=can_buy,
            key="buy",
        ):
            send(
                w3,
                vault.functions.buyPackage(state["merchant"]),
                state["consumer"],
                "Package purchased successfully.",
                value=state["package_price"],
            )
    with b2:
        if action(
            "Use One Session",
            None if can_use else (
                "Buy the package first."
                if not state["has_package"]
                else "The merchant is closed — no further sessions are allowed."
                if state["closed"]
                else "The package has already been refunded."
                if state["refunded"]
                else "All sessions have been used."
            ),
            primary=can_use,
            key="use",
        ):
            send(
                w3,
                vault.functions.useSession(state["package_id"]),
                state["consumer"],
                "One session has been completed.\n\n"
                f"{hkd(state['price_per_session'])} is now available to the merchant.",
            )

    if state["has_package"]:
        st.write("")
        st.markdown("#### Where the money actually is")
        fund_bar(state)


def page_merchant(state, w3, registry, vault, accounts):
    page_header(
        "Merchant",
        "You can only withdraw what has already been released by completed sessions.",
        role="Merchant",
    )

    status_cards(state)

    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("#### Earnings")
        card(
            [
                ("Sessions Completed", f"{state['sessions_used']} / {state['sessions_per_package']}"),
                ("Released Amount", hkd(state["released"])),
                ("Withdrawn Amount", hkd(state["withdrawn"])),
                ("Available to Withdraw", hkd(state["available"])),
            ]
        )
    with right:
        st.markdown("#### Escrow")
        card(
            [
                ("Protected Consumer Funds", hkd(state["protected"])),
                ("Vault Balance", hkd(state["vault_balance"])),
                ("Merchant Status", status_pill(state["closed"], state["has_package"])),
                ("Merchant License", license_pill(state["licensed"])),
            ]
        )

    st.write("")
    avail_hkd = int(state["available"] // HKD)
    amount_hkd = 0
    if state["has_package"] and avail_hkd > 0:
        amount_hkd = st.number_input(
            "Amount to withdraw (HKD)",
            min_value=0,
            max_value=avail_hkd,
            value=avail_hkd,
            step=100,
            key="withdraw_amount",
        )

    b1, b2, _ = st.columns([1, 1, 1.2])
    with b1:
        if action(
            "Withdraw Available Funds",
            None if (state["has_package"] and amount_hkd > 0) else (
                "Buy a package first." if not state["has_package"] else "Nothing has been released yet."
            ),
            primary=True,
            key="withdraw",
        ):
            send(
                w3,
                vault.functions.withdrawReleasedAmount(state["package_id"], amount_hkd * HKD),
                state["merchant"],
                "Withdrawal successful.\n\nAmount: " + hkd(amount_hkd * HKD),
            )
    with b2:
        if action(
            "Test Excess Withdrawal",
            None if state["has_package"] else "Buy a package first.",
            key="excess",
        ):
            excess = state["available"] + state["price_per_session"]
            send(
                w3,
                vault.functions.withdrawReleasedAmount(state["package_id"], excess),
                state["merchant"],
                "Unexpected: the excess withdrawal succeeded.",
                extra_error_note="The merchant cannot withdraw unused consumer funds.",
            )
    cap(
        "Withdrawable balance = released amount − already withdrawn. "
        "Anything above that is rejected by the contract."
    )

    if state["has_package"]:
        st.write("")
        st.markdown("#### Where the money actually is")
        fund_bar(state)


def page_regulator(state, w3, registry, vault, accounts):
    page_header(
        "Regulator",
        "License the merchant, close it when needed, and release the consumer's refund.",
        role="Regulator",
    )

    has_pkg = state["has_package"]
    licensed = state["licensed"]
    closed = state["closed"]
    refunded = state["refunded"]

    # ---- step status ----------------------------------------------------
    if licensed:
        s1_state, s1_txt = "done", "Merchant Licensed"
    else:
        s1_state, s1_txt = "now", "Register the merchant"

    if closed:
        s2_state, s2_txt = "done", "Merchant Closed"
    elif has_pkg:
        s2_state, s2_txt = "now", "Merchant Active"
    else:
        s2_state, s2_txt = "wait", "Waiting for a package"

    if refunded:
        s3_state, s3_txt = "done", "Refund Processed"
    elif closed:
        s3_state, s3_txt = "now", "Refund Available"
    else:
        s3_state, s3_txt = "wait", "Refund Not Available"

    def badge(kind):
        return {"done": "Done", "now": "Action needed", "wait": "Locked"}[kind]

    st.markdown(
        f"""
        <div class="ps-steps">
          <div class="ps-step {s1_state}">
            <span class="num">01</span><span class="txt">{s1_txt}</span>
            <span class="st">{badge(s1_state)}</span>
          </div>
          <div class="ps-step {s2_state}">
            <span class="num">02</span><span class="txt">{s2_txt}</span>
            <span class="st">{badge(s2_state)}</span>
          </div>
          <div class="ps-step {s3_state}">
            <span class="num">03</span><span class="txt">{s3_txt}</span>
            <span class="st">{badge(s3_state)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("#### Merchant")
        card(
            [
                ("Merchant License", license_pill(licensed)),
                ("Business Status", status_pill(closed, has_pkg)),
                ("Merchant", short(state["merchant"])),
                ("Package", f"#{state['package_id']}" if has_pkg else "—"),
            ]
        )
    with right:
        st.markdown("#### Consumer protection")
        card(
            [
                ("Protected Balance", hkd(state["protected"])),
                ("Refund Amount", hkd(state["refund_preview"])),
                ("Refund Processed", pill("Yes", "ps-ok") if refunded else pill("No", "ps-idle")),
                ("Consumer", short(state["consumer"])),
            ]
        )

    st.write("")
    step1, step2, step3 = st.columns(3)

    with step1:
        st.markdown("**Step 1 · License the merchant**")
        if action(
            "Register Merchant",
            None if not licensed else "The merchant is already licensed.",
            primary=not licensed,
            key="register",
        ):
            send(
                w3,
                registry.functions.registerMerchant(state["merchant"]),
                state["regulator"],
                "Merchant registered successfully.",
            )

    with step2:
        st.markdown("**Step 2 · Close the merchant**")
        if action(
            "Mark Merchant as Closed",
            None if (has_pkg and not closed) else (
                "Buy a package first." if not has_pkg else "Already closed."
            ),
            primary=licensed and has_pkg and not closed,
            key="close",
            confirm=True,
        ):
            send(
                w3,
                vault.functions.markClosed(state["package_id"]),
                state["regulator"],
                "Merchant has been marked as closed.",
            )

    with step3:
        st.markdown("**Step 3 · Refund the unused balance**")
        if action(
            "Process Consumer Refund",
            None if (has_pkg and closed) else (
                "Buy a package first." if not has_pkg else "Close the merchant first."
            ),
            primary=closed and not refunded,
            key="refund",
            confirm=True,
        ):
            amount = state["refund_preview"]
            send(
                w3,
                vault.functions.refundUnusedBalance(state["package_id"]),
                state["regulator"],
                "Consumer refund processed successfully.\n\nRefund Amount: " + hkd(amount),
            )

    if has_pkg:
        st.write("")
        st.markdown("#### Where the money actually is")
        fund_bar(state)

    st.write("")
    with st.expander("Exception path · revoke the merchant licence"):
        cap(
            "Revoking the licence does not touch existing packages — it only stops "
            "new packages from being purchased. Use it to show that licensing is "
            "a live on-chain permission, not a one-off check."
        )
        if action(
            "Revoke Merchant License",
            None if licensed else "The merchant is not licensed.",
            key="revoke",
            confirm=True,
        ):
            send(
                w3,
                registry.functions.revokeMerchant(state["merchant"]),
                state["regulator"],
                "Merchant license revoked.",
            )


def page_activity(state, w3, registry, vault, accounts):
    page_header(
        "Activity Log",
        "Every row below is a contract event. Block numbers form the audit trail.",
    )

    from_block = min(_deployment_block("MerchantRegistry"), _deployment_block("PrepayVault"))
    rows, error = event_rows(RPC_URL, str(DEPLOYMENT_FILE), from_block, state["block"])

    if error:
        st.warning(error, icon="⚠️")

    for r in rows:
        if r["kind"] == "err":
            st.caption(r["text"])

    real = [r for r in rows if r["kind"] != "err"]
    if not real:
        st.info("No on-chain activity yet. Start with Register Merchant on the Regulator page.")
        return

    for r in real:
        text = r["text"].replace("$", "&#36;")
        amount = r["amount"].replace("$", "&#36;")
        st.markdown(
            f'<div class="ps-log">'
            f'<div class="ps-log-top">'
            f'<span class="ps-ev">{r["event"]}</span>'
            f'<span class="ps-blk">Block #{r["block"]}</span>'
            f'<span class="ps-actor"><span class="ps-dot {r["kind"]}"></span>{r["actor"]}</span>'
            f'<span class="ps-amt">{amount}</span>'
            f'</div>'
            f'<div class="ps-log-bot">{text}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    try:
        w3, registry, vault, accounts = connect()
        state = read_state(w3, registry, vault, accounts)
    except Exception as err:  # noqa: BLE001
        st.error(f"**Cannot load the demo**\n\n{err}")
        st.code(
            "# 1) start the local chain\n"
            "npx hardhat node\n\n"
            "# 2) in a second terminal, deploy the contracts\n"
            "npx hardhat run scripts/deploy.js --network localhost\n\n"
            "# 3) start this app\n"
            "streamlit run frontend/app.py",
            language="bash",
        )
        st.stop()

    pages = {
        "Home": page_home,
        "Consumer": page_consumer,
        "Merchant": page_merchant,
        "Regulator": page_regulator,
        "Activity Log": page_activity,
    }

    requested = st.query_params.get("page", "Home")
    if isinstance(requested, list):
        requested = requested[0]
    default_index = PAGES.index(requested) if requested in PAGES else 0

    # ---- top navigation ------------------------------------------------
    # A radio's element id is hashed from its parameters, and `index` is one of
    # them. Passing an index that changes with the URL therefore makes Streamlit
    # tear the widget down and rebuild it on every navigation, which throws away
    # the value the user just clicked (every second click was being lost). A
    # stable key pins the id, so `index` is consulted only on the first render
    # and the widget keeps its identity for the rest of the session.
    page = st.radio(
        "Navigation",
        PAGES,
        index=default_index,
        key="nav_page",
        horizontal=True,
        label_visibility="collapsed",
    )

    # Keep the address bar in sync so a refresh never loses the page. Written
    # after the widget is built, so it can never feed back into the index.
    if st.query_params.get("page") != page:
        st.query_params["page"] = page

    # ---- compact status bar + demo info --------------------------------
    # Name the chain honestly: a hosted build runs one inside the app process,
    # not a node on the presenter's machine.
    chain_label = "In-process chain" if HOSTED else "Local chain"
    st.markdown(
        f"""
        <div class="ps-status">
          <span class="live"><i></i>{chain_label}</span>
          <span>Block <b>#{state['block']}</b></span>
          <span>Vault <b>{hkd(state['vault_balance'])}</b></span>
          <span>Reserve <b>{reserve_ratio(state)}%</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Demo information"):
        st.markdown(
            f"**Regulator** `{state['regulator']}`  \n"
            f"**Merchant** `{state['merchant']}`  \n"
            f"**Consumer** `{state['consumer']}`"
        )
        st.caption(
            "Roles are fixed to Hardhat accounts[0..2] so the CLI, the tests and this UI "
            "always agree on who is who."
        )
        st.checkbox(
            "Confirm destructive actions",
            value=not NO_CONFIRM,
            disabled=NO_CONFIRM,
            key="confirm_on",
            help="Ask for a second click before writing an irreversible state change.",
        )
        if st.button("Refresh chain state", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.write("")
    show_flash()
    pages[page](state, w3, registry, vault, accounts)


if __name__ == "__main__":
    main()
