"""Features and adapters for the public transaction fraud model."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

REAL_FEATURE_COLUMNS = [
    "step", "type", "amount", "oldbalanceOrg", "newbalanceOrig",
    "oldbalanceDest", "newbalanceDest",
]
RAW_REQUIRED_COLUMNS = REAL_FEATURE_COLUMNS + ["isFraud"]
OPTIONAL_COLUMNS = ["isFlaggedFraud", "nameOrig", "nameDest"]


def load_real_transactions(path: str | Path, *, max_rows: int | None = None) -> pd.DataFrame:
    """Load a bounded, schema-checked transaction table.

    ``max_rows`` is an explicit MVP guard; training never needs to read more than
    the requested sample into memory. Identifier columns are ignored downstream.
    """
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Public transaction dataset not found: {source}")
    header = pd.read_csv(source, nrows=0)
    missing = set(RAW_REQUIRED_COLUMNS) - set(header.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
    usecols = [c for c in header.columns if c in set(RAW_REQUIRED_COLUMNS + OPTIONAL_COLUMNS)]
    frame = pd.read_csv(source, usecols=usecols, nrows=max_rows)
    frame = frame.dropna(subset=RAW_REQUIRED_COLUMNS).copy()
    frame["isFraud"] = frame["isFraud"].astype(int)
    if not frame["isFraud"].isin([0, 1]).all():
        raise ValueError("isFraud must contain only 0/1 labels")
    frame["type"] = frame["type"].astype(str)
    for column in ["step", "amount", "oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", "newbalanceDest"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    return frame.reset_index(drop=True)


def engineer_real_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Return only decision-time features; target and rule flags never enter X."""
    missing = set(REAL_FEATURE_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing model feature columns: {sorted(missing)}")
    result = frame[REAL_FEATURE_COLUMNS].copy()
    result["type"] = result["type"].astype(str)
    result = result.replace([float("inf"), float("-inf")], pd.NA)
    return result


def event_to_real_row(event: object, *, step: int) -> dict[str, object]:
    """Explicitly map a FlowFreeze TransactionEvent to the public schema."""
    transaction_type = str(getattr(event, "transaction_type", "transfer")).lower()
    type_mapping = {
        "cashout": "CASH_OUT", "transfer": "TRANSFER", "merchant_payment": "PAYMENT",
        "payment": "PAYMENT", "cash_in": "CASH_IN", "debit": "DEBIT",
    }
    return {
        "step": int(step),
        "type": type_mapping.get(transaction_type, "TRANSFER"),
        "amount": float(getattr(event, "amount")),
        "oldbalanceOrg": float(getattr(event, "sender_balance_before")),
        "newbalanceOrig": float(getattr(event, "sender_balance_after")),
        "oldbalanceDest": float(getattr(event, "receiver_balance_before")),
        "newbalanceDest": float(getattr(event, "receiver_balance_after")),
    }


def events_to_real_rows(events: Iterable[object]) -> pd.DataFrame:
    events = list(events)
    if not events:
        return pd.DataFrame(columns=REAL_FEATURE_COLUMNS)
    timestamps = [getattr(event, "timestamp") for event in events]
    start = min(timestamps)
    rows = [event_to_real_row(event, step=max(1, int((getattr(event, "timestamp") - start).total_seconds() // 3600) + 1)) for event in events]
    return pd.DataFrame(rows, columns=REAL_FEATURE_COLUMNS)
