# PaySafe — 3-Minute Demo Script

Presenter script for the FTEC5520A final project demo.
Every quoted line is the exact text that appears on screen.

**Before you start**

- Terminal 1: `npx hardhat node` is running
- Terminal 2: `npx hardhat run scripts/deploy.js --network localhost` has completed
- Terminal 3: `streamlit run frontend/app.py` is running, browser on <http://localhost:8501>
- Chain is fresh: no merchant registered yet

**Reset if it is not fresh.** Open **Demo information** (top of any page) → **Reset demo chain** →
click twice. It deploys a new contract pair and starts from zero: no licence, no package, no
events. On the hosted link this is the only way to reset, and it is shared by everyone watching.
Restarting the node and redeploying also works locally, and additionally renumbers blocks from 0.

Two things that will otherwise make you think the UI is broken:

1. **Four buttons need two clicks.** *Mark Merchant as Closed*, *Process Consumer Refund*,
   *Revoke Merchant License* and *Reset demo chain* are irreversible, so the first click only shows
   "Click **…** once more to confirm. This writes an irreversible on-chain state change."
   Click the same button again to actually send the transaction.
2. **Every success message ends with a transaction line** (`Tx 0x… · block #N · gas …`).
   The quoted text below is the first line; the transaction line is proof it really hit the chain.

Total: ~3 minutes. Steps 1, 5 and 9 are the three rejection paths — slow down there.

---

## 0:00 — Opening (20s)

On **Home**, point at the three numbers.

> "A consumer pays HK$6,000 up front for 12 sessions. In a normal prepaid business that money
> lands in the merchant's bank account on day one, and if the merchant closes on day two the
> consumer is an unsecured creditor.
>
> PaySafe puts that money in a smart contract instead. The merchant only ever gets what the
> consumer has actually used."

Point at the three cards under the headline — **Protected Consumer Funds / Released to Merchant /
Sessions Used**. They stay on every page, so the audience can watch the money move.

---

## 0:20 — Step 1: Purchase Without a Licence (15s) — **rejection path 1**

**Consumer → Test Unlicensed Purchase**

> "Before we even license anyone: can the merchant take a prepayment while it is not on the
> register? The consumer has HK$6,000 ready and presses the button."

Screen:

```
Transaction Reverted

Merchant is not licensed.
The registry gate runs before any money moves — nothing was paid and nothing entered the vault.
```

> "The refusal comes from the contract, not from this page. There is no state where unlicensed
> money is sitting in escrow waiting to be sorted out."

---

## 0:35 — Step 2: Register Merchant (15s)

**Regulator → Register Merchant**

> "Only a licensed merchant can accept prepayments. The regulator licenses it here."

Screen: `Merchant registered successfully.` — License: **Licensed**, Business Status: **Active**

---

## 0:50 — Step 3: Buy Package (20s)

**Consumer → Buy Package**

> "The consumer pays the full HK$6,000. Watch where it goes — nowhere. It stays inside the vault
> contract. The merchant's withdrawable balance is still zero."

Screen: Total Paid **HK$6,000**, Released **HK$0**, Protected **HK$6,000**, Reserve Ratio **100%**

---

## 1:10 — Step 4: Use Three Sessions (25s)

**Consumer → Use One Session** ×3

> "Each completed session releases HK$500. Three sessions, HK$1,500 earned.
> Note the wording — *released*, not *transferred*. The contract has only updated a counter.
> The money has not moved yet."

Screen: Sessions **3 / 12**, Released **HK$1,500**, Protected **HK$4,500**, Reserve Ratio **75%**

---

## 1:35 — Step 5: Excess Withdrawal (30s) — **rejection path 2, key moment**

**Merchant → Test Excess Withdrawal**

> "The merchant has earned HK$1,500. Let's see what happens if it tries to take the whole
> HK$6,000 — the classic prepaid scam: take the money, then close the shop."

Screen:

```
Transaction Reverted

Reserve funds are locked.
The merchant cannot withdraw unused consumer funds.
```

> "This is not a policy the platform chose to enforce. There is no HK$4,500 sitting in a
> withdrawable balance to take. `releasedAmount` is HK$1,500, `withdrawnAmount` is zero, so the
> maximum the contract will pay out is HK$1,500 — anything above that reverts."

Note: this one is titled *Transaction Reverted*, like step 1; the double-refund in step 9 is
titled *Transaction Failed*. The project brief (§11) prints *Transaction Failed* for this screen —
same meaning, the contract simply reverts.

---

## 2:05 — Step 6: Normal Withdrawal (20s)

**Merchant → Withdraw Available Funds**

> "The legitimate withdrawal works, for exactly the earned amount."

The **Amount to withdraw (HKD)** field is pre-filled with the full available amount (1500).
Leave it as it is and press the button.

Screen: `Withdrawal successful.` — Amount: **HK$1,500**. Available to Withdraw drops to **HK$0**,
Protected stays **HK$4,500**, and the button now says
"All HK$1,500 released so far has already been withdrawn."

---

## 2:25 — Step 7: Merchant Closes (15s)

**Regulator → Mark Merchant as Closed** — *click twice* (first click asks for confirmation)

> "Now the merchant shuts down. In the real world this is where the consumer loses everything.
> Here the regulator flags it on-chain."

Screen: `Merchant has been marked as closed.` — Business Status: **Closed**

---

## 2:40 — Step 8: Refund (15s)

**Regulator → Process Consumer Refund** — *click twice*

> "The unused balance goes back automatically. HK$4,500 — the money for the nine sessions that
> were never delivered."

Screen: `Consumer refund processed successfully.` — Refund Amount: **HK$4,500**.
Protected Funds → **HK$0**.

The bar under it now reads **Protected HK$0 · Paid out HK$1,500 · Refunded HK$4,500** — all
HK$6,000 accounted for.

---

## 2:55 — Step 9: Double Refund (10s) — **rejection path 3**

**Regulator → Process Consumer Refund** again — *click twice* (the first click only asks to
confirm; the second one sends the transaction and gets rejected)

> "And it can only happen once."

Screen:

```
Transaction Failed

Refund has already been processed.
```

---

## 3:05 — Close (10s)

**Activity Log** page.

> "Every step you just watched is an on-chain event — registered, purchased, three sessions,
> one rejected withdrawal, one successful withdrawal, closure, refund. Each row names the role and
> the wallet that role uses, and if you open it you get the transaction hash and gas used."

Click any row to show `Tx 0x…` and gas. Point out `Regulator → Consumer 0x6813…BA69` on the refund
row — the actor is the regulator, the money went to the consumer's wallet.

> "The whole protection mechanism is about 270 lines of Solidity across two contracts, with no
> oracle and no trusted third party holding the money."

---

## If someone asks…

**"Is this a real blockchain or a simulation?"**
The EVM is real, the chain is disposable. On the laptop it is a Hardhat node on 127.0.0.1:8545;
on the hosted link it is py-evm running inside the app process (eth-tester). Either way the
contracts are compiled Solidity, every state change is a mined transaction with a hash, block
number and gas, and the UI reads all of it back from the chain — no numbers are stored in the app.
What is *not* real is the money: 1 HKD is mapped to 1e15 wei so HK$6,000 is 6 test ETH.

**"What if the merchant marks twelve sessions complete itself?"**
It cannot. `useSession` requires `msg.sender` to be the consumer, and there is no merchant-side
function that releases money. Show it live: Merchant → *Exception path* → *Test Completing a
Session* → `Transaction Reverted / Only the consumer can use a session.` It is off the timed route
because it answers a permission question, not a business step.

**"And if the consumer simply refuses to confirm?"**
Then the merchant is not paid and the money stays in escrow. There is no arbitration and no
timeout release in this contract; the exit is the regulator closing the merchant, which refunds the
consumer. That is the honest limit of a consumer-confirmed model without an oracle.

**"Why doesn't `useSession` transfer the money immediately?"**
It could. Separating "earned" from "withdrawn" makes the invariant explicit and lets the
merchant batch withdrawals; the safety property comes from the same subtraction either way.

**"What if the regulator colludes with the merchant?"**
The regulator here can only *close* a merchant and *trigger* a refund — it cannot redirect funds
or withdraw on the merchant's behalf. Refunds always go to the consumer recorded in the package.

**"What stops the merchant from never delivering a session?"**
Nothing in this contract — the consumer controls `useSession`, so an undelivered session is simply
never recorded, and the money stays protected until closure triggers a refund.

**"Why 1e15 wei per HKD?"**
The demo runs on a local chain with simulated funds. HK$6,000 maps to 6 ETH so the transfer is
real but affordable; the UI divides by 1e15 to show HK$ figures.
