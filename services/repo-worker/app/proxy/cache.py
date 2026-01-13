"""Cache management for pull-through proxy.

Implements stale-while-revalidate caching strategy:
- Mutable tags (latest, *nightly*): Serve from cache immediately, async revalidate
- Immutable tags: Cache forever, no revalidation
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from app.config import Config
from app.storage.s3 import S3Storage

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cached manifest entry metadata."""
    digest: str
    mutable: bool
    last_check: float  # Unix timestamp
    last_updated: float  # Unix timestamp


class CacheManager:
    """Manages caching for pull-through proxy."""

    def __init__(self, storage: S3Storage, config: Config):
        self.storage = storage
        self.config = config
        self._revalidation_tasks: dict[str, asyncio.Task] = {}

    def _cache_key(self, upstream: str, name: str, tag: str) -> str:
        """Generate cache key for a proxied image."""
        return f"{upstream}/{name}:{tag}"

    async def get_cached_manifest(
        self, upstream: str, name: str, tag: str
    ) -> Optional[tuple[bytes, str]]:
        """Get cached manifest if available.

        Returns:
            (content, digest) if cached, None otherwise
        """
        result = await self.storage.get_manifest(f"_proxy/{upstream}/{name}", tag)
        return result

    async def get_cache_meta(
        self, upstream: str, name: str, tag: str
    ) -> Optional[CacheEntry]:
        """Get cache metadata for a proxied image."""
        meta = await self.storage.get_cache_meta(upstream, name, tag)
        if meta:
            return CacheEntry(
                digest=meta.get("digest", ""),
                mutable=meta.get("mutable", False),
                last_check=meta.get("last_check", 0),
                last_updated=meta.get("last_updated", 0),
            )
        return None

    async def put_cached_manifest(
        self,
        upstream: str,
        name: str,
        tag: str,
        content: bytes,
        digest: str,
    ) -> None:
        """Cache a manifest."""
        # Store manifest
        repo_name = f"_proxy/{upstream}/{name}"
        await self.storage.put_manifest(repo_name, tag, content)

        # Update cache metadata
        is_mutable = self.config.is_mutable_tag(tag)
        now = time.time()
        await self.storage.put_cache_meta(
            upstream,
            name,
            tag,
            {
                "digest": digest,
                "mutable": is_mutable,
                "last_check": now,
                "last_updated": now,
            },
        )

    async def update_cache_check(
        self, upstream: str, name: str, tag: str
    ) -> None:
        """Update the last_check timestamp for a cache entry."""
        meta = await self.storage.get_cache_meta(upstream, name, tag)
        if meta:
            meta["last_check"] = time.time()
            await self.storage.put_cache_meta(upstream, name, tag, meta)

    def should_revalidate(self, cache_entry: CacheEntry) -> bool:
        """Check if a cache entry should be revalidated.

        Mutable tags are always revalidated.
        Immutable tags are never revalidated (cached forever).
        """
        if not cache_entry.mutable:
            return False  # Immutable tags cached forever
        return True  # Always revalidate mutable tags

    def is_revalidating(self, upstream: str, name: str, tag: str) -> bool:
        """Check if revalidation is already in progress."""
        key = self._cache_key(upstream, name, tag)
        task = self._revalidation_tasks.get(key)
        return task is not None and not task.done()

    def start_revalidation(
        self,
        upstream: str,
        name: str,
        tag: str,
        revalidate_coro,
    ) -> None:
        """Start async revalidation task.

        Args:
            upstream: Upstream registry name
            name: Image name
            tag: Image tag
            revalidate_coro: Coroutine to run for revalidation
        """
        key = self._cache_key(upstream, name, tag)

        # Don't start if already revalidating
        if self.is_revalidating(upstream, name, tag):
            return

        # Create and store task
        task = asyncio.create_task(self._revalidate_wrapper(key, revalidate_coro))
        self._revalidation_tasks[key] = task

    async def _revalidate_wrapper(self, key: str, coro) -> None:
        """Wrapper for revalidation that handles cleanup."""
        try:
            await coro
        except Exception as e:
            logger.error(f"Revalidation failed for {key}: {e}")
        finally:
            # Clean up task reference
            if key in self._revalidation_tasks:
                del self._revalidation_tasks[key]

    async def get_cached_blob(self, digest: str) -> Optional[bytes]:
        """Get cached blob.

        Blobs are content-addressable and cached forever.
        """
        return await self.storage.get_blob(digest)

    async def put_cached_blob(self, digest: str, content: bytes) -> None:
        """Cache a blob.

        Blobs are content-addressable and cached forever.
        """
        await self.storage.put_blob(digest, content)

    async def blob_exists(self, digest: str) -> bool:
        """Check if blob is cached."""
        return await self.storage.blob_exists(digest)
