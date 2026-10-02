"""Proportional, explainable attribution of reported value through wallet flows."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Any

from core.simulator import ReplayResult, TransactionSimulator

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_DOWN)


@dataclass(frozen=True)
class WalletTaint:
    wallet_id: str
    customer_type: str
    balance_bdt: Decimal
    potentially_tainted_bdt: Decimal
    potentially_legitimate_bdt: Decimal
    potentially_tainted_ratio: Decimal


@dataclass(frozen=True)
class TaintMovement:
    transaction_id: str
    timestamp: datetime
    from_wallet: str
    to_wallet: str
    transaction_type: str
    gross_amount_bdt: Decimal
    potentially_tainted_bdt: Decimal
    potentially_legitimate_bdt: Decimal
    terminal_cashout: bool


@dataclass(frozen=True)
class CashoutAttribution:
    transaction_id: str
    timestamp: datetime
    wallet_id: str
    gross_cashout_bdt: Decimal
    potentially_tainted_bdt: Decimal
    potentially_legitimate_bdt: Decimal


@dataclass(frozen=True)
class TaintResult:
    scenario_id: str
    incident_id: str
    incident_type: str
    reported_transaction_id: str
    as_of: datetime
    method: str
    interpretation: str
    reported_amount_bdt: Decimal
    remaining_potentially_tainted_bdt: Decimal
    remaining_potentially_legitimate_bdt: Decimal
    cashed_out_potentially_tainted_bdt: Decimal
    cashed_out_potentially_legitimate_bdt: Decimal
    unattributed_bdt: Decimal
    wallets: tuple[WalletTaint, ...]
    movements: tuple[TaintMovement, ...]
    cashouts: tuple[CashoutAttribution, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-ready values without converting money to binary floats."""
        return _json_ready(asdict(self))


def calculate_proportional_taint(replay: ReplayResult) -> TaintResult:
    """Propagate reported value in proportion to each sender's balance.

    The reported transaction seeds potentially tainted value at its direct
    recipient. For each later outgoing event, the attributed portion is
    `outgoing amount * (tainted balance / total balance before the event)`.
    We round moved attribution down to one poisha so rounding never increases
    the reported amount. Cash-outs remove the attributed portion from digital
    balances and are reported separately as terminal flows.
    """
    incident = replay.incident
    reported_id = str(incident["reported_transaction_id"])
    reported_event = next(
        (event for event in replay.transactions if event.transaction_id == reported_id),
        None,
    )
    if reported_event is None:
        raise ValueError("The replay does not include the incident's reported transaction.")

    reported_amount = _money(_decimal(incident["reported_amount"]))
    if reported_amount <= ZERO or reported_amount > _money(_decimal(reported_event.amount)):
        raise ValueError("Reported amount must be positive and no greater than its transaction amount.")

    balances = {wallet_id: _money(_decimal(value)) for wallet_id, value in replay.initial_balances.items()}
    tainted = {wallet_id: ZERO for wallet_id in balances}
    movements: list[TaintMovement] = []
    cashouts: list[CashoutAttribution] = []
    seeded = False

    for event in replay.transactions:
        sender_balance = balances[event.sender_wallet]
        receiver_balance = balances[event.receiver_wallet]
        if sender_balance != _money(_decimal(event.sender_balance_before)):
            raise ValueError(f"Replay balance changed unexpectedly before {event.transaction_id}.")
        if receiver_balance != _money(_decimal(event.receiver_balance_before)):
            raise ValueError(f"Replay balance changed unexpectedly before {event.transaction_id}.")

        amount = _money(_decimal(event.amount))
        if event.transaction_id == reported_id:
            balances[event.sender_wallet] -= amount
            balances[event.receiver_wallet] += amount
            tainted[event.receiver_wallet] += reported_amount
            movements.append(TaintMovement(
                transaction_id=event.transaction_id,
                timestamp=event.timestamp,
                from_wallet=event.sender_wallet,
                to_wallet=event.receiver_wallet,
                transaction_type=event.transaction_type,
                gross_amount_bdt=amount,
                potentially_tainted_bdt=reported_amount,
                potentially_legitimate_bdt=amount - reported_amount,
                terminal_cashout=False,
            ))
            seeded = True
            continue

        # Transactions before the reported transfer only establish balances.
        if not seeded:
            balances[event.sender_wallet] -= amount
            balances[event.receiver_wallet] += amount
            continue

        if sender_balance <= ZERO:
            moved_taint = ZERO
        else:
            proportion = min(Decimal(1), tainted[event.sender_wallet] / sender_balance)
            moved_taint = min(
                tainted[event.sender_wallet],
                _money(amount * proportion),
            )
        legitimate_part = amount - moved_taint
        is_cashout = (
            event.transaction_type == "cashout"
            or replay.wallet_types.get(event.receiver_wallet) == "cash_destination"
        )

        tainted[event.sender_wallet] -= moved_taint
        if not is_cashout:
            tainted[event.receiver_wallet] += moved_taint
        else:
            cashouts.append(CashoutAttribution(
                transaction_id=event.transaction_id,
                timestamp=event.timestamp,
                wallet_id=event.sender_wallet,
                gross_cashout_bdt=amount,
                potentially_tainted_bdt=moved_taint,
                potentially_legitimate_bdt=legitimate_part,
            ))

        balances[event.sender_wallet] -= amount
        balances[event.receiver_wallet] += amount
        movements.append(TaintMovement(
            transaction_id=event.transaction_id,
            timestamp=event.timestamp,
            from_wallet=event.sender_wallet,
            to_wallet=event.receiver_wallet,
            transaction_type=event.transaction_type,
            gross_amount_bdt=amount,
            potentially_tainted_bdt=moved_taint,
            potentially_legitimate_bdt=legitimate_part,
            terminal_cashout=is_cashout,
        ))

    if not seeded:
        raise ValueError("The reported transaction was not processed in replay order.")
    for wallet_id, expected in replay.final_balances.items():
        if balances[wallet_id] != _money(_decimal(expected)):
            raise ValueError(f"Taint replay balance does not match transaction replay for {wallet_id}.")

    wallet_rows: list[WalletTaint] = []
    for wallet_id, balance in replay.final_balances.items():
        if replay.wallet_types.get(wallet_id) == "cash_destination":
            continue
        wallet_balance = _money(_decimal(balance))
        wallet_tainted = _money(tainted[wallet_id])
        if wallet_tainted > wallet_balance:
            raise ValueError(f"Potential taint exceeds the current balance of {wallet_id}.")
        legitimate_balance = wallet_balance - wallet_tainted
        ratio = wallet_tainted / wallet_balance if wallet_balance > ZERO else ZERO
        wallet_rows.append(WalletTaint(
            wallet_id=wallet_id,
            customer_type=replay.wallet_types.get(wallet_id, "unknown"),
            balance_bdt=wallet_balance,
            potentially_tainted_bdt=wallet_tainted,
            potentially_legitimate_bdt=legitimate_balance,
            potentially_tainted_ratio=ratio.quantize(Decimal("0.0001"), rounding=ROUND_DOWN),
        ))

    remaining_tainted = sum(
        (wallet.potentially_tainted_bdt for wallet in wallet_rows), ZERO
    )
    remaining_legitimate = sum(
        (
            wallet.potentially_legitimate_bdt
            for wallet in wallet_rows
            if wallet.potentially_tainted_bdt > ZERO
        ),
        ZERO,
    )
    cashed_out_tainted = sum((item.potentially_tainted_bdt for item in cashouts), ZERO)
    cashed_out_legitimate = sum((item.potentially_legitimate_bdt for item in cashouts), ZERO)
    accounted_taint = remaining_tainted + cashed_out_tainted
    if accounted_taint > reported_amount:
        raise ValueError("Proportional attribution exceeded the reported amount.")
    unattributed = reported_amount - accounted_taint

    return TaintResult(
        scenario_id=replay.scenario_id,
        incident_id=str(incident["incident_id"]),
        incident_type=str(incident["incident_type"]),
        reported_transaction_id=reported_id,
        as_of=replay.as_of,
        method="proportional_balance",
        interpretation=(
            "Potential value attributed to the reported transfer under a synthetic proportional-flow assumption; "
            "this is not a fraud finding or a determination of ownership."
        ),
        reported_amount_bdt=reported_amount,
        remaining_potentially_tainted_bdt=remaining_tainted,
        remaining_potentially_legitimate_bdt=remaining_legitimate,
        cashed_out_potentially_tainted_bdt=cashed_out_tainted,
        cashed_out_potentially_legitimate_bdt=cashed_out_legitimate,
        unattributed_bdt=unattributed,
        wallets=tuple(wallet_rows),
        movements=tuple(movements),
        cashouts=tuple(cashouts),
    )


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate proportional reported-fund attribution for a synthetic scenario.")
    parser.add_argument("scenario_id", help="Scenario ID, such as SCN-06-FANOUT-CASHOUT")
    parser.add_argument("--at", dest="as_of", help="Optional timezone-aware ISO 8601 replay cutoff")
    parser.add_argument("--database", help="SQLite database path")
    args = parser.parse_args()
    replay = TransactionSimulator(args.database).replay(args.scenario_id, args.as_of)
    result = calculate_proportional_taint(replay)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
