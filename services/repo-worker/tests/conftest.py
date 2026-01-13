"""Pytest configuration and fixtures for repo-worker tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import create_app
from app.config import Config, S3Config, CacheConfig, AuthConfig, UpstreamsConfig


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config() -> Config:
    """Create test configuration."""
    return Config(
        port=5050,
        debug=True,
        s3=S3Config(
            endpoint="http://localhost:9000",
            bucket="test-bucket",
            region="",
            access_key="testkey",
            secret_key="testsecret",
            use_ssl=False,
        ),
        cache=CacheConfig(
            enabled=True,
            max_size_gb=1,
            mutable_tag_patterns=["latest", "*nightly*"],
            mutable_tag_check_interval="1m",
        ),
        auth=AuthConfig(
            enabled=False,
            flask_backend_url="http://localhost:5000",
            anonymous_pull=True,
            jwt_secret="test-secret",
        ),
        upstreams=UpstreamsConfig(
            builtin=[],
            custom_source="flask-backend",
        ),
    )


@pytest.fixture
def mock_s3_storage():
    """Create mock S3 storage."""
    storage = AsyncMock()
    storage.get_blob = AsyncMock(return_value=None)
    storage.put_blob = AsyncMock(return_value=True)
    storage.delete_blob = AsyncMock(return_value=True)
    storage.get_manifest = AsyncMock(return_value=None)
    storage.put_manifest = AsyncMock(return_value=True)
    storage.list_tags = AsyncMock(return_value=[])
    storage.list_repositories = AsyncMock(return_value=[])
    storage.get_chart = AsyncMock(return_value=None)
    storage.put_chart = AsyncMock(return_value=True)
    storage.list_charts = AsyncMock(return_value=[])
    return storage


@pytest.fixture
async def app(test_config, mock_s3_storage):
    """Create test application."""
    application = create_app(test_config)
    application.storage = mock_s3_storage
    return application


@pytest.fixture
async def client(app):
    """Create test client."""
    return app.test_client()
