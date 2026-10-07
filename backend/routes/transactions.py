"""Integration-ready synthetic transaction ingestion and stream simulation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import random
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status

from backend.db import application_connection
from backend.pipeline import analyze_live_transaction
from backend.schemas import SimulationRequest, TransactionCreate

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _ingest(payload: TransactionCreate) -> dict:
    try:
        with application_connection() as db:
            result = analyze_live_transaction(db, payload.model_dump(mode="python"))
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        if "UNIQUE constraint failed: flow_transactions.transaction_id" in str(exc):
            raise HTTPException(status_code=409, detail="transaction_id has already been ingested.") from exc
        raise


@router.post("", status_code=status.HTTP_201_CREATED)
def ingest_transaction(payload: TransactionCreate) -> dict:
    """Score and store one transaction. Scores and all data are synthetic/advisory."""
    return _ingest(payload)


@router.post("/simulate")
def simulate_live_transactions(request: SimulationRequest) -> dict:
    """Generate a small burst of synthetic MFS-like transactions via the same pipeline."""
    rng = random.Random(request.seed)
    wallets = [f"SYN-WALLET-{index:04d}" for index in range(1, 101)]
    now = datetime.now(timezone.utc)
    events = []
    try:
        with application_connection() as db:
            for index in range(request.count):
                sender = rng.choice(wallets[:12] if rng.random() < 0.45 else wallets)
                receiver = rng.choice([wallet for wallet in wallets if wallet != sender])
                amount = round(min(150000, max(80, rng.lognormvariate(7.8, 1.2))), 2)
                tx_type = "cashout" if rng.random() < 0.16 else "transfer"
                payload = {
                    "transaction_id": f"SIM-{uuid4().hex[:16]}",
                    "timestamp": now.replace(microsecond=min(999999, now.microsecond + index)),
                    "sender_wallet": sender,
                    "receiver_wallet": receiver,
                    "amount_bdt": amount,
                    "transaction_type": tx_type,
                    "channel": "synthetic_mfs_simulator",
                }
                events.append(analyze_live_transaction(db, payload))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Synthetic simulation failed: {exc}") from exc
    return {"synthetic": True, "count": len(events), "transactions": events,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "message": "Illustrative events only; no live MFS provider or wallet was contacted."}


@router.get("")
def list_stream_transactions(limit: int = Query(default=25, ge=1, le=200)) -> dict:
    with application_connection() as db:
        total = db.execute("SELECT COUNT(*) FROM flow_transactions").fetchone()[0]
        rows = db.execute(
            "SELECT transaction_id, timestamp, sender_wallet, receiver_wallet, amount_bdt, transaction_type, "
            "channel, risk_score, tainted_estimate_bdt, alerts_json, prediction_json "
            "FROM flow_transactions ORDER BY timestamp DESC, transaction_id DESC LIMIT ?", (limit,)
        ).fetchall()
    events = []
    for row in rows:
        item = dict(row)
        item["alerts"] = json.loads(item.pop("alerts_json"))
        item["predictions"] = json.loads(item.pop("prediction_json"))
        events.append(item)
    return {"synthetic": True, "total": total, "transactions": events}
