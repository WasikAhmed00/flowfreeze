"""FastAPI application for the local, synthetic-only FlowFreeze prototype."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.db import initialize_application_tables
from backend.routes import analysis, cases, decisions, demo, incidents, metrics, simulation, transactions
from backend.schemas import HealthResponse
from backend.telemetry import record_request


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_application_tables()
    yield


app = FastAPI(
    title="FlowFreeze API",
    description="Synthetic MFS-like fraud analysis prototype. Integration endpoints accept synthetic or de-identified records; no provider or wallet actions are connected.",
    version="0.2.0",
    lifespan=lifespan,
)
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-FlowFreeze-Write-Key"],
)

@app.middleware("http")
async def api_telemetry(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        record_request(status_code, (time.perf_counter() - started) * 1000)


for route_module in (incidents, analysis, decisions, simulation, transactions, cases, metrics, demo):
    app.include_router(route_module.router, prefix="/api")


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    database = "ok"
    try:
        from backend.db import connect_database

        connection = connect_database()
        try:
            connection.execute("SELECT 1").fetchone()
        finally:
            connection.close()
    except Exception:
        database = "unavailable"
    return HealthResponse(status="ok" if database == "ok" else "degraded", database=database)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": "FlowFreeze API", "docs": "/docs", "health": "/health"}
