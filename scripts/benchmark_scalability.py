"""Reproducible synthetic transaction-stream benchmark for FlowFreeze.

Run: python scripts/benchmark_scalability.py
The workload exercises the same incremental service used by POST /api/transactions.
The API percentile sample is measured separately against the 100K-populated DB.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import platform
import statistics
import tempfile
import time

from backend.db import connect_database, initialize_application_tables
from backend.streaming import process_transaction

ROOT = Path(__file__).resolve().parents[1]
SCALES = (1_000, 10_000, 50_000, 100_000)


def event(index: int, wallets: int = 10_000) -> dict:
    sender = (index * 7919 + 17) % wallets
    receiver = (index * 1543 + 101) % wallets
    if sender == receiver:
        receiver = (receiver + 1) % wallets
    return {
        "transaction_id": f"BENCH-{index:06d}",
        "timestamp": datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(seconds=index),
        "sender_wallet": f"wallet-{sender:05d}",
        "receiver_wallet": f"wallet-{receiver:05d}",
        "amount_bdt": float((index * 97) % 120_000 + 50),
        "transaction_type": "cashout" if index % 11 == 0 else "transfer",
        "channel": "synthetic_benchmark",
    }


def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    position = (len(values) - 1) * p
    lo, hi = int(position), min(int(position) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def main() -> None:
    results = []
    with tempfile.TemporaryDirectory(prefix="flowfreeze-scale-") as folder:
        database_path = Path(folder) / "benchmark.db"
        database_path.touch()
        initialize_application_tables(database_path)
        db = connect_database(database_path)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        started = time.perf_counter()
        pipeline_ms = 0.0
        graph_ms = 0.0
        count = 0
        checkpoints = set(SCALES)
        for index in range(SCALES[-1]):
            result = process_transaction(db, event(index))
            db.commit()  # model one durable transaction-ingestion operation
            count += 1
            pipeline_ms += result["processing_ms"]
            graph_ms += result["graph_processing_ms"]
            if count in checkpoints:
                elapsed = time.perf_counter() - started
                results.append({
                    "transactions": count,
                    "wallets_in_input_domain": 10_000,
                    "elapsed_seconds": round(elapsed, 4),
                    "processing_ms_sum": round(pipeline_ms, 3),
                    "graph_processing_ms_sum": round(graph_ms, 3),
                    "throughput_transactions_per_second": round(count / elapsed, 2),
                    "mean_processing_ms": round(pipeline_ms / count, 4),
                    "mean_graph_processing_ms": round(graph_ms / count, 4),
                })
                print(f"processed {count:,} events in {elapsed:.2f}s", flush=True)
        db.close()

        os.environ["DATABASE_URL"] = f"sqlite:///{database_path}"
        from fastapi.testclient import TestClient
        from backend.main import app

        api_latencies = []
        with TestClient(app) as client:
            health = client.get("/health")
            if health.status_code != 200 or health.json().get("database") != "ok":
                raise RuntimeError(f"Health check failed during benchmark: {health.text}")
            for index in range(40):
                payload = event(SCALES[-1] + index)
                payload["transaction_id"] = f"API-BENCH-{index:04d}"
                started_api = time.perf_counter()
                response = client.post("/api/transactions", json={**payload, "timestamp": payload["timestamp"].isoformat()})
                api_latencies.append((time.perf_counter() - started_api) * 1000)
                if response.status_code != 201:
                    raise RuntimeError(f"API benchmark request failed ({response.status_code}): {response.text}")
        api_results = {
            "sample_count": len(api_latencies),
            "mean_ms": round(statistics.mean(api_latencies), 3),
            "p50_ms": round(percentile(api_latencies, 0.50), 3),
            "p95_ms": round(percentile(api_latencies, 0.95), 3),
            "max_ms": round(max(api_latencies), 3),
            "measurement": "FastAPI TestClient POST /api/transactions with a 100K-row stream already persisted; includes validation, indexed graph context, scoring, SQLite write and response serialization.",
        }
        report = {
            "benchmark": "FlowFreeze synthetic transaction stream",
            "date_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "logical_cpus": os.cpu_count(),
            "database": "SQLite, WAL, synchronous=NORMAL; one durable commit per transaction",
            "wallet_domain": 10_000,
            "synthetic_only": True,
            "limitations": [
                "Single-process local benchmark; not a production MFS load test or a multi-worker deployment test.",
                "Risk/taint/prediction are illustrative synthetic heuristics, not calibrated model evaluation.",
                "The local graph work is bounded to indexed neighborhood lookups and a 10-minute response subgraph; it is not full-history path enumeration.",
                "API percentiles are a 40-request local in-process sample, not a concurrent network/load test.",
            ],
            "scales": results,
            "api_response": api_results,
        }
        output = ROOT / "docs" / "scalability_benchmark.json"
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        print(f"\nSaved {output}")


if __name__ == "__main__":
    main()
