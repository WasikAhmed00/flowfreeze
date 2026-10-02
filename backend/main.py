"""FastAPI application for the local, synthetic-only FlowFreeze prototype."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import initialize_application_tables
from backend.routes import analysis, decisions, demo, incidents, metrics, simulation
from backend.schemas import HealthResponse


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_application_tables()
    yield


app = FastAPI(
    title="FlowFreeze API",
    description="Synthetic upay BD hackathon prototype. Recommendations require analyst review and do not execute wallet actions.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

for route_module in (incidents, analysis, decisions, simulation, metrics, demo):
    app.include_router(route_module.router, prefix="/api")


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": "FlowFreeze API", "docs": "/docs", "health": "/health"}
