from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_health_returns_200_when_db_connected(client):
    with patch("app.routers.health.check_db_connection", return_value=True):
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"
    assert body["uptime_seconds"] >= 0


def test_health_returns_503_when_db_unreachable(client):
    with patch("app.routers.health.check_db_connection", return_value=False):
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "unreachable"


def test_health_response_has_all_required_fields(client):
    """Contract test: all fields the dashboard and K8s probes depend on must be present."""
    with patch("app.routers.health.check_db_connection", return_value=True):
        response = client.get("/health")

    required = {"status", "environment", "uptime_seconds", "database", "python_version", "version"}
    assert required.issubset(response.json().keys())
