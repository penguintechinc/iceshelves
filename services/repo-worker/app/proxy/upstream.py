"""Upstream registry client for pull-through proxy.

Handles communication with upstream Docker registries (Docker Hub, GHCR, etc.)
with support for various authentication methods.
"""

import asyncio
import base64
import logging
from dataclasses import dataclass
from typing import AsyncIterator, Optional

import aiohttp
from aiohttp_retry import ExponentialRetry, RetryClient

logger = logging.getLogger(__name__)


@dataclass
class RegistryAuth:
    """Authentication configuration for upstream registry."""
    auth_type: str = "none"  # none, basic, token, aws, gcp, azure
    username: str = ""
    password: str = ""
    token: str = ""


@dataclass
class ManifestResult:
    """Result of fetching a manifest from upstream."""
    content: bytes
    digest: str
    content_type: str


class UpstreamRegistry:
    """Client for interacting with upstream Docker registries."""

    def __init__(
        self,
        name: str,
        url: str,
        auth: Optional[RegistryAuth] = None,
        timeout: int = 30,
    ):
        self.name = name
        self.url = url.rstrip("/")
        self.auth = auth or RegistryAuth()
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._token_cache: dict[str, tuple[str, float]] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        """Create an aiohttp session with retry logic."""
        retry_options = ExponentialRetry(attempts=3)
        connector = aiohttp.TCPConnector(limit=10)
        session = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=connector,
        )
        return session

    async def _get_auth_header(
        self, session: aiohttp.ClientSession, scope: str = ""
    ) -> Optional[str]:
        """Get authentication header for requests.

        For Docker Hub and similar registries, we need to get a token
        from the auth service first.
        """
        if self.auth.auth_type == "none":
            return None

        if self.auth.auth_type == "basic":
            credentials = f"{self.auth.username}:{self.auth.password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return f"Basic {encoded}"

        if self.auth.auth_type == "token":
            return f"Bearer {self.auth.token}"

        # For registries that require token exchange (like Docker Hub)
        # We need to handle the token exchange flow
        return None

    async def _handle_auth_challenge(
        self,
        session: aiohttp.ClientSession,
        www_authenticate: str,
    ) -> Optional[str]:
        """Handle WWW-Authenticate challenge and get token."""
        # Parse WWW-Authenticate header
        # Format: Bearer realm="...",service="...",scope="..."
        if not www_authenticate.lower().startswith("bearer "):
            return None

        params = {}
        parts = www_authenticate[7:].split(",")
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                params[key.strip()] = value.strip('"')

        realm = params.get("realm")
        service = params.get("service", "")
        scope = params.get("scope", "")

        if not realm:
            return None

        # Build token request URL
        token_url = f"{realm}?service={service}"
        if scope:
            token_url += f"&scope={scope}"

        # Make token request
        headers = {}
        if self.auth.auth_type == "basic" and self.auth.username:
            credentials = f"{self.auth.username}:{self.auth.password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        try:
            async with session.get(token_url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("token") or data.get("access_token")
        except Exception as e:
            logger.error(f"Failed to get auth token: {e}")

        return None

    async def check_manifest(self, name: str, reference: str) -> Optional[str]:
        """Check if manifest exists and return its digest.

        Args:
            name: Image name (e.g., "library/nginx")
            reference: Tag or digest

        Returns:
            Digest string if exists, None otherwise
        """
        url = f"{self.url}/v2/{name}/manifests/{reference}"

        async with await self._get_session() as session:
            headers = {
                "Accept": (
                    "application/vnd.docker.distribution.manifest.v2+json, "
                    "application/vnd.docker.distribution.manifest.list.v2+json, "
                    "application/vnd.oci.image.manifest.v1+json, "
                    "application/vnd.oci.image.index.v1+json"
                ),
            }

            # First attempt
            async with session.head(url, headers=headers) as resp:
                if resp.status == 401:
                    # Handle auth challenge
                    www_auth = resp.headers.get("WWW-Authenticate", "")
                    token = await self._handle_auth_challenge(session, www_auth)
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        async with session.head(url, headers=headers) as auth_resp:
                            if auth_resp.status == 200:
                                return auth_resp.headers.get("Docker-Content-Digest")
                            return None
                    return None

                if resp.status == 200:
                    return resp.headers.get("Docker-Content-Digest")

                return None

    async def get_manifest(self, name: str, reference: str) -> Optional[ManifestResult]:
        """Fetch manifest from upstream.

        Args:
            name: Image name (e.g., "library/nginx")
            reference: Tag or digest

        Returns:
            ManifestResult if found, None otherwise
        """
        url = f"{self.url}/v2/{name}/manifests/{reference}"

        async with await self._get_session() as session:
            headers = {
                "Accept": (
                    "application/vnd.docker.distribution.manifest.v2+json, "
                    "application/vnd.docker.distribution.manifest.list.v2+json, "
                    "application/vnd.oci.image.manifest.v1+json, "
                    "application/vnd.oci.image.index.v1+json"
                ),
            }

            # First attempt
            async with session.get(url, headers=headers) as resp:
                if resp.status == 401:
                    # Handle auth challenge
                    www_auth = resp.headers.get("WWW-Authenticate", "")
                    token = await self._handle_auth_challenge(session, www_auth)
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        async with session.get(url, headers=headers) as auth_resp:
                            if auth_resp.status == 200:
                                content = await auth_resp.read()
                                return ManifestResult(
                                    content=content,
                                    digest=auth_resp.headers.get(
                                        "Docker-Content-Digest", ""
                                    ),
                                    content_type=auth_resp.headers.get(
                                        "Content-Type", ""
                                    ),
                                )
                            return None
                    return None

                if resp.status == 200:
                    content = await resp.read()
                    return ManifestResult(
                        content=content,
                        digest=resp.headers.get("Docker-Content-Digest", ""),
                        content_type=resp.headers.get("Content-Type", ""),
                    )

                return None

    async def get_blob(self, name: str, digest: str) -> Optional[bytes]:
        """Fetch blob from upstream.

        Args:
            name: Image name
            digest: Blob digest

        Returns:
            Blob content if found, None otherwise
        """
        url = f"{self.url}/v2/{name}/blobs/{digest}"

        async with await self._get_session() as session:
            headers = {}

            async with session.get(url, headers=headers) as resp:
                if resp.status == 401:
                    www_auth = resp.headers.get("WWW-Authenticate", "")
                    token = await self._handle_auth_challenge(session, www_auth)
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        async with session.get(url, headers=headers) as auth_resp:
                            if auth_resp.status == 200:
                                return await auth_resp.read()
                            return None
                    return None

                if resp.status == 200:
                    return await resp.read()

                return None

    async def stream_blob(
        self, name: str, digest: str
    ) -> AsyncIterator[bytes]:
        """Stream blob from upstream.

        Args:
            name: Image name
            digest: Blob digest

        Yields:
            Blob content chunks
        """
        url = f"{self.url}/v2/{name}/blobs/{digest}"

        async with await self._get_session() as session:
            headers = {}

            async with session.get(url, headers=headers) as resp:
                if resp.status == 401:
                    www_auth = resp.headers.get("WWW-Authenticate", "")
                    token = await self._handle_auth_challenge(session, www_auth)
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        async with session.get(url, headers=headers) as auth_resp:
                            if auth_resp.status == 200:
                                async for chunk in auth_resp.content.iter_chunked(65536):
                                    yield chunk
                            return
                    return

                if resp.status == 200:
                    async for chunk in resp.content.iter_chunked(65536):
                        yield chunk
