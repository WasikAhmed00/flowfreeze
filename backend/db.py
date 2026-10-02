"""SQLite connection helpers for the local FlowFreeze MVP."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

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
