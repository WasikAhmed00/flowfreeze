"""Minimal process-local API telemetry; reset on restart and not a time series."""
from __future__ import annotations

from collections import Counter
from threading import Lock

_lock = Lock()
_requests = 0
_errors = 0
_total_ms = 0.0
_max_ms = 0.0
_status_codes: Counter[str] = Counter()


def record_request(status_code: int, elapsed_ms: float) -> None:
    global _requests, _errors, _total_ms, _max_ms
    with _lock:
        _requests += 1
        _errors += status_code >= 500
        _total_ms += elapsed_ms
        _max_ms = max(_max_ms, elapsed_ms)
        _status_codes[str(status_code)] += 1


def snapshot() -> dict:
    with _lock:
        return {
            "requests_total": _requests,
            "server_errors_total": _errors,
            "mean_response_ms": round(_total_ms / _requests, 3) if _requests else 0.0,
            "max_response_ms": round(_max_ms, 3),
            "status_codes": dict(_status_codes),
            "scope": "process-local since restart",
        }
