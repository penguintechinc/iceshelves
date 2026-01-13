"""Tests for OCI Distribution API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_v2_endpoint(client):
    """Test /v2/ endpoint returns API version."""
    response = await client.get("/v2/")
    assert response.status_code == 200

    data = await response.get_json()
    assert data == {}


@pytest.mark.asyncio
async def test_catalog_empty(client, mock_s3_storage):
    """Test /v2/_catalog returns empty list when no repositories."""
    mock_s3_storage.list_repositories.return_value = []

    response = await client.get("/v2/_catalog")
    assert response.status_code == 200

    data = await response.get_json()
    assert "repositories" in data
    assert data["repositories"] == []


@pytest.mark.asyncio
async def test_catalog_with_repos(client, mock_s3_storage):
    """Test /v2/_catalog returns repositories list."""
    mock_s3_storage.list_repositories.return_value = [
        "library/nginx",
        "library/alpine",
        "myapp/backend",
    ]

    response = await client.get("/v2/_catalog")
    assert response.status_code == 200

    data = await response.get_json()
    assert "repositories" in data
    assert len(data["repositories"]) == 3
    assert "library/nginx" in data["repositories"]


@pytest.mark.asyncio
async def test_tags_list_empty(client, mock_s3_storage):
    """Test tags list returns empty when no tags."""
    mock_s3_storage.list_tags.return_value = []

    response = await client.get("/v2/library/nginx/tags/list")
    assert response.status_code == 200

    data = await response.get_json()
    assert data["name"] == "library/nginx"
    assert data["tags"] == []


@pytest.mark.asyncio
async def test_tags_list_with_tags(client, mock_s3_storage):
    """Test tags list returns tags."""
    mock_s3_storage.list_tags.return_value = ["latest", "1.25.0", "1.24.0"]

    response = await client.get("/v2/library/nginx/tags/list")
    assert response.status_code == 200

    data = await response.get_json()
    assert data["name"] == "library/nginx"
    assert len(data["tags"]) == 3
    assert "latest" in data["tags"]


@pytest.mark.asyncio
async def test_blob_not_found(client, mock_s3_storage):
    """Test GET blob returns 404 when not found."""
    mock_s3_storage.get_blob.return_value = None

    response = await client.get(
        "/v2/library/nginx/blobs/sha256:abc123def456"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_manifest_not_found(client, mock_s3_storage):
    """Test GET manifest returns 404 when not found."""
    mock_s3_storage.get_manifest.return_value = None

    response = await client.get("/v2/library/nginx/manifests/latest")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_blob_upload_initiate(client):
    """Test POST to initiate blob upload returns upload URL."""
    response = await client.post("/v2/library/nginx/blobs/uploads/")

    # Should return 202 Accepted with Location header
    assert response.status_code == 202
    assert "Location" in response.headers
    assert "Docker-Upload-UUID" in response.headers


@pytest.mark.asyncio
async def test_manifest_put_requires_content_type(client):
    """Test PUT manifest requires Content-Type header."""
    response = await client.put(
        "/v2/library/nginx/manifests/latest",
        data=b"{}",
    )

    # Should fail without proper content type
    assert response.status_code in [400, 415]
