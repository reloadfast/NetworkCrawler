"""NetworkCrawler — FastAPI application entrypoint."""

from __future__ import annotations

import logging
import os
import tomllib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.db import init_db

logger = logging.getLogger(__name__)

SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "3600"))


# Read version from pyproject.toml at import time; fall back to "dev" on any error.
def _read_version() -> str:
    try:
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        with pyproject.open("rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:  # noqa: BLE001 — intentional broad catch for version fallback
        return "dev"


_VERSION = _read_version()


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
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:  # noqa: ANN001 — callable type varies by Starlette version
    """Attach security headers to every response."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    )
    return response


app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": _VERSION}


# ── Static file serving ───────────────────────────────────────────────────────
# frontend/dist is copied into the image at /app/frontend/dist (see Dockerfile).
# In the dev tree the path resolves relative to this file:
#   __file__ = .../backend/app/main.py  →  parent.parent.parent = project root
_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    # Serve compiled assets (JS, CSS, images) under /assets
    app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catch_all(full_path: str) -> FileResponse:  # noqa: ARG001 — path consumed by router, not used here
        """Return index.html for all non-API routes so React Router works client-side."""
        return FileResponse(_FRONTEND_DIST / "index.html")
