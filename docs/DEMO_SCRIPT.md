# PaySafe — 3-Minute Demo Script

Presenter script for the FTEC5520A final project demo.
Every quoted line is the exact text that appears on screen.

**Before you start**

- Terminal 1: `npx hardhat node` is running
- Terminal 2: `npx hardhat run scripts/deploy.js --network localhost` has completed
- Terminal 3: `streamlit run frontend/app.py` is running, browser on <http://localhost:8501>
- Chain is fresh: no merchant registered yet

Two things that will otherwise make you think the UI is broken:

1. **Three buttons need two clicks.** *Mark Merchant as Closed*, *Process Consumer Refund* and
   *Revoke Merchant License* are irreversible, so the first click only shows
   "Click **…** once more to confirm. This writes an irreversible on-chain state change."
   Click the same button again to actually send the transaction.
2. **Every success message ends with a transaction line** (`Tx 0x… · block #N · gas …`).
   The quoted text below is the first line; the transaction line is proof it really hit the chain.

Total: ~3 minutes. Steps 4 and 8 are the two moments that matter — slow down there.

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

## 0:20 — Step 1: Register Merchant (15s)

**Regulator → Register Merchant**

> "Only a licensed merchant can accept prepayments. The regulator licenses it here."

Screen: `Merchant registered successfully.` — License: **Licensed**, Business Status: **Active**

---

## 0:35 — Step 2: Buy Package (20s)

**Consumer → Buy Package**

> "The consumer pays the full HK$6,000. Watch where it goes — nowhere. It stays inside the vault
> contract. The merchant's withdrawable balance is still zero."

Screen: Total Paid **HK$6,000**, Released **HK$0**, Protected **HK$6,000**, Reserve Ratio **100%**

---

## 0:55 — Step 3: Use Three Sessions (30s)

**Consumer → Use One Session** ×3

> "Each completed session releases HK$500. Three sessions, HK$1,500 earned.
> Note the wording — *released*, not *transferred*. The contract has only updated a counter.
> The money has not moved yet."

Screen: Sessions **3 / 12**, Released **HK$1,500**, Protected **HK$4,500**, Reserve Ratio **75%**

---

## 1:25 — Step 4: Excess Withdrawal (35s) — **key moment**

**Merchant → Test Excess Withdrawal**

> "The merchant has earned HK$1,500. Let's see what happens if it tries to take the whole
> HK$6,000 — the classic prepaid scam: take the money, then close the shop."

Screen:

```
Transaction Failed

Reserve funds are locked.
The merchant cannot withdraw unused consumer funds.
```

> "This is not a policy the platform chose to enforce. There is no HK$4,500 sitting in a
> withdrawable balance to take. `releasedAmount` is HK$1,500, `withdrawnAmount` is zero, so the
> maximum the contract will pay out is HK$1,500 — anything above that reverts."

---

## 2:00 — Step 5: Normal Withdrawal (20s)

**Merchant → Withdraw Available Funds**

> "The legitimate withdrawal works, for exactly the earned amount."

The **Amount to withdraw (HKD)** field is pre-filled with the full available amount (1500).
Leave it as it is and press the button.

Screen: `Withdrawal successful.` — Amount: **HK$1,500**. Available to Withdraw drops to **HK$0**,
Protected stays **HK$4,500**.

---

## 2:20 — Step 6: Merchant Closes (15s)

**Regulator → Mark Merchant as Closed** — *click twice* (first click asks for confirmation)

> "Now the merchant shuts down. In the real world this is where the consumer loses everything.
> Here the regulator flags it on-chain."

Screen: `Merchant has been marked as closed.` — Business Status: **Closed**

---

## 2:35 — Step 7: Refund (15s)

**Regulator → Process Consumer Refund** — *click twice*

> "The unused balance goes back automatically. HK$4,500 — the money for the nine sessions that
> were never delivered."

Screen: `Consumer refund processed successfully.` — Refund Amount: **HK$4,500**.
Protected Funds → **HK$0**.

---

## 2:50 — Step 8: Double Refund (10s) — **second key moment**

**Regulator → Process Consumer Refund** again — *click twice* (the first click only asks to
confirm; the second one sends the transaction and gets rejected)

> "And it can only happen once."

Screen:

```
Transaction Failed

Refund has already been processed.
```

---

## 3:00 — Close (10s)

**Activity Log** page.

> "Every step you just watched is an on-chain event — registered, purchased, three sessions,
> one rejected withdrawal, one successful withdrawal, closure, refund. The whole protection
> mechanism is about 270 lines of Solidity across two contracts, with no oracle and no trusted
> third party holding the money."

---

## If someone asks…

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
