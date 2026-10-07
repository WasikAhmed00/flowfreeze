"""Signed demo authentication and role-based authorization for FlowFreeze."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import os
import secrets

from fastapi import Header, HTTPException, status
from backend.db import connect_database


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    name: str
    email: str
    role: str


DEMO_USERS = {
    "nadia.rahman@flowfreeze.demo": ("Nadia Rahman", "analyst", "analyst-demo-42"),
    "rahim.khan@flowfreeze.demo": ("Rahim Khan", "risk_manager", "manager-demo-42"),
    "sadia.akter@flowfreeze.demo": ("Sadia Akter", "compliance", "compliance-demo-42"),
    "admin@flowfreeze.demo": ("FlowFreeze Admin", "admin", "admin-demo-42"),
    "support@flowfreeze.demo": ("Customer Support", "customer_support", "support-demo-42"),
}
ROLE_LABELS = {
    "analyst": "Fraud/Risk Analyst",
    "risk_manager": "Risk Manager",
    "compliance": "Compliance",
    "admin": "Administrator",
    "customer_support": "Customer Support",
}


def _secret() -> bytes:
    return os.getenv("FLOWFREEZE_AUTH_SECRET", "flowfreeze-local-demo-secret-change-me").encode()


def authenticate(email: str, password: str) -> CurrentUser | None:
    normalized_email = email.strip().lower()
    record = DEMO_USERS.get(normalized_email)
    if not record or not hmac.compare_digest(password, record[2]):
        try:
            connection = connect_database()
            try:
                row = connection.execute(
                    "SELECT user_id, name, email, role, password_hash FROM demo_users WHERE email = ?",
                    (normalized_email,),
                ).fetchone()
            finally:
                connection.close()
        except (FileNotFoundError, OSError):
            row = None
        if row is None or not verify_password(password, row["password_hash"]):
            return None
        return CurrentUser(row["user_id"], row["name"], row["email"], row["role"])
    name, role, _ = record
    return CurrentUser(normalized_email.split("@")[0], name, normalized_email, role)


def hash_password(password: str) -> str:
    """Hash a synthetic-demo password with a salted, standard-library KDF."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"pbkdf2_sha256$120000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_synthetic_account(name: str, email: str, password: str) -> CurrentUser:
    """Create an analyst-only account for this local synthetic workspace."""
    normalized_email = email.strip().lower()
    user = CurrentUser(f"user-{secrets.token_hex(8)}", name.strip(), normalized_email, "analyst")
    connection = connect_database()
    try:
        connection.execute(
            "INSERT INTO demo_users (user_id, name, email, role, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user.user_id, user.name, user.email, user.role, hash_password(password), datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()
    finally:
        connection.close()
    return user


def issue_token(user: CurrentUser, expires_minutes: int = 480) -> str:
    payload = {"sub": user.user_id, "name": user.name, "email": user.email, "role": user.role,
               "exp": int((datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)).timestamp())}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(_secret(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def user_from_token(token: str | None) -> CurrentUser:
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        encoded, signature = token[7:].split(".", 1)
        expected = hmac.new(_secret(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(payload["exp"]) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError
        return CurrentUser(payload["sub"], payload["name"], payload["email"], payload["role"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    return user_from_token(authorization)


def require_roles(*roles: str):
    def dependency(authorization: str | None = Header(default=None)) -> CurrentUser:
        user = user_from_token(authorization)
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your role cannot perform this action.")
        return user
    return dependency


def require_demo_write_access(
    x_flowfreeze_write_key: str | None = Header(default=None, alias="X-FlowFreeze-Write-Key"),
) -> None:
    """Keep public demo writes explicitly opt-in and keyed in non-development deployments."""
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env == "development":
        return
    if os.getenv("ENABLE_DEMO_WRITES", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Demo writes are disabled on this public deployment.")
    expected = os.getenv("DEMO_WRITE_KEY", "")
    if not expected or not x_flowfreeze_write_key or not hmac.compare_digest(x_flowfreeze_write_key, expected):
        raise HTTPException(status_code=401, detail="A valid X-FlowFreeze-Write-Key is required for demo writes.")
