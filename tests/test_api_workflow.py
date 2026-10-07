from __future__ import annotations

import os

from fastapi.testclient import TestClient


def test_authenticated_case_queue_and_audit_timeline(generated_fixture, monkeypatch):
    """The analyst can authenticate, open the queue, and read a case audit timeline."""
    from backend import db
    from backend.main import app

    monkeypatch.setattr(db, "DEFAULT_DATABASE_PATH", generated_fixture["database"])
    monkeypatch.setenv("APP_ENV", "development")
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"email": "nadia.rahman@flowfreeze.demo", "password": "analyst-demo-42"})
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/incidents", headers=headers).status_code == 200
        timeline = client.get("/api/decisions/SCN-02-FANOUT-0001/audit", headers=headers)
        assert timeline.status_code == 200
        assert timeline.json()["events"][0]["action"] == "Case created"


def test_role_cannot_submit_analyst_decision(generated_fixture, monkeypatch):
    """Customer support has read access but cannot submit a financial recommendation."""
    from backend import db
    from backend.main import app

    monkeypatch.setattr(db, "DEFAULT_DATABASE_PATH", generated_fixture["database"])
    monkeypatch.setenv("APP_ENV", "development")
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"email": "support@flowfreeze.demo", "password": "support-demo-42"})
        token = response.json()["access_token"]
        denied = client.post("/api/decisions", headers={"Authorization": f"Bearer {token}"}, json={})
        assert denied.status_code == 403


def test_synthetic_account_can_register_and_login(generated_fixture, monkeypatch):
    """A newly created synthetic analyst can sign in on a later request."""
    from backend import db
    from backend.main import app

    monkeypatch.setattr(db, "DEFAULT_DATABASE_PATH", generated_fixture["database"])
    monkeypatch.setenv("APP_ENV", "development")
    with TestClient(app) as client:
        created = client.post(
            "/api/auth/register",
            json={"name": "Upay Analyst", "email": "new.analyst@upay.bd", "password": "upay-demo-42"},
        )
        assert created.status_code == 201
        assert created.json()["user"]["role"] == "analyst"

        login = client.post(
            "/api/auth/login",
            json={"email": "new.analyst@upay.bd", "password": "upay-demo-42"},
        )
        assert login.status_code == 200
        assert login.json()["user"]["email"] == "new.analyst@upay.bd"
