"""Helm Chart Repository API routes.

Implements the Helm Chart Repository API for chart storage and retrieval.
"""

import io
import logging
import tarfile
from datetime import datetime, timezone
from typing import Optional

import yaml
from quart import Blueprint, Response, current_app, request

from app.auth.middleware import auth_required
from app.storage.s3 import get_storage

logger = logging.getLogger(__name__)

helm_bp = Blueprint("helm", __name__)


# =============================================================================
# Helm Repository Index
# =============================================================================


@helm_bp.route("/index.yaml", methods=["GET"])
async def get_index():
    """Get Helm repository index.yaml."""
    storage = get_storage()

    # Get all charts
    charts = await storage.list_charts()

    # Build index
    index = {
        "apiVersion": "v1",
        "generated": datetime.now(timezone.utc).isoformat(),
        "entries": {},
    }

    for chart_name, versions in charts.items():
        index["entries"][chart_name] = []

        for version in versions:
            # Get chart metadata
            chart_content = await storage.get_chart(chart_name, version)
            if chart_content:
                metadata = _extract_chart_metadata(chart_content)
                if metadata:
                    entry = {
                        "apiVersion": metadata.get("apiVersion", "v2"),
                        "name": chart_name,
                        "version": version,
                        "description": metadata.get("description", ""),
                        "urls": [f"/charts/{chart_name}-{version}.tgz"],
                        "created": datetime.now(timezone.utc).isoformat(),
                    }
                    if "appVersion" in metadata:
                        entry["appVersion"] = metadata["appVersion"]
                    if "icon" in metadata:
                        entry["icon"] = metadata["icon"]
                    if "keywords" in metadata:
                        entry["keywords"] = metadata["keywords"]
                    if "home" in metadata:
                        entry["home"] = metadata["home"]
                    if "sources" in metadata:
                        entry["sources"] = metadata["sources"]

                    index["entries"][chart_name].append(entry)

    # Return as YAML
    return Response(
        yaml.dump(index, default_flow_style=False),
        content_type="application/x-yaml",
    )


# =============================================================================
# Chart Download
# =============================================================================


@helm_bp.route("/charts/<filename>", methods=["GET"])
async def download_chart(filename: str):
    """Download a Helm chart tarball."""
    # Parse filename: {name}-{version}.tgz
    if not filename.endswith(".tgz"):
        return Response("Invalid chart filename", status=400)

    name_version = filename[:-4]  # Remove .tgz

    # Find the split point between name and version
    # Version typically starts with a digit after the last hyphen
    parts = name_version.rsplit("-", 1)
    if len(parts) != 2:
        return Response("Invalid chart filename format", status=400)

    chart_name, version = parts

    storage = get_storage()
    content = await storage.get_chart(chart_name, version)

    if content is None:
        return Response(status=404)

    return Response(
        content,
        content_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
        },
    )


# =============================================================================
# Chart Upload
# =============================================================================


@helm_bp.route("/api/v1/charts", methods=["POST"])
@auth_required(require_push=True)
async def upload_chart():
    """Upload a Helm chart."""
    # Get chart file from request
    files = await request.files
    if "chart" not in files:
        return Response("No chart file provided", status=400)

    chart_file = files["chart"]
    content = chart_file.read()

    # Extract chart metadata
    metadata = _extract_chart_metadata(content)
    if not metadata:
        return Response("Invalid chart: could not extract metadata", status=400)

    chart_name = metadata.get("name")
    version = metadata.get("version")

    if not chart_name or not version:
        return Response("Invalid chart: missing name or version", status=400)

    # Store chart
    storage = get_storage()
    await storage.put_chart(chart_name, version, content)

    return {
        "saved": True,
        "name": chart_name,
        "version": version,
    }, 201


# =============================================================================
# Chart Management API
# =============================================================================


@helm_bp.route("/api/v1/charts", methods=["GET"])
async def list_charts():
    """List all charts."""
    storage = get_storage()
    charts = await storage.list_charts()

    return {
        "charts": [
            {"name": name, "versions": versions}
            for name, versions in charts.items()
        ]
    }


@helm_bp.route("/api/v1/charts/<name>", methods=["GET"])
async def get_chart_versions(name: str):
    """Get all versions of a chart."""
    storage = get_storage()
    charts = await storage.list_charts()

    if name not in charts:
        return Response(status=404)

    return {
        "name": name,
        "versions": charts[name],
    }


@helm_bp.route("/api/v1/charts/<name>/<version>", methods=["GET"])
async def get_chart_info(name: str, version: str):
    """Get chart metadata."""
    storage = get_storage()
    content = await storage.get_chart(name, version)

    if content is None:
        return Response(status=404)

    metadata = _extract_chart_metadata(content)
    if not metadata:
        return Response("Could not extract metadata", status=500)

    return metadata


@helm_bp.route("/api/v1/charts/<name>/<version>", methods=["DELETE"])
@auth_required(require_push=True)
async def delete_chart(name: str, version: str):
    """Delete a chart."""
    storage = get_storage()
    deleted = await storage.delete_chart(name, version)

    if not deleted:
        return Response(status=404)

    return {"deleted": True}, 200


# =============================================================================
# Helper Functions
# =============================================================================


def _extract_chart_metadata(content: bytes) -> Optional[dict]:
    """Extract Chart.yaml metadata from a chart tarball."""
    try:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith("/Chart.yaml") or member.name == "Chart.yaml":
                    f = tar.extractfile(member)
                    if f:
                        return yaml.safe_load(f.read())
    except (tarfile.TarError, yaml.YAMLError) as e:
        logger.error(f"Failed to extract chart metadata: {e}")
    return None
