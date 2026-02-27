"""Package init — exposes the FastAPI app for uvicorn."""

from app.main import app  # noqa: F401

__all__ = ["app"]
