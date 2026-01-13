"""Configuration management for repo-worker service."""

import os
from dataclasses import dataclass, field
from typing import List
import yaml


@dataclass
class S3Config:
    """S3-compatible storage configuration."""
    endpoint: str = "http://minio:9000"
    bucket: str = "repository"
    region: str = ""
    access_key: str = ""
    secret_key: str = ""
    use_ssl: bool = False


@dataclass
class CacheConfig:
    """Caching configuration."""
    enabled: bool = True
    max_size_gb: int = 100
    mutable_tag_patterns: List[str] = field(default_factory=lambda: ["latest", "*nightly*"])
    mutable_tag_check_interval: str = "5m"


@dataclass
class AuthConfig:
    """Authentication configuration."""
    enabled: bool = True
    flask_backend_url: str = "http://flask-backend:5000"
    jwt_secret_key: str = ""
    anonymous_pull: bool = True


@dataclass
class UpstreamRegistry:
    """Upstream registry configuration."""
    name: str
    url: str
    auth_type: str = "none"  # none, basic, token, aws, gcp, azure
    username: str = ""
    password: str = ""
    token: str = ""
    token_env: str = ""


@dataclass
class Config:
    """Main application configuration."""
    # Server
    host: str = "0.0.0.0"
    port: int = 5050
    debug: bool = False
    workers: int = 4

    # Storage (S3-compatible required)
    s3: S3Config = field(default_factory=S3Config)

    # Caching
    cache: CacheConfig = field(default_factory=CacheConfig)

    # Authentication
    auth: AuthConfig = field(default_factory=AuthConfig)

    # Built-in upstream registries
    builtin_upstreams: List[UpstreamRegistry] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()

        # Server config
        config.host = os.getenv("HOST", config.host)
        config.port = int(os.getenv("PORT", config.port))
        config.debug = os.getenv("DEBUG", "false").lower() == "true"
        config.workers = int(os.getenv("WORKERS", config.workers))

        # S3 config
        config.s3.endpoint = os.getenv("S3_ENDPOINT", config.s3.endpoint)
        config.s3.bucket = os.getenv("S3_BUCKET", config.s3.bucket)
        config.s3.region = os.getenv("S3_REGION", config.s3.region)
        config.s3.access_key = os.getenv("S3_ACCESS_KEY", config.s3.access_key)
        config.s3.secret_key = os.getenv("S3_SECRET_KEY", config.s3.secret_key)
        config.s3.use_ssl = os.getenv("S3_USE_SSL", "false").lower() == "true"

        # Auth config
        config.auth.enabled = os.getenv("AUTH_ENABLED", "true").lower() == "true"
        config.auth.flask_backend_url = os.getenv(
            "FLASK_BACKEND_URL", config.auth.flask_backend_url
        )
        config.auth.jwt_secret_key = os.getenv("JWT_SECRET_KEY", config.auth.jwt_secret_key)
        config.auth.anonymous_pull = os.getenv("ANONYMOUS_PULL", "true").lower() == "true"

        # Cache config
        config.cache.enabled = os.getenv("CACHE_ENABLED", "true").lower() == "true"
        config.cache.max_size_gb = int(os.getenv("CACHE_MAX_SIZE_GB", config.cache.max_size_gb))

        # Initialize built-in upstreams
        config.builtin_upstreams = cls._get_builtin_upstreams()

        return config

    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        config = cls()

        if "server" in data:
            config.host = data["server"].get("host", config.host)
            config.port = data["server"].get("port", config.port)
            config.debug = data["server"].get("debug", config.debug)
            config.workers = data["server"].get("workers", config.workers)

        if "storage" in data and "s3" in data["storage"]:
            s3_data = data["storage"]["s3"]
            config.s3 = S3Config(
                endpoint=s3_data.get("endpoint", config.s3.endpoint),
                bucket=s3_data.get("bucket", config.s3.bucket),
                region=s3_data.get("region", config.s3.region),
                access_key=os.getenv(s3_data.get("access_key_env", "S3_ACCESS_KEY"), ""),
                secret_key=os.getenv(s3_data.get("secret_key_env", "S3_SECRET_KEY"), ""),
                use_ssl=s3_data.get("use_ssl", config.s3.use_ssl),
            )

        if "cache" in data:
            cache_data = data["cache"]
            config.cache = CacheConfig(
                enabled=cache_data.get("enabled", config.cache.enabled),
                max_size_gb=cache_data.get("max_size_gb", config.cache.max_size_gb),
                mutable_tag_patterns=cache_data.get(
                    "mutable_tag_patterns", config.cache.mutable_tag_patterns
                ),
                mutable_tag_check_interval=cache_data.get(
                    "mutable_tag_check_interval", config.cache.mutable_tag_check_interval
                ),
            )

        if "auth" in data:
            auth_data = data["auth"]
            config.auth = AuthConfig(
                enabled=auth_data.get("enabled", config.auth.enabled),
                flask_backend_url=auth_data.get(
                    "flask_backend_url", config.auth.flask_backend_url
                ),
                jwt_secret_key=os.getenv(
                    auth_data.get("jwt_secret_env", "JWT_SECRET_KEY"), ""
                ),
                anonymous_pull=auth_data.get("anonymous_pull", config.auth.anonymous_pull),
            )

        # Initialize built-in upstreams
        config.builtin_upstreams = cls._get_builtin_upstreams()

        return config

    @staticmethod
    def _get_builtin_upstreams() -> List[UpstreamRegistry]:
        """Get list of built-in upstream registries."""
        return [
            UpstreamRegistry(
                name="dockerhub",
                url="https://registry-1.docker.io",
                auth_type="none",
            ),
            UpstreamRegistry(
                name="ghcr",
                url="https://ghcr.io",
                auth_type="token",
                token_env="GHCR_TOKEN",
            ),
            UpstreamRegistry(
                name="quay",
                url="https://quay.io",
                auth_type="none",
            ),
            UpstreamRegistry(
                name="gcr",
                url="https://gcr.io",
                auth_type="gcp",
            ),
        ]

    def is_mutable_tag(self, tag: str) -> bool:
        """Check if a tag matches mutable tag patterns."""
        import fnmatch
        for pattern in self.cache.mutable_tag_patterns:
            if fnmatch.fnmatch(tag, pattern):
                return True
        return False
