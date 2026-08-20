"""Tests for GET /health - the one endpoint that exists on Day 1."""
from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_healthy_status(client: TestClient) -> None:
    response = client.get("/health")
    assert response.json() == {"status": "healthy"}


def test_unknown_route_returns_404(client: TestClient) -> None:
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
