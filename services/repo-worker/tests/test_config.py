"""Tests for configuration handling."""

import pytest

from app.config import Config, CacheConfig


class TestCacheConfig:
    """Tests for cache configuration."""

    def test_is_mutable_tag_latest(self):
        """Test 'latest' is identified as mutable tag."""
        config = CacheConfig(
            enabled=True,
            max_size_gb=10,
            mutable_tag_patterns=["latest", "*nightly*"],
            mutable_tag_check_interval="5m",
        )

        assert config.is_mutable_tag("latest") is True

    def test_is_mutable_tag_nightly(self):
        """Test nightly tags are identified as mutable."""
        config = CacheConfig(
            enabled=True,
            max_size_gb=10,
            mutable_tag_patterns=["latest", "*nightly*"],
            mutable_tag_check_interval="5m",
        )

        assert config.is_mutable_tag("nightly") is True
        assert config.is_mutable_tag("v1.0-nightly") is True
        assert config.is_mutable_tag("nightly-build") is True

    def test_is_mutable_tag_immutable(self):
        """Test versioned tags are identified as immutable."""
        config = CacheConfig(
            enabled=True,
            max_size_gb=10,
            mutable_tag_patterns=["latest", "*nightly*"],
            mutable_tag_check_interval="5m",
        )

        assert config.is_mutable_tag("v1.0.0") is False
        assert config.is_mutable_tag("1.25.0") is False
        assert config.is_mutable_tag("stable") is False
        assert config.is_mutable_tag("sha-abc123") is False

    def test_is_mutable_tag_case_insensitive(self):
        """Test tag matching is case insensitive."""
        config = CacheConfig(
            enabled=True,
            max_size_gb=10,
            mutable_tag_patterns=["latest", "*nightly*"],
            mutable_tag_check_interval="5m",
        )

        assert config.is_mutable_tag("LATEST") is True
        assert config.is_mutable_tag("Latest") is True
        assert config.is_mutable_tag("NIGHTLY") is True

    def test_is_mutable_tag_empty_patterns(self):
        """Test no tags are mutable when patterns are empty."""
        config = CacheConfig(
            enabled=True,
            max_size_gb=10,
            mutable_tag_patterns=[],
            mutable_tag_check_interval="5m",
        )

        assert config.is_mutable_tag("latest") is False
        assert config.is_mutable_tag("nightly") is False


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_config_from_env(self, monkeypatch):
        """Test config can be loaded from environment variables."""
        monkeypatch.setenv("PORT", "8080")
        monkeypatch.setenv("S3_ENDPOINT", "http://s3.example.com")
        monkeypatch.setenv("S3_BUCKET", "my-bucket")
        monkeypatch.setenv("S3_ACCESS_KEY", "access123")
        monkeypatch.setenv("S3_SECRET_KEY", "secret456")

        from app.config import load_config
        config = load_config()

        assert config.port == 8080
        assert config.s3.endpoint == "http://s3.example.com"
        assert config.s3.bucket == "my-bucket"

    def test_config_defaults(self, monkeypatch):
        """Test config uses sensible defaults."""
        # Clear environment
        for key in ["PORT", "S3_ENDPOINT", "S3_BUCKET"]:
            monkeypatch.delenv(key, raising=False)

        from app.config import load_config
        config = load_config()

        assert config.port == 5050
        assert config.cache.enabled is True
