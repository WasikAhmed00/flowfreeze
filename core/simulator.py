"""Time-ordered, balance-checked replay of synthetic MFS transactions."""

from __future__ import annotations

import sqlite3
import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.db import connect_database


class ReplayValidationError(ValueError):
    """Raised when stored scenario records cannot be replayed consistently."""


@dataclass(frozen=True)
class TransactionEvent:
    transaction_id: str
    timestamp: datetime
    sender_wallet: str
    receiver_wallet: str
    amount: int
    transaction_type: str
    channel: str
    agent_id: str | None
    scenario_id: str
    sender_balance_before: int
    sender_balance_after: int
    receiver_balance_before: int
    receiver_balance_after: int


@dataclass(frozen=True)
class CashoutEvent:
    transaction_id: str
    timestamp: datetime
    wallet_id: str
    amount: int
    agent_id: str | None
    destination_wallet: str


@dataclass(frozen=True)
class ReplaySnapshot:
    timestamp: datetime
    balances: dict[str, int]
    transaction_count: int
    cashout_count: int
    cashout_total: int


@dataclass(frozen=True)
class ReplayResult:
    scenario_id: str
    incident: dict[str, Any]
    as_of: datetime
    initial_balances: dict[str, int]
    final_balances: dict[str, int]
    wallet_types: dict[str, str]
    transactions: tuple[TransactionEvent, ...]
    cashouts: tuple[CashoutEvent, ...]
    snapshots: tuple[ReplaySnapshot, ...]

    @property
    def digital_balances(self) -> dict[str, int]:
        """Current balances for digital wallets, excluding the cash-out sink."""
        return {
            wallet_id: balance
            for wallet_id, balance in self.final_balances.items()
            if self.wallet_types.get(wallet_id) != "cash_destination"
        }


def _parse_datetime(value: str | datetime, field: str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ReplayValidationError(f"Invalid {field} timestamp: {value!r}") from exc
    else:
        parsed = value
    if parsed.tzinfo is None:
        raise ReplayValidationError(f"{field} must include a timezone.")
    return parsed.astimezone(timezone.utc)


def _integer(row: sqlite3.Row, field: str, transaction_id: str) -> int:
    value = row[field]
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:
        raise ReplayValidationError(
            f"Transaction {transaction_id} has invalid integer field {field}: {value!r}"
        ) from exc
    if isinstance(value, float) and value != integer:
        raise ReplayValidationError(
            f"Transaction {transaction_id} has fractional {field}; MVP money values must be whole BDT."
        )
    return integer


class TransactionSimulator:
    """Load and replay one synthetic incident scenario from SQLite.

    Balances start at each wallet's `baseline_balance`. A replay cutoff is
    applied before any event is processed, so post-cutoff transactions cannot
    leak into a snapshot.
    """

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = database_path

    def replay(
        self,
        scenario_id: str,
        as_of: str | datetime | None = None,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ReplayResult:
        owns_connection = connection is None
        db = connection or connect_database(self.database_path)
        db.row_factory = sqlite3.Row
        try:
            return self._replay(db, scenario_id, as_of)
        finally:
            if owns_connection:
                db.close()

    def _replay(
        self,
        db: sqlite3.Connection,
        scenario_id: str,
        as_of: str | datetime | None,
    ) -> ReplayResult:
        self._require_tables(db)
        incident_row = db.execute(
            "SELECT * FROM incidents WHERE scenario_id = ? ORDER BY incident_id LIMIT 1",
            (scenario_id,),
        ).fetchone()
        if incident_row is None:
            raise KeyError(f"No incident exists for scenario {scenario_id!r}.")
        incident = dict(incident_row)
        cutoff = _parse_datetime(as_of or incident["analysis_at"], "as_of")
        report_time = _parse_datetime(str(incident["reported_at"]), "reported_at")
        if report_time > cutoff:
            raise ReplayValidationError("Replay cutoff is earlier than the incident report time.")

        wallet_rows = db.execute(
            "SELECT * FROM wallets WHERE scenario_id = ? ORDER BY wallet_id",
            (scenario_id,),
        ).fetchall()
        if not wallet_rows:
            raise ReplayValidationError(f"Scenario {scenario_id!r} has no wallets.")
        balances: dict[str, int] = {}
        wallet_types: dict[str, str] = {}
        for wallet in wallet_rows:
            wallet_id = str(wallet["wallet_id"])
            try:
                balance = int(wallet["baseline_balance"])
            except (TypeError, ValueError) as exc:
                raise ReplayValidationError(f"Wallet {wallet_id} has an invalid baseline balance.") from exc
            if balance < 0:
                raise ReplayValidationError(f"Wallet {wallet_id} has a negative baseline balance.")
            balances[wallet_id] = balance
            wallet_types[wallet_id] = str(wallet["customer_type"])
        initial_balances = balances.copy()

        raw_rows = db.execute(
            "SELECT * FROM transactions WHERE scenario_id = ? ORDER BY timestamp, transaction_id",
            (scenario_id,),
        ).fetchall()
        raw_rows = sorted(
            raw_rows,
            key=lambda row: (
                _parse_datetime(str(row["timestamp"]), "transaction"),
                str(row["transaction_id"]),
            ),
        )
        visible_rows = [
            row for row in raw_rows
            if _parse_datetime(str(row["timestamp"]), "transaction") <= cutoff
        ]

        incident_tx = next(
            (row for row in raw_rows if row["transaction_id"] == incident["reported_transaction_id"]),
            None,
        )
        if incident_tx is None:
            raise ReplayValidationError(
                f"Incident {incident['incident_id']} references a missing reported transaction."
            )
        if _parse_datetime(str(incident_tx["timestamp"]), "reported transaction") > cutoff:
            raise ReplayValidationError("Replay cutoff is earlier than the incident's reported transaction.")
        if _integer(incident, "reported_amount", str(incident["incident_id"])) != _integer(
            incident_tx, "amount", str(incident_tx["transaction_id"])
        ):
            raise ReplayValidationError("Incident reported amount does not match its referenced transaction.")

        events: list[TransactionEvent] = []
        cashouts: list[CashoutEvent] = []
        snapshots: list[ReplaySnapshot] = []
        for row in visible_rows:
            transaction_id = str(row["transaction_id"])
            timestamp = _parse_datetime(str(row["timestamp"]), "transaction")
            sender = str(row["sender_wallet"])
            receiver = str(row["receiver_wallet"])
            amount = _integer(row, "amount", transaction_id)
            if amount <= 0:
                raise ReplayValidationError(f"Transaction {transaction_id} amount must be positive.")
            if sender == receiver:
                raise ReplayValidationError(f"Transaction {transaction_id} sends to the same wallet.")
            if sender not in balances or receiver not in balances:
                missing = sender if sender not in balances else receiver
                raise ReplayValidationError(
                    f"Transaction {transaction_id} references wallet {missing!r} outside its scenario."
                )
            if row["agent_id"] and str(row["agent_id"]) not in balances:
                raise ReplayValidationError(
                    f"Transaction {transaction_id} references unknown agent {row['agent_id']!r}."
                )

            stored_sender_before = _integer(row, "sender_balance_before", transaction_id)
            stored_sender_after = _integer(row, "sender_balance_after", transaction_id)
            stored_receiver_before = _integer(row, "receiver_balance_before", transaction_id)
            stored_receiver_after = _integer(row, "receiver_balance_after", transaction_id)
            if balances[sender] != stored_sender_before:
                raise ReplayValidationError(
                    f"Transaction {transaction_id}: sender balance chain mismatch for {sender}; "
                    f"expected {balances[sender]}, record says {stored_sender_before}."
                )
            if balances[receiver] != stored_receiver_before:
                raise ReplayValidationError(
                    f"Transaction {transaction_id}: receiver balance chain mismatch for {receiver}; "
                    f"expected {balances[receiver]}, record says {stored_receiver_before}."
                )
            if amount > balances[sender]:
                raise ReplayValidationError(f"Transaction {transaction_id} overdraws wallet {sender}.")

            expected_sender_after = balances[sender] - amount
            expected_receiver_after = balances[receiver] + amount
            if (stored_sender_after, stored_receiver_after) != (expected_sender_after, expected_receiver_after):
                raise ReplayValidationError(
                    f"Transaction {transaction_id} recorded balances do not match its amount."
                )

            balances[sender] = expected_sender_after
            balances[receiver] = expected_receiver_after
            event = TransactionEvent(
                transaction_id=transaction_id,
                timestamp=timestamp,
                sender_wallet=sender,
                receiver_wallet=receiver,
                amount=amount,
                transaction_type=str(row["transaction_type"]),
                channel=str(row["channel"] or ""),
                agent_id=str(row["agent_id"]) if row["agent_id"] else None,
                scenario_id=scenario_id,
                sender_balance_before=stored_sender_before,
                sender_balance_after=stored_sender_after,
                receiver_balance_before=stored_receiver_before,
                receiver_balance_after=stored_receiver_after,
            )
            events.append(event)
            if event.transaction_type == "cashout":
                cashouts.append(CashoutEvent(
                    transaction_id=transaction_id,
                    timestamp=timestamp,
                    wallet_id=sender,
                    amount=amount,
                    agent_id=event.agent_id,
                    destination_wallet=receiver,
                ))
            snapshots.append(ReplaySnapshot(
                timestamp=timestamp,
                balances=balances.copy(),
                transaction_count=len(events),
                cashout_count=len(cashouts),
                cashout_total=sum(item.amount for item in cashouts),
            ))

        return ReplayResult(
            scenario_id=scenario_id,
            incident=incident,
            as_of=cutoff,
            initial_balances=initial_balances,
            final_balances=balances.copy(),
            wallet_types=wallet_types,
            transactions=tuple(events),
            cashouts=tuple(cashouts),
            snapshots=tuple(snapshots),
        )

    @staticmethod
    def _require_tables(db: sqlite3.Connection) -> None:
        required = {
            "transactions": {
                "transaction_id", "timestamp", "sender_wallet", "receiver_wallet", "amount",
                "transaction_type", "channel", "agent_id", "sender_balance_before",
                "sender_balance_after", "receiver_balance_before", "receiver_balance_after", "scenario_id",
            },
            "wallets": {"wallet_id", "baseline_balance", "customer_type", "scenario_id"},
            "incidents": {
                "incident_id", "reported_transaction_id", "reported_at", "analysis_at",
                "reported_amount", "scenario_id",
            },
        }
        existing = {
            str(row[0]) for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing_tables = set(required) - existing
        if missing_tables:
            raise ReplayValidationError(
                "FlowFreeze database is missing required tables: " + ", ".join(sorted(missing_tables))
            )
        for table, expected_columns in required.items():
            actual_columns = {
                str(row[1]) for row in db.execute(f'PRAGMA table_info("{table}")').fetchall()
            }
            missing_columns = expected_columns - actual_columns
            if missing_columns:
                raise ReplayValidationError(
                    f"FlowFreeze table {table!r} is missing columns: "
                    + ", ".join(sorted(missing_columns))
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay one synthetic FlowFreeze incident.")
    parser.add_argument("scenario_id", help="Scenario ID, such as SCN-06-FANOUT-CASHOUT")
    parser.add_argument("--at", dest="as_of", help="Optional timezone-aware ISO 8601 replay cutoff")
    parser.add_argument("--database", type=Path, help="SQLite database path; defaults to DATABASE_URL or data/flowfreeze.db")
    args = parser.parse_args()
    result = TransactionSimulator(args.database).replay(args.scenario_id, args.as_of)
    print(json.dumps({
        "scenario_id": result.scenario_id,
        "incident_id": result.incident["incident_id"],
        "as_of": result.as_of.isoformat(),
        "transaction_count": len(result.transactions),
        "cashout_count": len(result.cashouts),
        "cashout_total_bdt": sum(event.amount for event in result.cashouts),
        "digital_balances_bdt": result.digital_balances,
        "ledger_balances_bdt": result.final_balances,
    }, indent=2))


if __name__ == "__main__":
    main()
