"""S3-compatible storage backend for repo-worker.

Supports MinIO, AWS S3, GCS, and other S3-compatible storage services.
"""

import asyncio
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from aiobotocore.session import get_session
from botocore.exceptions import ClientError

from app.config import S3Config

logger = logging.getLogger(__name__)

# Global storage instance
_storage: Optional["S3Storage"] = None


def get_storage() -> "S3Storage":
    """Get the global storage instance."""
    if _storage is None:
        raise RuntimeError("Storage not initialized. Call set_storage() first.")
    return _storage


def set_storage(storage: "S3Storage") -> None:
    """Set the global storage instance."""
    global _storage
    _storage = storage


class S3Storage:
    """S3-compatible storage backend."""

    def __init__(self, config: S3Config):
        self.config = config
        self._session = get_session()

    @asynccontextmanager
    async def _get_client(self):
        """Get an S3 client context manager."""
        async with self._session.create_client(
            "s3",
            endpoint_url=self.config.endpoint,
            aws_access_key_id=self.config.access_key,
            aws_secret_access_key=self.config.secret_key,
            region_name=self.config.region or "us-east-1",
            use_ssl=self.config.use_ssl,
        ) as client:
            yield client

    async def check_connection(self) -> bool:
        """Check if S3 connection is working."""
        async with self._get_client() as client:
            await client.head_bucket(Bucket=self.config.bucket)
        return True

    async def ensure_bucket_exists(self) -> None:
        """Create the bucket if it doesn't exist."""
        async with self._get_client() as client:
            try:
                await client.head_bucket(Bucket=self.config.bucket)
                logger.info(f"Bucket '{self.config.bucket}' exists")
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                if error_code in ("404", "NoSuchBucket"):
                    logger.info(f"Creating bucket '{self.config.bucket}'")
                    await client.create_bucket(Bucket=self.config.bucket)
                else:
                    raise

    # =========================================================================
    # Blob operations (content-addressable storage)
    # =========================================================================

    def _blob_key(self, digest: str) -> str:
        """Get S3 key for a blob by digest."""
        # Format: blobs/sha256/ab/abcdef123...
        algo, hash_value = digest.split(":", 1) if ":" in digest else ("sha256", digest)
        return f"blobs/{algo}/{hash_value[:2]}/{hash_value}"

    async def blob_exists(self, digest: str) -> bool:
        """Check if a blob exists."""
        async with self._get_client() as client:
            try:
                await client.head_object(Bucket=self.config.bucket, Key=self._blob_key(digest))
                return True
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return False
                raise

    async def get_blob(self, digest: str) -> Optional[bytes]:
        """Get blob content by digest."""
        async with self._get_client() as client:
            try:
                response = await client.get_object(
                    Bucket=self.config.bucket, Key=self._blob_key(digest)
                )
                async with response["Body"] as stream:
                    return await stream.read()
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return None
                raise

    async def get_blob_stream(self, digest: str) -> AsyncIterator[bytes]:
        """Stream blob content by digest."""
        async with self._get_client() as client:
            try:
                response = await client.get_object(
                    Bucket=self.config.bucket, Key=self._blob_key(digest)
                )
                async with response["Body"] as stream:
                    while chunk := await stream.read(65536):  # 64KB chunks
                        yield chunk
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return
                raise

    async def get_blob_size(self, digest: str) -> Optional[int]:
        """Get blob size by digest."""
        async with self._get_client() as client:
            try:
                response = await client.head_object(
                    Bucket=self.config.bucket, Key=self._blob_key(digest)
                )
                return response["ContentLength"]
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return None
                raise

    async def put_blob(self, digest: str, content: bytes) -> None:
        """Store blob content."""
        # Verify digest matches content
        computed = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if digest != computed:
            raise ValueError(f"Digest mismatch: expected {digest}, got {computed}")

        async with self._get_client() as client:
            await client.put_object(
                Bucket=self.config.bucket,
                Key=self._blob_key(digest),
                Body=content,
                ContentType="application/octet-stream",
            )

    async def put_blob_stream(
        self, digest: str, stream: AsyncIterator[bytes], size: int
    ) -> None:
        """Store blob from async stream."""
        # For streaming uploads, we need to collect chunks and verify
        chunks = []
        hasher = hashlib.sha256()

        async for chunk in stream:
            chunks.append(chunk)
            hasher.update(chunk)

        content = b"".join(chunks)
        computed = f"sha256:{hasher.hexdigest()}"

        if digest != computed:
            raise ValueError(f"Digest mismatch: expected {digest}, got {computed}")

        async with self._get_client() as client:
            await client.put_object(
                Bucket=self.config.bucket,
                Key=self._blob_key(digest),
                Body=content,
                ContentType="application/octet-stream",
            )

    async def delete_blob(self, digest: str) -> bool:
        """Delete a blob. Returns True if deleted, False if not found."""
        async with self._get_client() as client:
            try:
                await client.delete_object(Bucket=self.config.bucket, Key=self._blob_key(digest))
                return True
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return False
                raise

    # =========================================================================
    # Manifest operations
    # =========================================================================

    def _manifest_key(self, name: str, reference: str) -> str:
        """Get S3 key for a manifest."""
        # Reference can be a tag or digest
        if reference.startswith("sha256:"):
            return f"repositories/{name}/_manifests/revisions/{reference}"
        return f"repositories/{name}/_manifests/tags/{reference}/current"

    def _tag_link_key(self, name: str, tag: str) -> str:
        """Get S3 key for tag -> digest link."""
        return f"repositories/{name}/_manifests/tags/{tag}/link"

    async def get_manifest(self, name: str, reference: str) -> Optional[tuple[bytes, str]]:
        """Get manifest by name and reference (tag or digest).

        Returns (content, digest) or None if not found.
        """
        async with self._get_client() as client:
            # If reference is a tag, resolve to digest first
            if not reference.startswith("sha256:"):
                link_key = self._tag_link_key(name, reference)
                try:
                    response = await client.get_object(
                        Bucket=self.config.bucket, Key=link_key
                    )
                    async with response["Body"] as stream:
                        digest = (await stream.read()).decode().strip()
                except ClientError as e:
                    if e.response.get("Error", {}).get("Code") == "404":
                        return None
                    raise
            else:
                digest = reference

            # Get manifest content
            manifest_key = f"repositories/{name}/_manifests/revisions/{digest}/content"
            try:
                response = await client.get_object(
                    Bucket=self.config.bucket, Key=manifest_key
                )
                async with response["Body"] as stream:
                    content = await stream.read()
                return content, digest
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return None
                raise

    async def put_manifest(self, name: str, reference: str, content: bytes) -> str:
        """Store manifest. Returns digest."""
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"

        async with self._get_client() as client:
            # Store manifest content by digest
            manifest_key = f"repositories/{name}/_manifests/revisions/{digest}/content"
            await client.put_object(
                Bucket=self.config.bucket,
                Key=manifest_key,
                Body=content,
                ContentType="application/vnd.oci.image.manifest.v1+json",
            )

            # If reference is a tag, create tag -> digest link
            if not reference.startswith("sha256:"):
                link_key = self._tag_link_key(name, reference)
                await client.put_object(
                    Bucket=self.config.bucket,
                    Key=link_key,
                    Body=digest.encode(),
                    ContentType="text/plain",
                )

        return digest

    async def delete_manifest(self, name: str, reference: str) -> bool:
        """Delete manifest. Returns True if deleted."""
        async with self._get_client() as client:
            try:
                # If reference is a tag, delete the link
                if not reference.startswith("sha256:"):
                    link_key = self._tag_link_key(name, reference)
                    await client.delete_object(Bucket=self.config.bucket, Key=link_key)
                else:
                    # Delete manifest content
                    manifest_key = f"repositories/{name}/_manifests/revisions/{reference}/content"
                    await client.delete_object(Bucket=self.config.bucket, Key=manifest_key)
                return True
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return False
                raise

    async def list_tags(self, name: str) -> list[str]:
        """List all tags for a repository."""
        async with self._get_client() as client:
            tags = []
            prefix = f"repositories/{name}/_manifests/tags/"
            paginator = client.get_paginator("list_objects_v2")

            async for page in paginator.paginate(
                Bucket=self.config.bucket, Prefix=prefix, Delimiter="/"
            ):
                for common_prefix in page.get("CommonPrefixes", []):
                    tag = common_prefix["Prefix"][len(prefix):].rstrip("/")
                    tags.append(tag)

            return sorted(tags)

    # =========================================================================
    # Repository catalog
    # =========================================================================

    async def list_repositories(self) -> list[str]:
        """List all repositories."""
        async with self._get_client() as client:
            repos = set()
            prefix = "repositories/"
            paginator = client.get_paginator("list_objects_v2")

            async for page in paginator.paginate(
                Bucket=self.config.bucket, Prefix=prefix
            ):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    # Extract repository name from key
                    parts = key[len(prefix):].split("/")
                    if len(parts) >= 2:
                        # Handle namespaced repos like "library/nginx"
                        if parts[1] == "_manifests" or parts[1] == "_layers":
                            repos.add(parts[0])
                        elif len(parts) >= 3 and (
                            parts[2] == "_manifests" or parts[2] == "_layers"
                        ):
                            repos.add(f"{parts[0]}/{parts[1]}")

            return sorted(repos)

    # =========================================================================
    # Helm chart operations
    # =========================================================================

    def _chart_key(self, name: str, version: str) -> str:
        """Get S3 key for a Helm chart."""
        return f"charts/{name}/{name}-{version}.tgz"

    async def get_chart(self, name: str, version: str) -> Optional[bytes]:
        """Get Helm chart content."""
        async with self._get_client() as client:
            try:
                response = await client.get_object(
                    Bucket=self.config.bucket, Key=self._chart_key(name, version)
                )
                async with response["Body"] as stream:
                    return await stream.read()
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return None
                raise

    async def put_chart(self, name: str, version: str, content: bytes) -> None:
        """Store Helm chart."""
        async with self._get_client() as client:
            await client.put_object(
                Bucket=self.config.bucket,
                Key=self._chart_key(name, version),
                Body=content,
                ContentType="application/gzip",
            )

    async def delete_chart(self, name: str, version: str) -> bool:
        """Delete Helm chart."""
        async with self._get_client() as client:
            try:
                await client.delete_object(
                    Bucket=self.config.bucket, Key=self._chart_key(name, version)
                )
                return True
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return False
                raise

    async def list_charts(self) -> dict[str, list[str]]:
        """List all charts and their versions."""
        async with self._get_client() as client:
            charts: dict[str, list[str]] = {}
            prefix = "charts/"
            paginator = client.get_paginator("list_objects_v2")

            async for page in paginator.paginate(
                Bucket=self.config.bucket, Prefix=prefix
            ):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    # Extract chart name and version from key
                    # Format: charts/{name}/{name}-{version}.tgz
                    parts = key[len(prefix):].split("/")
                    if len(parts) == 2:
                        chart_name = parts[0]
                        filename = parts[1]
                        if filename.endswith(".tgz"):
                            # Extract version from filename
                            version = filename[len(chart_name) + 1:-4]  # Remove "{name}-" and ".tgz"
                            if chart_name not in charts:
                                charts[chart_name] = []
                            charts[chart_name].append(version)

            # Sort versions
            for chart_name in charts:
                charts[chart_name].sort()

            return charts

    # =========================================================================
    # Cache metadata operations
    # =========================================================================

    async def get_cache_meta(
        self, upstream: str, name: str, tag: str
    ) -> Optional[dict]:
        """Get cache metadata for a proxied image."""
        key = f"cache/{upstream}/{name}/{tag}/meta.json"
        async with self._get_client() as client:
            try:
                response = await client.get_object(
                    Bucket=self.config.bucket, Key=key
                )
                async with response["Body"] as stream:
                    content = await stream.read()
                return json.loads(content)
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return None
                raise

    async def put_cache_meta(
        self, upstream: str, name: str, tag: str, meta: dict
    ) -> None:
        """Store cache metadata for a proxied image."""
        key = f"cache/{upstream}/{name}/{tag}/meta.json"
        async with self._get_client() as client:
            await client.put_object(
                Bucket=self.config.bucket,
                Key=key,
                Body=json.dumps(meta).encode(),
                ContentType="application/json",
            )
