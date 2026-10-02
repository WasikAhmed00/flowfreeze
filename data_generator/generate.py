"""Generate reproducible synthetic FlowFreeze CSV data and a SQLite database."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import DEFAULT_BASE_TIME, DEFAULT_DATA_DIR, DEFAULT_RANDOM_SEED, NEXT_MOVE_WINDOW_MINUTES, SPLIT_BY_SCENARIO_FAMILY
from .scenarios import SCENARIOS

TRANSACTION_FIELDS = [
    "transaction_id", "timestamp", "sender_wallet", "receiver_wallet", "amount",
    "transaction_type", "channel", "agent_id", "location", "sender_balance_before",
    "sender_balance_after", "receiver_balance_before", "receiver_balance_after", "scenario_id",
]
WALLET_FIELDS = [
    "wallet_id", "account_age", "customer_type", "baseline_balance",
    "average_transaction_amount", "transaction_frequency", "normal_active_hours",
    "usual_transaction_types", "scenario_id",
]
INCIDENT_FIELDS = [
    "incident_id", "reported_transaction_id", "reported_at", "analysis_at",
    "reported_amount", "incident_type", "status", "scenario_id",
]
GROUND_TRUTH_FIELDS = [
    "scenario_id", "scenario_type", "split", "wallet_id", "fraud_flag",
    "fraud_source_wallet", "tainted_amount", "hop_number", "cashout_flag",
    "expected_next_action",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _timestamp(base: datetime, minutes: float) -> datetime:
    return base + timedelta(minutes=minutes)


def _find_hops(wallets: list[str], edges: list[tuple[str, str]], start: str) -> dict[str, int]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for sender, receiver in edges:
        adjacency[sender].append(receiver)
    hops = {start: 0}
    pending = deque([start])
    while pending:
        current = pending.popleft()
        for receiver in adjacency[current]:
            if receiver not in hops:
                hops[receiver] = hops[current] + 1
                pending.append(receiver)
    return {wallet: hops.get(wallet, -1) for wallet in wallets}


def generate_dataset(out_dir: Path = DEFAULT_DATA_DIR, seed: int = DEFAULT_RANDOM_SEED) -> dict[str, int]:
    """Generate the eight canonical scenarios into CSV files and flowfreeze.db."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_time = datetime.fromisoformat(DEFAULT_BASE_TIME).astimezone(timezone.utc)

    transactions: list[dict[str, Any]] = []
    wallets: list[dict[str, Any]] = []
    incidents: list[dict[str, Any]] = []
    ground_truth: list[dict[str, Any]] = []
    all_wallets: dict[str, dict[str, Any]] = {}

    for scenario in SCENARIOS:
        scenario_id = scenario["scenario_id"]
        family = scenario["scenario_type"]
        start = base_time + timedelta(days=len(incidents))
        analysis_at = _timestamp(start, 4)
        report_at = _timestamp(start, 1)
        roles = scenario["wallets"]
        role_ids = {role: f"{scenario_id}-{role}" for role in roles}
        balances = {role_ids[role]: int(profile[1]) for role, profile in roles.items()}
        initial_balances = balances.copy()

        for role, (customer_type, baseline_balance) in roles.items():
            wallet_id = role_ids[role]
            # Profiles are deliberately synthetic and differ between scenarios.
            all_wallets[wallet_id] = {
                "wallet_id": wallet_id,
                "account_age": rng.randint(20, 1600),
                "customer_type": customer_type,
                "baseline_balance": int(baseline_balance),
                "average_transaction_amount": round(rng.uniform(700, 9500), 2),
                "transaction_frequency": round(rng.uniform(0.1, 5.0), 3),
                "normal_active_hours": rng.choice(["08:00-18:00", "09:00-21:00", "17:00-23:00"]),
                "usual_transaction_types": "transfer,merchant_payment" if customer_type != "agent" else "cashin,cashout",
                "scenario_id": scenario_id,
            }

        event_rows: list[dict[str, Any]] = []
        sorted_events = sorted(scenario["events"], key=lambda item: item[0])
        for event_number, (minute, sender_role, receiver_role, amount, transaction_type) in enumerate(sorted_events, start=1):
            sender = role_ids[sender_role]
            receiver = role_ids[receiver_role]
            amount = int(amount)
            if balances[sender] < amount:
                raise ValueError(f"Insufficient generated balance in {sender} for {scenario_id}")
            sender_before = balances[sender]
            receiver_before = balances[receiver]
            balances[sender] -= amount
            balances[receiver] += amount
            tx = {
                "transaction_id": f"{scenario_id}-TX{event_number:03d}",
                "timestamp": _timestamp(start, minute).isoformat(),
                "sender_wallet": sender,
                "receiver_wallet": receiver,
                "amount": amount,
                "transaction_type": transaction_type,
                "channel": "app" if transaction_type != "cashout" else "agent",
                "agent_id": role_ids.get("AGENT1", "") if transaction_type == "cashout" else "",
                "location": rng.choice(["ZONE-A", "ZONE-B", "ZONE-C", "ZONE-D"]),
                "sender_balance_before": sender_before,
                "sender_balance_after": balances[sender],
                "receiver_balance_before": receiver_before,
                "receiver_balance_after": balances[receiver],
                "scenario_id": scenario_id,
            }
            event_rows.append(tx)

        transactions.extend(event_rows)
        initial_tx = event_rows[0]
        incidents.append({
            "incident_id": f"INC-{scenario_id}",
            "reported_transaction_id": initial_tx["transaction_id"],
            "reported_at": report_at.isoformat(),
            "analysis_at": analysis_at.isoformat(),
            "reported_amount": initial_tx["amount"],
            "incident_type": scenario["incident_type"],
            "status": "new",
            "scenario_id": scenario_id,
        })

        # For ground truth, use events visible by analysis time for taint/hops,
        # and the following five minutes for the next-movement target.
        visible = [row for row in event_rows if datetime.fromisoformat(row["timestamp"]) <= analysis_at]
        visible_edges = [(row["sender_wallet"], row["receiver_wallet"]) for row in visible]
        root = role_ids["W1"]
        hops = _find_hops(list(balances), visible_edges, root)
        tainted = {wallet: 0.0 for wallet in balances}
        tainted[root] = float(initial_tx["amount"])
        running_balance = initial_balances.copy()
        initial_tainted = {wallet: 0.0 for wallet in balances}
        initial_tainted[root] = float(initial_tx["amount"])
        # Replay visible events; the reported transaction seeds taint, later
        # outgoing amounts consume taint in proportion to the sender balance.
        for tx in visible:
            sender, receiver = tx["sender_wallet"], tx["receiver_wallet"]
            amount = float(tx["amount"])
            if tx["transaction_id"] == initial_tx["transaction_id"]:
                running_balance[sender] -= amount
                running_balance[receiver] += amount
                continue
            balance_before = running_balance[sender]
            ratio = min(1.0, initial_tainted[sender] / balance_before) if balance_before > 0 else 0.0
            moved_taint = min(initial_tainted[sender], amount * ratio)
            initial_tainted[sender] -= moved_taint
            initial_tainted[receiver] += moved_taint
            running_balance[sender] -= amount
            running_balance[receiver] += amount

        future_end = analysis_at + timedelta(minutes=NEXT_MOVE_WINDOW_MINUTES)
        future = [row for row in event_rows if analysis_at < datetime.fromisoformat(row["timestamp"]) <= future_end]
        for wallet_id in balances:
            outgoing = [row for row in future if row["sender_wallet"] == wallet_id]
            if not outgoing:
                next_action = "no_movement"
            elif outgoing[0]["transaction_type"] == "cashout":
                next_action = "cashout"
            else:
                next_action = "forward"
            has_cashout = any(row["transaction_type"] == "cashout" and row["sender_wallet"] == wallet_id for row in event_rows)
            ground_truth.append({
                "scenario_id": scenario_id,
                "scenario_type": family,
                "split": SPLIT_BY_SCENARIO_FAMILY[family],
                "wallet_id": wallet_id,
                "fraud_flag": int(bool(scenario["fraud"] and hops.get(wallet_id, -1) >= 0)),
                "fraud_source_wallet": root,
                "tainted_amount": round(initial_tainted[wallet_id], 2),
                "hop_number": hops.get(wallet_id, -1),
                "cashout_flag": int(has_cashout),
                "expected_next_action": next_action,
            })

    wallets = list(all_wallets.values())
    _write_csv(out_dir / "transactions.csv", TRANSACTION_FIELDS, transactions)
    _write_csv(out_dir / "wallets.csv", WALLET_FIELDS, wallets)
    _write_csv(out_dir / "incidents.csv", INCIDENT_FIELDS, incidents)
    _write_csv(out_dir / "ground_truth.csv", GROUND_TRUTH_FIELDS, ground_truth)
    metadata = {
        "synthetic": True,
        "seed": seed,
        "scenario_count": len(SCENARIOS),
        "next_move_window_minutes": NEXT_MOVE_WINDOW_MINUTES,
        "warning": "Generated demo data only; not upay production data or customer behavior.",
    }
    (out_dir / "generation_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    _write_database(out_dir / "flowfreeze.db", transactions, wallets, incidents, ground_truth)
    return {"transactions": len(transactions), "wallets": len(wallets), "incidents": len(incidents), "ground_truth_rows": len(ground_truth)}


def _write_database(path: Path, transactions: list[dict[str, Any]], wallets: list[dict[str, Any]], incidents: list[dict[str, Any]], ground_truth: list[dict[str, Any]]) -> None:
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as connection:
        for table, rows in (("transactions", transactions), ("wallets", wallets), ("incidents", incidents), ("ground_truth", ground_truth)):
            if not rows:
                continue
            columns = list(rows[0])
            definitions = ", ".join(f'"{column}" {_sqlite_type(rows[0][column])}' for column in columns)
            quoted_columns = ", ".join(f'"{column}"' for column in columns)
            placeholders = ", ".join("?" for _ in columns)
            connection.execute(f'CREATE TABLE "{table}" ({definitions})')
            connection.executemany(
                f'INSERT INTO "{table}" ({quoted_columns}) VALUES ({placeholders})',
                [[str(row[column]) for column in columns] for row in rows],
            )
            connection.execute(f'CREATE INDEX "idx_{table}_scenario" ON "{table}" ("scenario_id")')
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.executemany(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            [("synthetic", "true"), ("generator", "data_generator/generate.py")],
        )


def _sqlite_type(value: Any) -> str:
    if isinstance(value, bool) or isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    args = parser.parse_args()
    counts = generate_dataset(args.out_dir, args.seed)
    print(f"Generated synthetic dataset (seed={args.seed}) at {args.out_dir.resolve()}: {counts}")


if __name__ == "__main__":
    main()
