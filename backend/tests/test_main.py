"""
Unit tests for the FastAPI application entrypoint and health endpoint.

Markers: unit
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# Patch init_db so tests don't need a real DB file
@pytest.fixture(scope="module")
def client():
    with patch("app.db.init_db"):
        from app.main import app

        with TestClient(app) as c:
            yield c


@pytest.mark.unit
def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


@pytest.mark.unit
def test_health_body(client):
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    # Version must be a non-empty string (either semver or "dev" fallback)
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0


@pytest.mark.unit
def test_health_version_from_pyproject(client):
    """Version in /health response must match pyproject.toml or be the 'dev' fallback."""
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    with pyproject.open("rb") as f:
        expected = tomllib.load(f)["project"]["version"]

    response = client.get("/health")
    assert response.json()["version"] == expected


@pytest.mark.unit
def test_health_version_fallback(monkeypatch):
    """When pyproject.toml is unreadable, version falls back to 'dev'."""
    import app.main as main_module

    monkeypatch.setattr(main_module, "_VERSION", "dev")
    with patch("app.db.init_db"):
        from app.main import app

        with TestClient(app) as c:
            response = c.get("/health")
    assert response.json()["version"] == "dev"


@pytest.mark.unit
def test_openapi_schema_accessible(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "NetworkCrawler"


@pytest.mark.unit
def test_docs_accessible(client):
    response = client.get("/docs")
    assert response.status_code == 200
