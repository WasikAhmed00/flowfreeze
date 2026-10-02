# Proportional Reported-Fund Attribution

## Purpose and limits

FlowFreeze uses the term **potentially tainted** as a bookkeeping estimate for value linked to a reported transaction. It does not mean that funds are legally tainted, that a wallet owner committed fraud, or that the value is recoverable. All current data is synthetic.

The engine starts with the reported transaction's amount at its direct recipient and carries that estimate through events visible by the replay's `as_of` timestamp. The incident type remains attached to the result; a wrong-recipient dispute is not converted into a fraud finding.

## MVP rule

For a wallet with pre-event balance `B`, potentially tainted balance `T`, and outgoing event amount `A`:

```text
tainted share = min(1, T / B)
potentially tainted amount moved = min(T, round_down_to_৳0.01(A × tainted share))
potentially legitimate amount moved = A − potentially tainted amount moved
```

The moved attribution is subtracted from the sender and added to a digital recipient. Legitimate incoming value increases the wallet balance but does not increase its potentially tainted amount. The ratio therefore changes as balances and flows change.

Cash-out events remove the proportionally attributed amount from digital wallets and record it separately. A cash-out destination is a terminal ledger sink, not a downstream digital wallet.

## Output

For each digital wallet at the analysis time, the result reports:

- Current balance
- Potentially tainted estimate
- Potentially legitimate remainder
- Potentially tainted share of that wallet's balance

It also reports the original reported amount, each movement used as evidence, potentially tainted and legitimate cash-out amounts, and any unattributed remainder. The summary's potentially legitimate remainder is collateral in wallets that still contain a nonzero potentially tainted estimate; unaffected wallets remain visible in the per-wallet list but are excluded from that collateral summary. Amounts are represented as decimal BDT to two places; the initial synthetic data uses whole BDT amounts.

## Assumptions

- The incident's reported amount seeds the estimate at the direct recipient.
- Subsequent value is fungible, so every outgoing amount draws the same tainted/legitimate proportions from the sender's current balance.
- No taint is created by later legitimate inflows.
- Attribution is rounded down to one poisha at each movement so rounding cannot increase the amount attributed to the report.
- Only events included in the time-bounded replay contribute to the estimate.

## Known limitations

- Real money is fungible and ledger balances do not establish legal ownership or prove which physical units moved.
- The result is sensitive to the generated transaction history, opening balances, report amount, and time cutoff.
- This is one explainable assumption, not ground truth. First-in/first-out, last-in/first-out, and whole-balance assumptions may produce different collateral exposure; they can be compared in a later evaluation phase.
- Recommendations must show the estimate and collateral exposure separately and require human review.
