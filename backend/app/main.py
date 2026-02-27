"""NetworkCrawler — FastAPI application entrypoint."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.db import init_db

logger = logging.getLogger(__name__)

SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "3600"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()

    from apscheduler.schedulers.background import BackgroundScheduler

    from app.scan_runner import run_scan_and_persist

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_scan_and_persist,
        "interval",
        seconds=SCAN_INTERVAL_SECONDS,
        kwargs={"triggered_by": "scheduler"},
        id="periodic_scan",
    )
    scheduler.start()
    logger.info("Scheduler started; interval=%ds", SCAN_INTERVAL_SECONDS)

    yield

    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


app = FastAPI(
    title="NetworkCrawler",
    description="LAN security posture scanner for home lab operators.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:  # noqa: ANN001 — callable type varies by Starlette version
    """Attach security headers to every response."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
