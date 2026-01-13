"""Tests for health check endpoints."""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """Test /healthz endpoint returns healthy status."""
    response = await client.get("/healthz")
    assert response.status_code == 200

    data = await response.get_json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_check(client):
    """Test /readyz endpoint returns ready status."""
    response = await client.get("/readyz")
    assert response.status_code == 200

    data = await response.get_json()
    assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    """Test /metrics endpoint returns Prometheus metrics."""
    response = await client.get("/metrics")
    assert response.status_code == 200

    content = await response.get_data(as_text=True)
    assert "repo_worker" in content or "process" in content
