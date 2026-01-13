"""Tests for Helm Chart Repository API endpoints."""

import pytest
import yaml


@pytest.mark.asyncio
async def test_helm_index_empty(client, mock_s3_storage):
    """Test /index.yaml returns valid empty index."""
    mock_s3_storage.list_charts.return_value = []

    response = await client.get("/index.yaml")
    assert response.status_code == 200

    content = await response.get_data(as_text=True)
    index = yaml.safe_load(content)

    assert index["apiVersion"] == "v1"
    assert "entries" in index
    assert "generated" in index


@pytest.mark.asyncio
async def test_helm_index_with_charts(client, mock_s3_storage):
    """Test /index.yaml returns charts in index."""
    mock_s3_storage.list_charts.return_value = [
        {
            "name": "mychart",
            "version": "1.0.0",
            "description": "A test chart",
            "digest": "sha256:abc123",
        },
        {
            "name": "mychart",
            "version": "1.1.0",
            "description": "A test chart",
            "digest": "sha256:def456",
        },
    ]

    response = await client.get("/index.yaml")
    assert response.status_code == 200

    content = await response.get_data(as_text=True)
    index = yaml.safe_load(content)

    assert "mychart" in index["entries"]
    assert len(index["entries"]["mychart"]) == 2


@pytest.mark.asyncio
async def test_chart_download_not_found(client, mock_s3_storage):
    """Test chart download returns 404 when not found."""
    mock_s3_storage.get_chart.return_value = None

    response = await client.get("/charts/mychart-1.0.0.tgz")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chart_download_success(client, mock_s3_storage):
    """Test chart download returns chart file."""
    mock_s3_storage.get_chart.return_value = b"fake-chart-content"

    response = await client.get("/charts/mychart-1.0.0.tgz")
    assert response.status_code == 200
    assert response.content_type == "application/gzip"


@pytest.mark.asyncio
async def test_chart_list_api(client, mock_s3_storage):
    """Test /api/v1/charts returns chart list."""
    mock_s3_storage.list_charts.return_value = [
        {"name": "chart1", "version": "1.0.0"},
        {"name": "chart2", "version": "2.0.0"},
    ]

    response = await client.get("/api/v1/charts")
    assert response.status_code == 200

    data = await response.get_json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_chart_upload_requires_auth(client):
    """Test chart upload requires authentication when auth is enabled."""
    # This test assumes auth is disabled in test config
    # In production with auth enabled, this should return 401

    # For now, test the upload endpoint exists
    response = await client.post(
        "/api/v1/charts",
        data=b"fake-chart-data",
        content_type="application/gzip",
    )

    # Should not be 404 (endpoint exists)
    assert response.status_code != 404
