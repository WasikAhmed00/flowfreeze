"""Generate reproducible, varied synthetic FlowFreeze incident cases."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any

from .config import (
    DEFAULT_BASE_TIME,
    DEFAULT_CASES_PER_SCENARIO,
    DEFAULT_DATA_DIR,
    DEFAULT_RANDOM_SEED,
    NEXT_MOVE_WINDOW_MINUTES,
    SPLIT_RATIOS,
)
from .scenarios import SCENARIOS

CENT = Decimal("0.01")
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
    "reported_amount", "incident_type", "scenario_type", "status", "scenario_id",
]
GROUND_TRUTH_FIELDS = [
    "scenario_id", "scenario_type", "split", "wallet_id", "fraud_flag",
    "fraud_source_wallet", "tainted_amount", "hop_number", "cashout_flag",
    "expected_next_action",
]
NORMAL_ROLES = {
    "NORMAL_A": ("individual", 25000),
    "NORMAL_B": ("merchant", 45000),
    "NORMAL_C": ("individual", 18000),
}
NORMAL_EVENTS = [
    (-30 * 24 * 60, "NORMAL_A", "NORMAL_B", 1800, "transfer"),
    (-20 * 24 * 60, "NORMAL_B", "NORMAL_C", 900, "merchant_payment"),
    (-10 * 24 * 60, "NORMAL_C", "NORMAL_A", 650, "transfer"),
    (-5 * 24 * 60, "NORMAL_A", "NORMAL_C", 1000, "transfer"),
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _timestamp(base: datetime, minutes: float) -> datetime:
    return base + timedelta(minutes=minutes)


def _scaled(value: int, factor: float) -> int:
    return max(0, int(round(value * factor)))


def _build_cases(cases_per_scenario: int, seed: int) -> list[dict[str, Any]]:
    if cases_per_scenario < 3:
        raise ValueError("cases_per_scenario must be at least 3 to populate all data splits.")

    variation_rng = random.Random(seed)
    split_rng = random.Random(seed ^ 0x5F3759DF)
    cases: list[dict[str, Any]] = []

    for template in SCENARIOS:
        family_cases: list[dict[str, Any]] = []
        for variant in range(1, cases_per_scenario + 1):
            amount_scale = variation_rng.uniform(0.75, 1.25)
            time_scale = variation_rng.uniform(0.90, 1.10)
            case = {
                "scenario_id": f"{template['scenario_id']}-{variant:04d}",
                "scenario_type": template["scenario_type"],
                "fraud": template["fraud"],
                "incident_type": template["incident_type"],
                "source": template["source"],
                "amount_scale": amount_scale,
                "time_scale": time_scale,
                "wallets": {
                    role: (customer_type, _scaled(balance, amount_scale * variation_rng.uniform(0.80, 1.20)))
                    for role, (customer_type, balance) in template["wallets"].items()
                },
                "events": [
                    (
                        minute * time_scale,
                        sender,
                        receiver,
                        max(1, _scaled(amount, amount_scale)),
                        transaction_type,
                    )
                    for minute, sender, receiver, amount, transaction_type in template["events"]
                ],
            }
            family_cases.append(case)

        shuffled = list(range(cases_per_scenario))
        split_rng.shuffle(shuffled)
        train_count = max(1, int(cases_per_scenario * SPLIT_RATIOS["train"]))
        validation_count = max(1, int(cases_per_scenario * SPLIT_RATIOS["validation"]))
        if train_count + validation_count >= cases_per_scenario:
            train_count = cases_per_scenario - 2
            validation_count = 1
        for position, case_index in enumerate(shuffled):
            if position < train_count:
                split = "train"
            elif position < train_count + validation_count:
                split = "validation"
            else:
                split = "test"
            family_cases[case_index]["split"] = split
        cases.extend(family_cases)

    return cases


def _find_hops(wallet_ids: list[str], edges: list[tuple[str, str]], start: str) -> dict[str, int]:
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
    return {wallet: hops.get(wallet, -1) for wallet in wallet_ids}


def _ground_truth_taint(
    visible_events: list[dict[str, Any]],
    initial_balances: dict[str, int],
    wallet_types: dict[str, str],
    reported_transaction_id: str,
    reported_amount: int,
) -> dict[str, Decimal]:
    balances = {wallet: Decimal(amount) for wallet, amount in initial_balances.items()}
    tainted = {wallet: Decimal("0") for wallet in initial_balances}
    seeded = False
    for event in visible_events:
        sender, receiver = event["sender_wallet"], event["receiver_wallet"]
        amount = Decimal(event["amount"])
        if event["transaction_id"] == reported_transaction_id:
            balances[sender] -= amount
            balances[receiver] += amount
            tainted[receiver] += Decimal(reported_amount)
            seeded = True
            continue
        if not seeded:
            balances[sender] -= amount
            balances[receiver] += amount
            continue

        sender_balance = balances[sender]
        proportion = min(Decimal(1), tainted[sender] / sender_balance) if sender_balance > 0 else Decimal(0)
        moved = min(tainted[sender], (amount * proportion).quantize(CENT, rounding=ROUND_DOWN))
        tainted[sender] -= moved
        is_cashout = (
            event["transaction_type"] == "cashout"
            or wallet_types.get(receiver) == "cash_destination"
        )
        if not is_cashout:
            tainted[receiver] += moved
        balances[sender] -= amount
        balances[receiver] += amount

    return {wallet: amount.quantize(CENT, rounding=ROUND_DOWN) for wallet, amount in tainted.items()}


def generate_dataset(
    out_dir: Path = DEFAULT_DATA_DIR,
    seed: int = DEFAULT_RANDOM_SEED,
    cases_per_scenario: int = DEFAULT_CASES_PER_SCENARIO,
) -> dict[str, Any]:
    """Generate varied cases, benign history, labels/splits, CSVs, and SQLite."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_time = datetime.fromisoformat(DEFAULT_BASE_TIME).astimezone(timezone.utc)

    transactions: list[dict[str, Any]] = []
    wallets: list[dict[str, Any]] = []
    incidents: list[dict[str, Any]] = []
    ground_truth: list[dict[str, Any]] = []
    all_wallets: dict[str, dict[str, Any]] = {}
    cases = _build_cases(cases_per_scenario, seed)
    split_counts = {split: 0 for split in SPLIT_RATIOS}

    for case_number, scenario in enumerate(cases):
        scenario_id = scenario["scenario_id"]
        family = scenario["scenario_type"]
        split = scenario["split"]
        split_counts[split] += 1
        start = base_time + timedelta(minutes=case_number * 15)
        analysis_at = _timestamp(start, 4)
        report_at = _timestamp(start, 1)
        profile_roles = dict(scenario["wallets"])
        for role, (customer_type, balance) in NORMAL_ROLES.items():
            profile_roles[role] = (customer_type, _scaled(balance, scenario["amount_scale"]))
        role_ids = {role: f"{scenario_id}-{role}" for role in profile_roles}
        balances = {role_ids[role]: int(profile[1]) for role, profile in profile_roles.items()}
        initial_balances = balances.copy()
        wallet_types: dict[str, str] = {}

        for role, (customer_type, baseline_balance) in profile_roles.items():
            wallet_id = role_ids[role]
            wallet_types[wallet_id] = customer_type
            all_wallets[wallet_id] = {
                "wallet_id": wallet_id,
                "account_age": rng.randint(20, 2000),
                "customer_type": customer_type,
                "baseline_balance": int(baseline_balance),
                "average_transaction_amount": round(rng.uniform(500, 12000), 2),
                "transaction_frequency": round(rng.uniform(0.05, 5.0), 3),
                "normal_active_hours": rng.choice(["08:00-18:00", "09:00-21:00", "17:00-23:00"]),
                "usual_transaction_types": "transfer,merchant_payment" if customer_type != "agent" else "cashin,cashout",
                "scenario_id": scenario_id,
            }

        event_specs: list[dict[str, Any]] = []
        for normal_order, (minute, sender_role, receiver_role, amount, transaction_type) in enumerate(NORMAL_EVENTS):
            event_specs.append({
                "minute": minute,
                "order": normal_order,
                "sender_role": sender_role,
                "receiver_role": receiver_role,
                "amount": max(1, _scaled(amount, scenario["amount_scale"])),
                "transaction_type": transaction_type,
                "reported": False,
            })
        for event_index, (minute, sender_role, receiver_role, amount, transaction_type) in enumerate(scenario["events"]):
            event_specs.append({
                "minute": minute,
                "order": len(NORMAL_EVENTS) + event_index,
                "sender_role": sender_role,
                "receiver_role": receiver_role,
                "amount": amount,
                "transaction_type": transaction_type,
                "reported": event_index == 0,
            })
        event_specs.sort(key=lambda event: (event["minute"], event["order"]))

        event_rows: list[dict[str, Any]] = []
        reported_transaction_id = ""
        for event_number, event_spec in enumerate(event_specs, start=1):
            sender = role_ids[event_spec["sender_role"]]
            receiver = role_ids[event_spec["receiver_role"]]
            amount = int(event_spec["amount"])
            if balances[sender] < amount:
                raise ValueError(f"Insufficient generated balance in {sender} for {scenario_id}")
            sender_before = balances[sender]
            receiver_before = balances[receiver]
            balances[sender] -= amount
            balances[receiver] += amount
            transaction_id = f"{scenario_id}-TX{event_number:03d}"
            # Incident-relative events were time-scaled when this case was
            # instantiated. Benign history remains in the preceding month.
            timestamp_minutes = event_spec["minute"]
            tx = {
                "transaction_id": transaction_id,
                "timestamp": _timestamp(start, timestamp_minutes).isoformat(),
                "sender_wallet": sender,
                "receiver_wallet": receiver,
                "amount": amount,
                "transaction_type": event_spec["transaction_type"],
                "channel": "app" if event_spec["transaction_type"] != "cashout" else "agent",
                "agent_id": role_ids.get("AGENT1", "") if event_spec["transaction_type"] == "cashout" else "",
                "location": rng.choice(["ZONE-A", "ZONE-B", "ZONE-C", "ZONE-D"]),
                "sender_balance_before": sender_before,
                "sender_balance_after": balances[sender],
                "receiver_balance_before": receiver_before,
                "receiver_balance_after": balances[receiver],
                "scenario_id": scenario_id,
            }
            event_rows.append(tx)
            if event_spec["reported"]:
                reported_transaction_id = transaction_id

        normal_history_start = start - timedelta(days=30)
        for role in NORMAL_ROLES:
            wallet_id = role_ids[role]
            normal_history = [
                row for row in event_rows
                if row["sender_wallet"] == wallet_id
                and normal_history_start <= datetime.fromisoformat(row["timestamp"]) < report_at
            ]
            if normal_history:
                profile = all_wallets[wallet_id]
                profile["average_transaction_amount"] = round(
                    sum(int(row["amount"]) for row in normal_history) / len(normal_history), 2
                )
                profile["transaction_frequency"] = round(len(normal_history) / 30.0, 3)
                profile["normal_active_hours"] = "08:00-18:00"

        if not reported_transaction_id:
            raise ValueError(f"Scenario {scenario_id} has no reported transaction marker.")
        initial_tx = next(row for row in event_rows if row["transaction_id"] == reported_transaction_id)
        transactions.extend(event_rows)

        incidents.append({
            "incident_id": f"INC-{scenario_id}",
            "reported_transaction_id": reported_transaction_id,
            "reported_at": report_at.isoformat(),
            "analysis_at": analysis_at.isoformat(),
            "reported_amount": initial_tx["amount"],
            "incident_type": scenario["incident_type"],
            "scenario_type": family,
            "status": "new",
            "scenario_id": scenario_id,
        })

        visible = [row for row in event_rows if datetime.fromisoformat(row["timestamp"]) <= analysis_at]
        visible_edges = [(row["sender_wallet"], row["receiver_wallet"]) for row in visible]
        root = role_ids[scenario["source"]]
        hops = _find_hops(list(balances), visible_edges, root)
        tainted = _ground_truth_taint(
            visible,
            initial_balances,
            wallet_types,
            reported_transaction_id,
            int(initial_tx["amount"]),
        )

        future_end = analysis_at + timedelta(minutes=NEXT_MOVE_WINDOW_MINUTES)
        future = [row for row in event_rows if analysis_at < datetime.fromisoformat(row["timestamp"]) <= future_end]
        for wallet_id, customer_type in wallet_types.items():
            if customer_type == "cash_destination":
                continue
            outgoing = [row for row in future if row["sender_wallet"] == wallet_id]
            if not outgoing:
                next_action = "no_movement"
            elif outgoing[0]["transaction_type"] == "cashout":
                next_action = "cashout"
            else:
                next_action = "forward"
            has_cashout = any(
                row["transaction_type"] == "cashout" and row["sender_wallet"] == wallet_id
                for row in event_rows
            )
            ground_truth.append({
                "scenario_id": scenario_id,
                "scenario_type": family,
                "split": split,
                "wallet_id": wallet_id,
                "fraud_flag": int(bool(scenario["fraud"] and hops.get(wallet_id, -1) >= 0)),
                "fraud_source_wallet": root,
                "tainted_amount": float(tainted[wallet_id]),
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
        "scenario_family_count": len(SCENARIOS),
        "cases_per_scenario_family": cases_per_scenario,
        "case_count": len(cases),
        "split_case_counts": split_counts,
        "split_unit": "scenario_id (all wallet and transaction rows for a case stay together)",
        "split_ratios": SPLIT_RATIOS,
        "next_move_window_minutes": NEXT_MOVE_WINDOW_MINUTES,
        "warning": "Generated demo/training data only; not upay production data or customer behavior.",
    }
    (out_dir / "generation_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    _write_database(out_dir / "flowfreeze.db", transactions, wallets, incidents, ground_truth)
    return {
        "transactions": len(transactions),
        "wallets": len(wallets),
        "incidents": len(incidents),
        "ground_truth_rows": len(ground_truth),
        "split_case_counts": split_counts,
    }


def _write_database(
    path: Path,
    transactions: list[dict[str, Any]],
    wallets: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
) -> None:
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
                [[row[column] for column in columns] for row in rows],
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
    parser.add_argument("--cases-per-scenario", type=int, default=DEFAULT_CASES_PER_SCENARIO)
    args = parser.parse_args()
    counts = generate_dataset(args.out_dir, args.seed, args.cases_per_scenario)
    print(f"Generated synthetic dataset (seed={args.seed}) at {args.out_dir.resolve()}: {counts}")


if __name__ == "__main__":
    main()
