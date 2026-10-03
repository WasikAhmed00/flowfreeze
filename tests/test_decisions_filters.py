from __future__ import annotations

from contextlib import contextmanager
import sqlite3

from backend.routes import decisions as decisions_route


def test_list_decisions_filters_and_paginates(monkeypatch, tmp_path):
    database = tmp_path / "audit.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE analyst_decisions (
                decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id TEXT NOT NULL,
                wallet_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                proposed_amount_bdt TEXT NOT NULL,
                reason TEXT NOT NULL,
                actor TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        connection.executemany(
            """INSERT INTO analyst_decisions
            (scenario_id, wallet_id, decision, proposed_amount_bdt, reason, actor, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                ("SCN-ALPHA", "WALLET-ALPHA", "reject", "0.00", "Manual review required", "analyst-one", "2026-01-01"),
                ("SCN-BETA", "WALLET-BETA", "approve", "250.00", "Reviewed carefully", "analyst-two", "2026-01-02"),
                ("SCN-GAMMA", "WALLET-GAMMA", "reject", "0.00", "Manual review complete", "analyst-three", "2026-01-03"),
            ],
        )

    @contextmanager
    def test_connection():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    monkeypatch.setattr(decisions_route, "application_connection", test_connection)
    result = decisions_route.list_decisions(
        scenario_id=None,
        decision="reject",
        q="manual",
        limit=1,
        offset=1,
    )

    assert result["total"] == 2
    assert result["limit"] == 1
    assert result["offset"] == 1
    assert len(result["decisions"]) == 1
    assert result["decisions"][0]["scenario_id"] == "SCN-ALPHA"


def test_list_decisions_searches_actor_and_scenario(monkeypatch, tmp_path):
    database = tmp_path / "audit.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE analyst_decisions (
                decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id TEXT NOT NULL,
                wallet_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                proposed_amount_bdt TEXT NOT NULL,
                reason TEXT NOT NULL,
                actor TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT INTO analyst_decisions
            (scenario_id, wallet_id, decision, proposed_amount_bdt, reason, actor, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("SCN-BETA", "WALLET-BETA", "approve", "250.00", "Reviewed carefully", "analyst-two", "2026-01-02"),
        )

    @contextmanager
    def test_connection():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    monkeypatch.setattr(decisions_route, "application_connection", test_connection)
    result = decisions_route.list_decisions(
        scenario_id=None,
        decision=None,
        q="analyst-two",
        limit=25,
        offset=0,
    )

    assert result["total"] == 1
    assert result["decisions"][0]["wallet_id"] == "WALLET-BETA"
