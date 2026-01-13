"""Pull-through proxy handler.

Implements stale-while-revalidate caching strategy for proxying
images from upstream registries.
"""

import asyncio
import json
import logging
from typing import Optional

from app.config import Config, UpstreamRegistry as UpstreamConfig
from app.proxy.cache import CacheManager
from app.proxy.upstream import ManifestResult, RegistryAuth, UpstreamRegistry
from app.storage.s3 import S3Storage

logger = logging.getLogger(__name__)


class ProxyHandler:
    """Handles pull-through proxy requests with stale-while-revalidate caching."""

    def __init__(self, storage: S3Storage, config: Config):
        self.storage = storage
        self.config = config
        self.cache = CacheManager(storage, config)
        self._upstream_clients: dict[str, UpstreamRegistry] = {}

        # Initialize built-in upstream clients
        for upstream_config in config.builtin_upstreams:
            self._register_upstream(upstream_config)

    def _register_upstream(self, config: UpstreamConfig) -> None:
        """Register an upstream registry client."""
        import os

        auth = RegistryAuth(auth_type=config.auth_type)

        if config.auth_type == "basic":
            auth.username = config.username
            auth.password = config.password
        elif config.auth_type == "token":
            auth.token = config.token or os.getenv(config.token_env, "")

        self._upstream_clients[config.name] = UpstreamRegistry(
            name=config.name,
            url=config.url,
            auth=auth,
        )

    def get_upstream(self, name: str) -> Optional[UpstreamRegistry]:
        """Get upstream registry client by name."""
        return self._upstream_clients.get(name)

    def parse_proxy_request(self, name: str) -> Optional[tuple[str, str]]:
        """Parse image name to extract upstream registry and image name.

        Supports formats:
        - dockerhub/library/nginx -> (dockerhub, library/nginx)
        - ghcr/owner/repo -> (ghcr, owner/repo)
        - library/nginx -> (dockerhub, library/nginx)  # Default to Docker Hub

        Returns:
            (upstream_name, image_name) or None if not a proxy request
        """
        parts = name.split("/", 1)

        # Check if first part is a known upstream
        if len(parts) >= 2 and parts[0] in self._upstream_clients:
            return parts[0], parts[1]

        # Default to Docker Hub for standard library images
        if len(parts) == 1 or (len(parts) == 2 and parts[0] == "library"):
            return "dockerhub", f"library/{name}" if "/" not in name else name

        # Not a proxy request (local image)
        return None

    async def get_manifest(
        self, upstream_name: str, image_name: str, reference: str
    ) -> Optional[tuple[bytes, str]]:
        """Get manifest from upstream with stale-while-revalidate caching.

        Args:
            upstream_name: Name of upstream registry
            image_name: Image name on upstream
            reference: Tag or digest

        Returns:
            (manifest_content, digest) or None if not found
        """
        upstream = self.get_upstream(upstream_name)
        if not upstream:
            logger.error(f"Unknown upstream registry: {upstream_name}")
            return None

        # For digest references, check cache and return if found
        if reference.startswith("sha256:"):
            cached = await self.cache.get_cached_manifest(
                upstream_name, image_name, reference
            )
            if cached:
                return cached

            # Not cached, fetch from upstream
            result = await upstream.get_manifest(image_name, reference)
            if result:
                await self.cache.put_cached_manifest(
                    upstream_name, image_name, reference, result.content, result.digest
                )
                return result.content, result.digest
            return None

        # For tag references, use stale-while-revalidate
        cache_meta = await self.cache.get_cache_meta(
            upstream_name, image_name, reference
        )
        cached = await self.cache.get_cached_manifest(
            upstream_name, image_name, reference
        )

        if cached and cache_meta:
            # Cache hit - serve immediately
            if self.cache.should_revalidate(cache_meta):
                # Start async revalidation for mutable tags
                if not self.cache.is_revalidating(upstream_name, image_name, reference):
                    self.cache.start_revalidation(
                        upstream_name,
                        image_name,
                        reference,
                        self._revalidate(
                            upstream, upstream_name, image_name, reference, cache_meta.digest
                        ),
                    )

            return cached

        # Cache miss - fetch from upstream
        result = await upstream.get_manifest(image_name, reference)
        if result:
            await self.cache.put_cached_manifest(
                upstream_name, image_name, reference, result.content, result.digest
            )
            return result.content, result.digest

        return None

    async def _revalidate(
        self,
        upstream: UpstreamRegistry,
        upstream_name: str,
        image_name: str,
        tag: str,
        cached_digest: str,
    ) -> None:
        """Revalidate cache entry by checking upstream for updates.

        This runs asynchronously after serving cached content.
        """
        logger.debug(f"Revalidating {upstream_name}/{image_name}:{tag}")

        try:
            # Check upstream for current digest
            current_digest = await upstream.check_manifest(image_name, tag)

            if current_digest and current_digest != cached_digest:
                # Upstream has newer version - fetch and update cache
                logger.info(
                    f"Updating cache for {upstream_name}/{image_name}:{tag} "
                    f"(old: {cached_digest[:12]}, new: {current_digest[:12]})"
                )

                result = await upstream.get_manifest(image_name, tag)
                if result:
                    await self.cache.put_cached_manifest(
                        upstream_name, image_name, tag, result.content, result.digest
                    )

                    # Also cache any new blobs referenced by the manifest
                    await self._cache_manifest_blobs(
                        upstream, upstream_name, image_name, result.content
                    )
            else:
                # No update needed, just update check timestamp
                await self.cache.update_cache_check(upstream_name, image_name, tag)
                logger.debug(f"Cache still valid for {upstream_name}/{image_name}:{tag}")

        except Exception as e:
            logger.error(f"Revalidation error for {upstream_name}/{image_name}:{tag}: {e}")

    async def _cache_manifest_blobs(
        self,
        upstream: UpstreamRegistry,
        upstream_name: str,
        image_name: str,
        manifest_content: bytes,
    ) -> None:
        """Cache blobs referenced by a manifest."""
        try:
            manifest = json.loads(manifest_content)

            # Collect all blob digests from manifest
            digests = []

            # Config blob
            if "config" in manifest:
                digests.append(manifest["config"].get("digest"))

            # Layer blobs
            for layer in manifest.get("layers", []):
                digests.append(layer.get("digest"))

            # For manifest lists, we'd recurse into each platform manifest
            # but that's handled when those are requested

            # Filter out already cached blobs
            to_fetch = []
            for digest in digests:
                if digest and not await self.cache.blob_exists(digest):
                    to_fetch.append(digest)

            # Fetch missing blobs in parallel (limited concurrency)
            semaphore = asyncio.Semaphore(5)

            async def fetch_blob(digest: str):
                async with semaphore:
                    content = await upstream.get_blob(image_name, digest)
                    if content:
                        await self.cache.put_cached_blob(digest, content)

            await asyncio.gather(
                *[fetch_blob(d) for d in to_fetch],
                return_exceptions=True,
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse manifest for blob caching: {e}")

    async def get_blob(
        self, upstream_name: str, image_name: str, digest: str
    ) -> Optional[bytes]:
        """Get blob from upstream with caching.

        Blobs are content-addressable and cached forever.
        """
        # Check cache first
        cached = await self.cache.get_cached_blob(digest)
        if cached:
            return cached

        # Fetch from upstream
        upstream = self.get_upstream(upstream_name)
        if not upstream:
            return None

        content = await upstream.get_blob(image_name, digest)
        if content:
            await self.cache.put_cached_blob(digest, content)
            return content

        return None

    async def blob_exists(
        self, upstream_name: str, image_name: str, digest: str
    ) -> bool:
        """Check if blob exists in cache or upstream."""
        # Check cache first
        if await self.cache.blob_exists(digest):
            return True

        # Check upstream
        upstream = self.get_upstream(upstream_name)
        if not upstream:
            return False

        # For existence check, we just try to get the blob
        # A proper implementation would use HEAD request
        content = await upstream.get_blob(image_name, digest)
        if content:
            # Cache it since we fetched it
            await self.cache.put_cached_blob(digest, content)
            return True

        return False
