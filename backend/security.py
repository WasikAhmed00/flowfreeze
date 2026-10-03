"""Small request guards for the public synthetic demo deployment."""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def require_demo_write_access(
    x_flowfreeze_write_key: str | None = Header(default=None, alias="X-FlowFreeze-Write-Key"),
) -> None:
    """Allow local writes, but make public writes explicitly opt-in and keyed.

    The frontend's demo login is intentionally not authentication. In production,
    writes stay disabled unless the operator enables them and configures a secret
    request key. This keeps a public Render demo read-only by default.
    """
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env == "development":
        return
    if os.getenv("ENABLE_DEMO_WRITES", "false").lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="Demo writes are disabled on this public deployment.",
        )
    expected = os.getenv("DEMO_WRITE_KEY", "")
    if not expected or not x_flowfreeze_write_key or not hmac.compare_digest(
        x_flowfreeze_write_key, expected
    ):
        raise HTTPException(
            status_code=401,
            detail="A valid X-FlowFreeze-Write-Key is required for demo writes.",
        )
