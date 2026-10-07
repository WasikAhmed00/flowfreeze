from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.db import initialize_application_tables
from backend.main import app
from backend.streaming import process_transaction


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    database = tmp_path / "flowfreeze-test.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        "CREATE TABLE incidents (incident_id TEXT);"
        "CREATE TABLE transactions (transaction_id TEXT);"
        "CREATE TABLE wallets (wallet_id TEXT);"
    )
    connection.commit()
    connection.close()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    with TestClient(app) as client:
        yield client


def test_health_metrics_and_single_transaction_pipeline(api_client):
    health = api_client.get("/health")
    assert health.status_code == 200
    assert health.json()["database"] == "ok"

    response = api_client.post("/api/transactions", json={
        "transaction_id": "test-live-001", "timestamp": "2026-10-07T10:00:00Z",
        "sender_wallet": "wallet-a", "receiver_wallet": "wallet-b",
        "amount_bdt": "55000.00", "transaction_type": "transfer", "channel": "synthetic-test",
    })
    assert response.status_code == 201
    body = response.json()
    assert body["synthetic"] is True
    assert body["analysis"]["risk_score"] >= 0.30
    assert body["analysis"]["taint"]["potentially_tainted_bdt_estimate"]
    assert body["analysis"]["predictions"]["next_move_probabilities"]
    assert body["graph"]["edge_count"] == 1
    assert "LARGE_AMOUNT" in {alert["code"] for alert in body["analysis"]["alerts"]}
    duplicate = api_client.post("/api/transactions", json={
        "transaction_id": "test-live-001", "sender_wallet": "wallet-a",
        "receiver_wallet": "wallet-b", "amount_bdt": "15",
    })
    assert duplicate.status_code == 409

    metrics = api_client.get("/api/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["operational"]["stream_transactions_total"] == 1
    assert metrics.json()["operational"]["api"]["requests_total"] >= 3


def test_case_crud_and_linked_risk(api_client):
    ingested = api_client.post("/api/transactions", json={
        "transaction_id": "case-linked-tx", "sender_wallet": "sender", "receiver_wallet": "recipient",
        "amount": "90000", "transaction_type": "cashout",
    }).json()
    created = api_client.post("/api/cases", json={
        "transaction_id": "case-linked-tx", "title": "Synthetic cash-out review",
        "investigator": "A. Rahman",
    })
    assert created.status_code == 201
    case = created.json()
    assert case["risk_score"] == ingested["analysis"]["risk_score"]
    assert case["investigator"] == "A. Rahman"

    listed = api_client.get("/api/cases")
    assert listed.status_code == 200 and listed.json()["total"] == 1
    case_id = case["case_id"]
    assert api_client.get(f"/api/cases/{case_id}").json()["status"] == "new"
    updated = api_client.patch(f"/api/cases/{case_id}", json={
        "investigator": "N. Rahman", "status": "investigating", "notes": "Review graph evidence",
    })
    assert updated.status_code == 200
    assert updated.json()["status"] == "investigating"
    assert updated.json()["investigator"] == "N. Rahman"
    assert api_client.get("/api/cases?status=investigating").json()["total"] == 1
    assert api_client.patch(f"/api/cases/{case_id}", json={}).status_code == 422
    assert api_client.get("/api/cases/not-a-case").status_code == 404


def test_synthetic_live_simulator_updates_graph_risk_alerts_and_predictions(api_client):
    response = api_client.post("/api/transactions/simulate", json={"count": 6, "seed": 17})
    assert response.status_code == 200
    items = response.json()["transactions"]
    assert len(items) == 6
    assert all(item["analysis"]["predictions"]["synthetic"] for item in items)
    assert all(item["analysis"]["taint"]["potentially_tainted_bdt_estimate"] is not None for item in items)
    assert all(item["graph"]["edge_count"] >= 1 for item in items)
    assert api_client.get("/api/transactions?limit=10").json()["total"] == 6
    assert api_client.get("/api/metrics").json()["operational"]["stream_transactions_total"] == 6
    assert api_client.post("/api/transactions/simulate", json={"count": 21}).status_code == 422


def test_transaction_validation_rejects_unsafe_or_malformed_inputs(api_client):
    assert api_client.post("/api/transactions", json={
        "sender_wallet": "a", "receiver_wallet": "b", "amount_bdt": -1,
    }).status_code == 422
    assert api_client.post("/api/transactions", json={
        "sender_wallet": "a", "receiver_wallet": "b", "amount_bdt": 1,
        "timestamp": "2026-10-07T10:00:00",
    }).status_code == 422
    assert api_client.post("/api/transactions", json={
        "sender_wallet": "a", "receiver_wallet": "a", "amount_bdt": 1,
    }).status_code == 422


def test_stream_processor_handles_ten_thousand_wallet_network_events(tmp_path):
    database = tmp_path / "scale-10k.db"
    database.touch()
    initialize_application_tables(database)
    from backend.db import connect_database

    db = connect_database(database)
    origin = datetime(2026, 10, 7, tzinfo=timezone.utc)
    for index in range(10_000):
        sender = f"wallet-{index % 1000}"
        receiver = f"wallet-{(index * 17 + 1) % 1000}"
        if receiver == sender:
            receiver = f"wallet-{(index * 17 + 2) % 1000}"
        process_transaction(db, {
            "transaction_id": f"scale-{index}", "timestamp": origin + timedelta(seconds=index),
            "sender_wallet": sender, "receiver_wallet": receiver,
            "amount_bdt": (index % 80_000) + 1,
            "transaction_type": "transfer", "channel": "synthetic-scale-test",
        })
        db.commit()
    total = db.execute("SELECT COUNT(*) FROM flow_transactions").fetchone()[0]
    indexes = {row[1] for row in db.execute("PRAGMA index_list(flow_transactions)")}
    db.close()
    assert total == 10_000
    assert "idx_flow_tx_sender_time" in indexes
    assert "idx_flow_tx_receiver_time" in indexes
