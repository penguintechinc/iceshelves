"""Tests for cache management."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.proxy.cache import CacheManager


class TestCacheManager:
    """Tests for CacheManager class."""

    @pytest.fixture
    def cache_config(self):
        """Create cache config for testing."""
        from app.config import CacheConfig
        return CacheConfig(
            enabled=True,
            max_size_gb=10,
            mutable_tag_patterns=["latest", "*nightly*"],
            mutable_tag_check_interval="5m",
        )

    @pytest.fixture
    def mock_storage(self):
        """Create mock storage."""
        storage = AsyncMock()
        storage.get_cache_metadata = AsyncMock(return_value=None)
        storage.put_cache_metadata = AsyncMock(return_value=True)
        return storage

    @pytest.fixture
    def cache_manager(self, mock_storage, cache_config):
        """Create cache manager for testing."""
        return CacheManager(mock_storage, cache_config)

    def test_should_revalidate_mutable_tag_old_cache(
        self, cache_manager, cache_config
    ):
        """Test that old cache for mutable tags needs revalidation."""
        cache_meta = {
            "mutable": True,
            "last_check": (
                datetime.utcnow() - timedelta(minutes=10)
            ).isoformat(),
        }

        assert cache_manager.should_revalidate(cache_meta, cache_config) is True

    def test_should_revalidate_mutable_tag_recent_cache(
        self, cache_manager, cache_config
    ):
        """Test that recent cache for mutable tags doesn't need revalidation."""
        cache_meta = {
            "mutable": True,
            "last_check": (
                datetime.utcnow() - timedelta(minutes=1)
            ).isoformat(),
        }

        assert cache_manager.should_revalidate(cache_meta, cache_config) is False

    def test_should_revalidate_immutable_tag(self, cache_manager, cache_config):
        """Test that immutable tags never need revalidation."""
        cache_meta = {
            "mutable": False,
            "last_check": (
                datetime.utcnow() - timedelta(days=30)
            ).isoformat(),
        }

        assert cache_manager.should_revalidate(cache_meta, cache_config) is False

    def test_is_mutable_tag_detection(self, cache_manager):
        """Test mutable tag detection."""
        assert cache_manager.is_mutable_tag("latest") is True
        assert cache_manager.is_mutable_tag("nightly") is True
        assert cache_manager.is_mutable_tag("v1.0.0") is False
        assert cache_manager.is_mutable_tag("stable") is False

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache_manager, mock_storage):
        """Test cache miss returns None."""
        mock_storage.get_cache_metadata.return_value = None

        result = await cache_manager.get_cache(
            "dockerhub", "library/nginx", "latest"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, cache_manager, mock_storage):
        """Test cache hit returns cached data."""
        cached_data = {
            "manifest": {"schemaVersion": 2},
            "digest": "sha256:abc123",
        }
        cache_meta = {
            "mutable": True,
            "last_check": datetime.utcnow().isoformat(),
            "data": cached_data,
        }
        mock_storage.get_cache_metadata.return_value = cache_meta

        result = await cache_manager.get_cache(
            "dockerhub", "library/nginx", "latest"
        )

        assert result == cache_meta

    @pytest.mark.asyncio
    async def test_set_cache(self, cache_manager, mock_storage):
        """Test setting cache data."""
        data = {
            "manifest": {"schemaVersion": 2},
            "digest": "sha256:abc123",
        }

        await cache_manager.set_cache(
            "dockerhub", "library/nginx", "latest", data, is_mutable=True
        )

        mock_storage.put_cache_metadata.assert_called_once()
        call_args = mock_storage.put_cache_metadata.call_args
        assert call_args[0][0] == "dockerhub"
        assert call_args[0][1] == "library/nginx"
        assert call_args[0][2] == "latest"

    def test_parse_check_interval(self, cache_manager):
        """Test parsing check interval strings."""
        assert cache_manager._parse_interval("5m") == timedelta(minutes=5)
        assert cache_manager._parse_interval("1h") == timedelta(hours=1)
        assert cache_manager._parse_interval("30s") == timedelta(seconds=30)
        assert cache_manager._parse_interval("1d") == timedelta(days=1)
