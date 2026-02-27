"""Package init — exposes the FastAPI app for uvicorn."""

from app.main import app  # noqa: F401 — re-exported for uvicorn app:app entrypoint

__all__ = ["app"]
