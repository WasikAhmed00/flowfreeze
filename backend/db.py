"""SQLite connection helpers for the local FlowFreeze MVP."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "flowfreeze.db"


def resolve_database_path(path: str | Path | None = None) -> Path:
    """Resolve a path or the supported SQLite DATABASE_URL to an absolute path."""
    if path is None:
        value = os.environ.get("DATABASE_URL", "")
        if value.startswith("sqlite:///"):
            value = value[len("sqlite:///") :]
        elif value:
            raise ValueError("Only SQLite DATABASE_URL values are supported by this MVP.")
        else:
            value = str(DEFAULT_DATABASE_PATH)
        path = value

    result = Path(path)
    if not result.is_absolute():
        result = PROJECT_ROOT / result
    return result.resolve()


def connect_database(path: str | Path | None = None) -> sqlite3.Connection:
    """Open the generated database, with row access by column name."""
    database_path = resolve_database_path(path)
    if not database_path.is_file():
        raise FileNotFoundError(
            f"FlowFreeze database not found at {database_path}. "
            "Generate it with: python -m data_generator.generate --seed 42"
        )
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_application_tables(path: str | Path | None = None) -> None:
    """Create application tables in the local synthetic demo DB."""
    connection = connect_database(path)
    try:
        _ensure_auth_tables(connection)
        _ensure_audit_tables(connection)
        from backend.streaming import ensure_stream_tables

        ensure_stream_tables(connection)
    finally:
        connection.close()


@contextmanager
def application_connection(path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection after making sure local audit tables exist."""
    connection = connect_database(path)
    try:
        _ensure_audit_tables(connection)
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _ensure_audit_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS analyst_decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            scenario_id TEXT NOT NULL,
            wallet_id TEXT NOT NULL,
            decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject', 'modify')),
            proposed_amount_bdt TEXT NOT NULL,
            reason TEXT NOT NULL,
            actor TEXT NOT NULL,
            created_at TEXT NOT NULL,
            synthetic INTEGER NOT NULL DEFAULT 1 CHECK (synthetic = 1)
        );
        CREATE INDEX IF NOT EXISTS idx_decisions_scenario
            ON analyst_decisions (scenario_id, decision_id);
        CREATE TABLE IF NOT EXISTS case_audit_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            actor TEXT NOT NULL,
            role TEXT NOT NULL,
            action TEXT NOT NULL,
            result TEXT NOT NULL,
            synthetic INTEGER NOT NULL DEFAULT 1 CHECK (synthetic = 1)
        );
        CREATE INDEX IF NOT EXISTS idx_case_audit_scenario
            ON case_audit_events (scenario_id, event_id);
        CREATE TABLE IF NOT EXISTS simulated_outcomes (
            simulation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id INTEGER NOT NULL UNIQUE REFERENCES analyst_decisions(decision_id),
            scenario_id TEXT NOT NULL,
            wallet_id TEXT NOT NULL,
            simulated_amount_bdt TEXT NOT NULL,
            estimated_tainted_preserved_bdt TEXT NOT NULL,
            estimated_legitimate_affected_bdt TEXT NOT NULL,
            created_at TEXT NOT NULL,
            synthetic INTEGER NOT NULL DEFAULT 1 CHECK (synthetic = 1)
        );
        CREATE TABLE IF NOT EXISTS analyst_feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id INTEGER NOT NULL UNIQUE REFERENCES analyst_decisions(decision_id),
            was_useful TEXT NOT NULL CHECK (was_useful IN ('yes', 'partially', 'no')),
            recommendation_feedback TEXT NOT NULL CHECK (recommendation_feedback IN ('helpful', 'not_helpful')),
            trace_accuracy TEXT NOT NULL CHECK (trace_accuracy IN ('accurate', 'partially_accurate', 'inaccurate')),
            confidence TEXT NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
            reason TEXT NOT NULL DEFAULT '' CHECK (length(reason) <= 1000),
            actor TEXT NOT NULL,
            created_at TEXT NOT NULL,
            synthetic INTEGER NOT NULL DEFAULT 1 CHECK (synthetic = 1)
        );
        CREATE TRIGGER IF NOT EXISTS analyst_feedback_no_update
        BEFORE UPDATE ON analyst_feedback BEGIN
            SELECT RAISE(ABORT, 'analyst feedback is append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS analyst_feedback_no_delete
        BEFORE DELETE ON analyst_feedback BEGIN
            SELECT RAISE(ABORT, 'analyst feedback is append-only');
        END;
        """
    )


def _ensure_auth_tables(connection: sqlite3.Connection) -> None:
    """Store self-registered synthetic accounts without touching seeded users."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS demo_users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            role TEXT NOT NULL DEFAULT 'analyst' CHECK (role = 'analyst'),
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            synthetic INTEGER NOT NULL DEFAULT 1 CHECK (synthetic = 1)
        );
        CREATE INDEX IF NOT EXISTS idx_demo_users_email ON demo_users (email);
        """
    )
