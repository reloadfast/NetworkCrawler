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
    assert response.json() == {"status": "ok"}


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
