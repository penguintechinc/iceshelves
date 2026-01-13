"""OCI Distribution API routes.

Implements the OCI Distribution Specification for Docker Registry v2 API.
https://github.com/opencontainers/distribution-spec
"""

import hashlib
import logging
import uuid
from typing import Optional

from quart import Blueprint, Response, current_app, request

from app.storage.s3 import get_storage

logger = logging.getLogger(__name__)

registry_bp = Blueprint("registry", __name__)

# In-memory upload sessions (for chunked uploads)
# In production, this should be stored in Redis or similar
_upload_sessions: dict[str, dict] = {}


# =============================================================================
# API Version Check
# =============================================================================


@registry_bp.route("/v2/", methods=["GET"])
async def api_version():
    """OCI Distribution API version check."""
    return Response(
        "{}",
        status=200,
        content_type="application/json",
        headers={"Docker-Distribution-API-Version": "registry/2.0"},
    )


# =============================================================================
# Blob Operations
# =============================================================================


@registry_bp.route("/v2/<path:name>/blobs/<digest>", methods=["HEAD"])
async def blob_exists(name: str, digest: str):
    """Check if a blob exists."""
    storage = get_storage()

    size = await storage.get_blob_size(digest)
    if size is None:
        return Response(status=404)

    return Response(
        status=200,
        headers={
            "Content-Length": str(size),
            "Docker-Content-Digest": digest,
            "Content-Type": "application/octet-stream",
        },
    )


@registry_bp.route("/v2/<path:name>/blobs/<digest>", methods=["GET"])
async def get_blob(name: str, digest: str):
    """Get blob content."""
    storage = get_storage()

    content = await storage.get_blob(digest)
    if content is None:
        return Response(status=404)

    return Response(
        content,
        status=200,
        content_type="application/octet-stream",
        headers={
            "Content-Length": str(len(content)),
            "Docker-Content-Digest": digest,
        },
    )


@registry_bp.route("/v2/<path:name>/blobs/<digest>", methods=["DELETE"])
async def delete_blob(name: str, digest: str):
    """Delete a blob."""
    storage = get_storage()

    deleted = await storage.delete_blob(digest)
    if not deleted:
        return Response(status=404)

    return Response(status=202)


@registry_bp.route("/v2/<path:name>/blobs/uploads/", methods=["POST"])
async def initiate_blob_upload(name: str):
    """Initiate a blob upload session."""
    # Check for single-request monolithic upload
    digest = request.args.get("digest")
    if digest:
        # Monolithic upload - entire blob in this request
        content = await request.get_data()
        if content:
            storage = get_storage()
            try:
                await storage.put_blob(digest, content)
                location = f"/v2/{name}/blobs/{digest}"
                return Response(
                    status=201,
                    headers={
                        "Location": location,
                        "Docker-Content-Digest": digest,
                        "Content-Length": "0",
                    },
                )
            except ValueError as e:
                return Response(str(e), status=400)

    # Create upload session for chunked upload
    upload_id = str(uuid.uuid4())
    _upload_sessions[upload_id] = {
        "name": name,
        "chunks": [],
        "offset": 0,
    }

    location = f"/v2/{name}/blobs/uploads/{upload_id}"
    return Response(
        status=202,
        headers={
            "Location": location,
            "Range": "0-0",
            "Docker-Upload-UUID": upload_id,
        },
    )


@registry_bp.route("/v2/<path:name>/blobs/uploads/<upload_id>", methods=["PATCH"])
async def upload_blob_chunk(name: str, upload_id: str):
    """Upload a blob chunk."""
    if upload_id not in _upload_sessions:
        return Response(status=404)

    session = _upload_sessions[upload_id]
    content = await request.get_data()

    if content:
        session["chunks"].append(content)
        session["offset"] += len(content)

    location = f"/v2/{name}/blobs/uploads/{upload_id}"
    return Response(
        status=202,
        headers={
            "Location": location,
            "Range": f"0-{session['offset']}",
            "Docker-Upload-UUID": upload_id,
        },
    )


@registry_bp.route("/v2/<path:name>/blobs/uploads/<upload_id>", methods=["PUT"])
async def complete_blob_upload(name: str, upload_id: str):
    """Complete a blob upload."""
    digest = request.args.get("digest")
    if not digest:
        return Response("digest parameter required", status=400)

    if upload_id not in _upload_sessions:
        return Response(status=404)

    session = _upload_sessions[upload_id]

    # Get any final chunk from this request
    final_chunk = await request.get_data()
    if final_chunk:
        session["chunks"].append(final_chunk)

    # Combine all chunks
    content = b"".join(session["chunks"])

    # Store blob
    storage = get_storage()
    try:
        await storage.put_blob(digest, content)
    except ValueError as e:
        del _upload_sessions[upload_id]
        return Response(str(e), status=400)

    # Clean up session
    del _upload_sessions[upload_id]

    location = f"/v2/{name}/blobs/{digest}"
    return Response(
        status=201,
        headers={
            "Location": location,
            "Docker-Content-Digest": digest,
            "Content-Length": "0",
        },
    )


@registry_bp.route("/v2/<path:name>/blobs/uploads/<upload_id>", methods=["DELETE"])
async def cancel_blob_upload(name: str, upload_id: str):
    """Cancel a blob upload."""
    if upload_id in _upload_sessions:
        del _upload_sessions[upload_id]

    return Response(status=204)


# =============================================================================
# Manifest Operations
# =============================================================================


@registry_bp.route("/v2/<path:name>/manifests/<reference>", methods=["HEAD"])
async def manifest_exists(name: str, reference: str):
    """Check if a manifest exists."""
    storage = get_storage()

    result = await storage.get_manifest(name, reference)
    if result is None:
        return Response(status=404)

    content, digest = result

    return Response(
        status=200,
        headers={
            "Content-Length": str(len(content)),
            "Docker-Content-Digest": digest,
            "Content-Type": "application/vnd.oci.image.manifest.v1+json",
        },
    )


@registry_bp.route("/v2/<path:name>/manifests/<reference>", methods=["GET"])
async def get_manifest(name: str, reference: str):
    """Get a manifest."""
    storage = get_storage()

    result = await storage.get_manifest(name, reference)
    if result is None:
        return Response(status=404)

    content, digest = result

    # Determine content type from manifest
    import json
    try:
        manifest = json.loads(content)
        media_type = manifest.get(
            "mediaType", "application/vnd.oci.image.manifest.v1+json"
        )
    except json.JSONDecodeError:
        media_type = "application/vnd.oci.image.manifest.v1+json"

    return Response(
        content,
        status=200,
        content_type=media_type,
        headers={
            "Content-Length": str(len(content)),
            "Docker-Content-Digest": digest,
        },
    )


@registry_bp.route("/v2/<path:name>/manifests/<reference>", methods=["PUT"])
async def put_manifest(name: str, reference: str):
    """Store a manifest."""
    content = await request.get_data()
    if not content:
        return Response("empty manifest", status=400)

    storage = get_storage()
    digest = await storage.put_manifest(name, reference, content)

    location = f"/v2/{name}/manifests/{digest}"
    return Response(
        status=201,
        headers={
            "Location": location,
            "Docker-Content-Digest": digest,
            "Content-Length": "0",
        },
    )


@registry_bp.route("/v2/<path:name>/manifests/<reference>", methods=["DELETE"])
async def delete_manifest(name: str, reference: str):
    """Delete a manifest."""
    storage = get_storage()

    deleted = await storage.delete_manifest(name, reference)
    if not deleted:
        return Response(status=404)

    return Response(status=202)


# =============================================================================
# Tag Operations
# =============================================================================


@registry_bp.route("/v2/<path:name>/tags/list", methods=["GET"])
async def list_tags(name: str):
    """List tags for a repository."""
    storage = get_storage()

    tags = await storage.list_tags(name)

    # Handle pagination
    n = request.args.get("n", type=int)
    last = request.args.get("last")

    if last:
        try:
            start_idx = tags.index(last) + 1
            tags = tags[start_idx:]
        except ValueError:
            pass

    if n:
        tags = tags[:n]

    return {
        "name": name,
        "tags": tags,
    }


# =============================================================================
# Catalog Operations
# =============================================================================


@registry_bp.route("/v2/_catalog", methods=["GET"])
async def catalog():
    """List all repositories."""
    storage = get_storage()

    repos = await storage.list_repositories()

    # Handle pagination
    n = request.args.get("n", type=int)
    last = request.args.get("last")

    if last:
        try:
            start_idx = repos.index(last) + 1
            repos = repos[start_idx:]
        except ValueError:
            pass

    if n:
        repos = repos[:n]

    return {
        "repositories": repos,
    }
