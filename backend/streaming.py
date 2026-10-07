"""Incremental synthetic transaction stream for integration and scale testing.

This is a local adapter boundary for future MFS event feeds. It deliberately
accepts synthetic/de-identified event fields only and does not call a wallet,
ledger, or external provider.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
import json
import time
from typing import Any
from uuid import uuid4


def ensure_stream_tables(connection) -> None:
    """Create additive stream and case tables in the existing application DB."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS flow_transactions (
            transaction_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            sender_wallet TEXT NOT NULL,
            receiver_wallet TEXT NOT NULL,
            amount_bdt TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            channel TEXT NOT NULL,
            risk_score REAL NOT NULL,
            tainted_estimate_bdt TEXT NOT NULL,
            alerts_json TEXT NOT NULL,
            prediction_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_flow_tx_sender_time ON flow_transactions(sender_wallet, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_flow_tx_receiver_time ON flow_transactions(receiver_wallet, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_flow_tx_time ON flow_transactions(timestamp DESC);
        CREATE TABLE IF NOT EXISTS investigation_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL UNIQUE,
            transaction_id TEXT,
            risk_score REAL NOT NULL DEFAULT 0,
            investigator TEXT NOT NULL DEFAULT 'Unassigned',
            status TEXT NOT NULL DEFAULT 'new',
            title TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cases_status_created ON investigation_cases(status, created_at DESC);
        """
    )


def process_transaction(connection, transaction: dict[str, Any]) -> dict[str, Any]:
    """Score and persist one transaction, then return a graph-aware snapshot."""
    started_ns = time.perf_counter_ns()
    transaction_id = str(transaction.get("transaction_id") or f"SYN-{uuid4().hex[:16]}")
    event_time = transaction.get("timestamp") or datetime.now(timezone.utc)
    if isinstance(event_time, str):
        event_time = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
    if event_time.tzinfo is None:
        raise ValueError("timestamp must include a timezone offset.")
    event_time = event_time.astimezone(timezone.utc)
    timestamp = event_time.isoformat(timespec="microseconds")
    sender = str(transaction["sender_wallet"])
    receiver = str(transaction["receiver_wallet"])
    amount = Decimal(str(transaction.get("amount_bdt", transaction.get("amount")))).quantize(Decimal("0.01"))
    tx_type = str(transaction.get("transaction_type", "transfer"))
    channel = str(transaction.get("channel", "synthetic"))

    graph_started_ns = time.perf_counter_ns()
    recent_since = (event_time - timedelta(minutes=10)).isoformat(timespec="microseconds")
    rapid_since = (event_time - timedelta(minutes=5)).isoformat(timespec="microseconds")
    fanout = connection.execute(
        "SELECT COUNT(DISTINCT receiver_wallet) FROM flow_transactions "
        "WHERE sender_wallet = ? AND timestamp >= ?",
        (sender, rapid_since),
    ).fetchone()[0]
    prior_receipt = connection.execute(
        "SELECT 1 FROM flow_transactions WHERE receiver_wallet = ? AND timestamp <= ? "
        "AND timestamp >= ? LIMIT 1",
        (sender, timestamp, rapid_since),
    ).fetchone() is not None
    # Build a bounded local subgraph. Two indexed queries avoid a full ledger scan.
    related = connection.execute(
        "SELECT transaction_id, sender_wallet, receiver_wallet, timestamp, amount_bdt, transaction_type "
        "FROM flow_transactions WHERE sender_wallet IN (?, ?) AND timestamp >= ? "
        "ORDER BY timestamp DESC LIMIT 20",
        (sender, receiver, recent_since),
    ).fetchall()
    related += connection.execute(
        "SELECT transaction_id, sender_wallet, receiver_wallet, timestamp, amount_bdt, transaction_type "
        "FROM flow_transactions WHERE receiver_wallet IN (?, ?) AND timestamp >= ? "
        "ORDER BY timestamp DESC LIMIT 20",
        (sender, receiver, recent_since),
    ).fetchall()
    graph_edges: dict[str, dict[str, Any]] = {
        str(row[0]): {"transaction_id": str(row[0]), "from": str(row[1]), "to": str(row[2]),
                      "timestamp": str(row[3]), "amount_bdt": str(row[4]), "type": str(row[5])}
        for row in related
    }
    risk_context = {"recent_sender_fanout": int(fanout), "rapid_forward": prior_receipt}
    graph_ms = (time.perf_counter_ns() - graph_started_ns) / 1_000_000

    # Bounded, explainable synthetic heuristic; these values are not model
    # probabilities or a fraud finding and must be recalibrated for any pilot.
    risk = 0.06
    if amount >= Decimal("100000"):
        risk += 0.42
    elif amount >= Decimal("50000"):
        risk += 0.32
    elif amount >= Decimal("20000"):
        risk += 0.21
    elif amount >= Decimal("5000"):
        risk += 0.10
    risk += min(0.20, max(0, int(fanout) - 1) * 0.04)
    if prior_receipt:
        risk += 0.20
    if tx_type.lower() in {"cashout", "cash_out", "withdrawal"}:
        risk += 0.12
    risk = round(min(0.99, risk), 4)
    risk_band = "high" if risk >= 0.70 else "elevated" if risk >= 0.45 else "guarded" if risk >= 0.25 else "low"

    tainted_estimate = (amount * Decimal(str(risk))).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    alerts: list[dict[str, str]] = []
    if risk >= 0.70:
        alerts.append({"code": "HIGH_SYNTHETIC_RISK", "severity": "high", "message": "Synthetic risk heuristic crossed the high-risk threshold."})
    if int(fanout) >= 3:
        alerts.append({"code": "RECIPIENT_FANOUT", "severity": "medium", "message": "Sender has multiple recent recipients in the synthetic stream."})
    if prior_receipt:
        alerts.append({"code": "RAPID_FORWARD", "severity": "medium", "message": "Sender received funds shortly before this event."})
    if amount >= Decimal("50000"):
        alerts.append({"code": "LARGE_AMOUNT", "severity": "low", "message": "Synthetic amount exceeded the illustrative monitoring threshold."})

    p_cashout = min(0.75, 0.10 + risk * 0.48 + (0.10 if tx_type.lower() in {"cashout", "cash_out", "withdrawal"} else 0))
    p_forward = min(0.75, 0.50 - risk * 0.20)
    p_no_movement = max(0.05, 1.0 - p_cashout - p_forward)
    total = p_cashout + p_forward + p_no_movement
    prediction = {
        "synthetic": True,
        "method": "illustrative_risk_heuristic",
        "next_move_probabilities": {
            "forward": round(p_forward / total, 4),
            "cashout": round(p_cashout / total, 4),
            "no_movement": round(p_no_movement / total, 4),
        },
    }
    # Add the new edge to the bounded transaction graph response.
    graph_edges[transaction_id] = {"transaction_id": transaction_id, "from": sender, "to": receiver,
                                   "timestamp": timestamp, "amount_bdt": format(amount, "f"), "type": tx_type}
    nodes = sorted({item[key] for item in graph_edges.values() for key in ("from", "to")})
    graph = {"nodes": nodes, "edges": list(graph_edges.values()), "node_count": len(nodes),
             "edge_count": len(graph_edges), "window_minutes": 10, "truncated": len(graph_edges) >= 40}

    created_at = datetime.now(timezone.utc).isoformat()
    connection.execute(
        "INSERT INTO flow_transactions "
        "(transaction_id, timestamp, sender_wallet, receiver_wallet, amount_bdt, transaction_type, channel, "
        "risk_score, tainted_estimate_bdt, alerts_json, prediction_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (transaction_id, timestamp, sender, receiver, format(amount, "f"), tx_type, channel, risk,
         format(tainted_estimate, "f"), json.dumps(alerts), json.dumps(prediction), created_at),
    )
    processing_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
    analysis = {
        "synthetic": True,
        "risk_score": risk,
        "risk_band": risk_band,
        "taint": {"potentially_tainted_bdt_estimate": format(tainted_estimate, "f"),
                  "basis": "amount multiplied by illustrative synthetic risk score; not proportional ledger taint"},
        "alerts": alerts,
        "predictions": prediction,
        "features": risk_context,
        "limitations": "Synthetic heuristic only; not a trained or calibrated fraud model.",
    }
    return {
        "synthetic": True,
        "transaction": {"transaction_id": transaction_id, "timestamp": timestamp,
                        "sender_wallet": sender, "receiver_wallet": receiver,
                        "amount_bdt": format(amount, "f"), "transaction_type": tx_type,
                        "channel": channel},
        "analysis": analysis,
        "graph": graph,
        "processing_ms": round(processing_ms, 4),
        "graph_processing_ms": round(graph_ms, 4),
    }
