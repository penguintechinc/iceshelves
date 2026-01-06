"""Cloud Provider Detection and Configuration REST API Endpoints.

This module provides REST API endpoints for cloud provider detection,
ingress options, storage classes, and managed services configuration.
"""

from dataclasses import dataclass
from typing import List, Optional

from flask import Blueprint, jsonify, request

from ..middleware import admin_required, auth_required, maintainer_or_admin_required

cloud_bp = Blueprint("cloud", __name__, url_prefix="/cloud")


@dataclass(slots=True)
class CloudDetectionResponse:
    """Response DTO for cloud provider detection."""
    provider: str
    region: Optional[str] = None
    confidence: float = 0.0
    metadata: Optional[dict] = None


@dataclass(slots=True)
class IngressOption:
    """Data class for ingress option."""
    name: str
    display_name: str
    description: str
    provider: str
    enabled: bool = True


@dataclass(slots=True)
class StorageClass:
    """Data class for storage class."""
    name: str
    provisioner: str
    type: str
    performance_tier: str
    description: str


@dataclass(slots=True)
class ManagedService:
    """Data class for managed service option."""
    service_id: str
    name: str
    service_type: str
    provider: str
    description: str
    availability: str


def get_aws_ingress_options() -> List[dict]:
    """Get AWS-specific ingress options."""
    return [
        {
            "name": "aws-alb",
            "display_name": "AWS Application Load Balancer",
            "description": "Layer 7 load balancing for HTTP/HTTPS traffic",
            "provider": "aws",
            "enabled": True,
            "controller": "aws-load-balancer-controller",
        },
        {
            "name": "aws-nlb",
            "display_name": "AWS Network Load Balancer",
            "description": "Layer 4 ultra-high performance load balancing",
            "provider": "aws",
            "enabled": True,
            "controller": "aws-load-balancer-controller",
        },
    ]


def get_gcp_ingress_options() -> List[dict]:
    """Get GCP-specific ingress options."""
    return [
        {
            "name": "gke-ingress",
            "display_name": "GKE Ingress",
            "description": "Google Cloud native Kubernetes ingress controller",
            "provider": "gcp",
            "enabled": True,
            "controller": "gke-ingress",
        },
        {
            "name": "gcp-alb",
            "display_name": "Google Cloud Application Load Balancer",
            "description": "Global application load balancing for distributed traffic",
            "provider": "gcp",
            "enabled": True,
            "controller": "gcp-alb-controller",
        },
    ]


def get_generic_ingress_options() -> List[dict]:
    """Get generic/cross-platform ingress options."""
    return [
        {
            "name": "nginx",
            "display_name": "NGINX Ingress Controller",
            "description": "Popular open-source NGINX ingress controller",
            "provider": "generic",
            "enabled": True,
            "controller": "ingress-nginx",
        },
        {
            "name": "traefik",
            "display_name": "Traefik Ingress Controller",
            "description": "Cloud-native edge router with dynamic configuration",
            "provider": "generic",
            "enabled": True,
            "controller": "traefik",
        },
        {
            "name": "clusterip",
            "display_name": "Kubernetes ClusterIP Service",
            "description": "Internal-only service accessible within cluster",
            "provider": "generic",
            "enabled": True,
            "controller": "kubernetes",
        },
        {
            "name": "nodeport",
            "display_name": "Kubernetes NodePort Service",
            "description": "External access via node ports (30000-32767)",
            "provider": "generic",
            "enabled": True,
            "controller": "kubernetes",
        },
        {
            "name": "loadbalancer",
            "display_name": "Kubernetes LoadBalancer Service",
            "description": "Cloud provider load balancer integration",
            "provider": "generic",
            "enabled": True,
            "controller": "kubernetes",
        },
    ]


def get_marchproxy_option() -> dict:
    """Get MarchProxy ingress option."""
    return {
        "name": "marchproxy",
        "display_name": "MarchProxy API Gateway",
        "description": "PenguinTech MarchProxy edge router and API gateway",
        "provider": "generic",
        "enabled": True,
        "controller": "marchproxy",
        "external": True,
    }


def get_aws_storage_classes() -> List[dict]:
    """Get AWS EBS storage classes."""
    return [
        {
            "name": "ebs-gp3",
            "provisioner": "ebs.csi.aws.com",
            "type": "block",
            "performance_tier": "high",
            "description": "General Purpose SSD (gp3) - balanced performance",
            "iops_range": "3000-16000",
            "throughput_range": "125-1000 MB/s",
        },
        {
            "name": "ebs-gp2",
            "provisioner": "ebs.csi.aws.com",
            "type": "block",
            "performance_tier": "medium",
            "description": "General Purpose SSD (gp2) - legacy",
            "iops_range": "100-16000",
            "throughput_range": "125-250 MB/s",
        },
        {
            "name": "ebs-io1",
            "provisioner": "ebs.csi.aws.com",
            "type": "block",
            "performance_tier": "ultra",
            "description": "Provisioned IOPS SSD (io1) - high performance",
            "iops_range": "100-64000",
            "throughput_range": "125-1000 MB/s",
        },
        {
            "name": "ebs-sc1",
            "provisioner": "ebs.csi.aws.com",
            "type": "block",
            "performance_tier": "low",
            "description": "Cold HDD (sc1) - infrequent access",
            "iops_range": "250-250",
            "throughput_range": "12.5-250 MB/s",
        },
    ]


def get_gcp_storage_classes() -> List[dict]:
    """Get GCP persistent disk storage classes."""
    return [
        {
            "name": "pd-ssd",
            "provisioner": "pd.csi.storage.gke.io",
            "type": "block",
            "performance_tier": "high",
            "description": "SSD persistent disk - high performance",
            "iops_range": "30000+",
            "throughput_range": "1200+ MB/s",
        },
        {
            "name": "pd-standard",
            "provisioner": "pd.csi.storage.gke.io",
            "type": "block",
            "performance_tier": "medium",
            "description": "Standard persistent disk - general purpose",
            "iops_range": "15000+",
            "throughput_range": "250+ MB/s",
        },
        {
            "name": "pd-balanced",
            "provisioner": "pd.csi.storage.gke.io",
            "type": "block",
            "performance_tier": "medium",
            "description": "Balanced persistent disk - cost optimized",
            "iops_range": "15000+",
            "throughput_range": "250+ MB/s",
        },
    ]


def get_generic_storage_classes() -> List[dict]:
    """Get generic storage classes for any Kubernetes cluster."""
    return [
        {
            "name": "local-storage",
            "provisioner": "kubernetes.io/no-provisioner",
            "type": "block",
            "performance_tier": "high",
            "description": "Local node storage - highest performance",
            "iops_range": "unlimited",
            "throughput_range": "unlimited",
        },
        {
            "name": "standard",
            "provisioner": "kubernetes.io/hostpath",
            "type": "block",
            "performance_tier": "low",
            "description": "Host path storage - development only",
            "iops_range": "variable",
            "throughput_range": "variable",
        },
    ]


def get_aws_managed_services() -> List[dict]:
    """Get AWS managed service options."""
    return [
        {
            "service_id": "aws-rds-mysql",
            "name": "AWS RDS for MySQL",
            "service_type": "database",
            "provider": "aws",
            "description": "Managed MySQL database on AWS RDS",
            "availability": "Multi-AZ with automatic failover",
            "engines": ["MySQL 5.7", "MySQL 8.0"],
            "max_storage": "65536 GB",
        },
        {
            "service_id": "aws-rds-postgresql",
            "name": "AWS RDS for PostgreSQL",
            "service_type": "database",
            "provider": "aws",
            "description": "Managed PostgreSQL database on AWS RDS",
            "availability": "Multi-AZ with automatic failover",
            "engines": ["PostgreSQL 12", "PostgreSQL 13", "PostgreSQL 14", "PostgreSQL 15"],
            "max_storage": "65536 GB",
        },
        {
            "service_id": "aws-elasticache-redis",
            "name": "AWS ElastiCache for Redis",
            "service_type": "cache",
            "provider": "aws",
            "description": "Managed Redis cache service",
            "availability": "Multi-AZ with automatic failover",
            "engines": ["Redis 6.x", "Redis 7.x"],
            "max_memory": "6 TB",
        },
        {
            "service_id": "aws-s3",
            "name": "AWS S3",
            "service_type": "storage",
            "provider": "aws",
            "description": "Object storage service for application data",
            "availability": "Multi-region replication available",
            "storage_classes": ["Standard", "Intelligent-Tiering", "Glacier"],
            "max_objects": "unlimited",
        },
    ]


def get_gcp_managed_services() -> List[dict]:
    """Get GCP managed service options."""
    return [
        {
            "service_id": "gcp-cloud-sql-mysql",
            "name": "Google Cloud SQL for MySQL",
            "service_type": "database",
            "provider": "gcp",
            "description": "Managed MySQL database on Google Cloud SQL",
            "availability": "High availability with automatic failover",
            "engines": ["MySQL 5.7", "MySQL 8.0"],
            "max_storage": "65536 GB",
        },
        {
            "service_id": "gcp-cloud-sql-postgresql",
            "name": "Google Cloud SQL for PostgreSQL",
            "service_type": "database",
            "provider": "gcp",
            "description": "Managed PostgreSQL database on Google Cloud SQL",
            "availability": "High availability with automatic failover",
            "engines": ["PostgreSQL 12", "PostgreSQL 13", "PostgreSQL 14", "PostgreSQL 15"],
            "max_storage": "65536 GB",
        },
        {
            "service_id": "gcp-memorystore-redis",
            "name": "Google Memorystore for Redis",
            "service_type": "cache",
            "provider": "gcp",
            "description": "Managed Redis cache service on Google Cloud",
            "availability": "Multi-zone replication available",
            "engines": ["Redis 6.x", "Redis 7.x"],
            "max_memory": "300 GB",
        },
        {
            "service_id": "gcp-gcs",
            "name": "Google Cloud Storage",
            "service_type": "storage",
            "provider": "gcp",
            "description": "Object storage service for application data",
            "availability": "Multi-region replication available",
            "storage_classes": ["Standard", "Nearline", "Coldline", "Archive"],
            "max_objects": "unlimited",
        },
    ]


def detect_cloud_provider(cluster_info: Optional[dict] = None) -> dict:
    """Detect cloud provider from cluster information.

    Args:
        cluster_info: Optional cluster metadata for detection.

    Returns:
        Dictionary with detected provider and confidence.
    """
    # Default detection logic
    if not cluster_info:
        return {
            "provider": "generic",
            "region": None,
            "confidence": 0.5,
            "metadata": {"reason": "No cluster info provided"},
        }

    provider = cluster_info.get("cloud_provider", "generic")
    region = cluster_info.get("region")
    confidence = 0.9 if provider != "generic" else 0.5

    return {
        "provider": provider,
        "region": region,
        "confidence": confidence,
        "metadata": {"detected_from": "cluster_info"},
    }


@cloud_bp.route("/detect", methods=["GET"])
@auth_required
def detect_cloud():
    """Detect cloud provider from cluster information.

    Query Parameters:
        cluster_id: Optional cluster ID for detection
        cluster_name: Optional cluster name for detection

    Returns:
        JSON with detected provider, region, and confidence.
    """
    from .models import get_cluster_by_id, get_cluster_by_name

    cluster_id = request.args.get("cluster_id", type=int)
    cluster_name = request.args.get("cluster_name", type=str)

    cluster_info = None

    if cluster_id:
        cluster_info = get_cluster_by_id(cluster_id)
    elif cluster_name:
        cluster_info = get_cluster_by_name(cluster_name)

    detection = detect_cloud_provider(cluster_info)

    return jsonify(detection), 200


@cloud_bp.route("/ingress-options", methods=["GET"])
@auth_required
def get_ingress_options():
    """Get ingress options based on detected or specified cloud provider.

    Query Parameters:
        provider: Cloud provider (aws, gcp, generic). Defaults to generic.
        include_marchproxy: Include MarchProxy option (default: true)

    Returns:
        JSON with available ingress options for the provider.
    """
    provider = request.args.get("provider", "generic").lower()
    include_marchproxy = request.args.get("include_marchproxy", "true").lower() == "true"

    # Validate provider
    valid_providers = ["aws", "gcp", "generic"]
    if provider not in valid_providers:
        return jsonify({
            "error": f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
        }), 400

    options = []

    # Add provider-specific options
    if provider == "aws":
        options.extend(get_aws_ingress_options())
    elif provider == "gcp":
        options.extend(get_gcp_ingress_options())

    # Add generic options
    options.extend(get_generic_ingress_options())

    # Add MarchProxy option if requested
    if include_marchproxy:
        options.append(get_marchproxy_option())

    return jsonify({
        "provider": provider,
        "options": options,
        "count": len(options),
    }), 200


@cloud_bp.route("/storage-classes", methods=["GET"])
@auth_required
def get_storage_classes_endpoint():
    """Get available storage classes for specified cloud provider.

    Query Parameters:
        provider: Cloud provider (aws, gcp, generic). Defaults to generic.

    Returns:
        JSON with available storage classes for the provider.
    """
    provider = request.args.get("provider", "generic").lower()

    # Validate provider
    valid_providers = ["aws", "gcp", "generic"]
    if provider not in valid_providers:
        return jsonify({
            "error": f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
        }), 400

    classes = []

    # Add provider-specific storage classes
    if provider == "aws":
        classes.extend(get_aws_storage_classes())
    elif provider == "gcp":
        classes.extend(get_gcp_storage_classes())
    else:
        classes.extend(get_generic_storage_classes())

    return jsonify({
        "provider": provider,
        "storage_classes": classes,
        "count": len(classes),
    }), 200


@cloud_bp.route("/managed-services", methods=["GET"])
@auth_required
def get_managed_services_endpoint():
    """Get available managed service options for specified cloud provider.

    Query Parameters:
        provider: Cloud provider (aws, gcp). Required.
        service_type: Filter by service type (database, cache, storage, messaging)

    Returns:
        JSON with available managed services for the provider.
    """
    provider = request.args.get("provider", "").lower()
    service_type = request.args.get("service_type", "").lower()

    # Validate provider
    valid_providers = ["aws", "gcp"]
    if not provider:
        return jsonify({
            "error": "Provider parameter is required"
        }), 400

    if provider not in valid_providers:
        return jsonify({
            "error": f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
        }), 400

    services = []

    # Add provider-specific managed services
    if provider == "aws":
        services.extend(get_aws_managed_services())
    elif provider == "gcp":
        services.extend(get_gcp_managed_services())

    # Filter by service type if specified
    if service_type:
        valid_types = ["database", "cache", "storage", "messaging"]
        if service_type not in valid_types:
            return jsonify({
                "error": f"Invalid service_type. Must be one of: {', '.join(valid_types)}"
            }), 400
        services = [s for s in services if s.get("service_type") == service_type]

    return jsonify({
        "provider": provider,
        "service_type": service_type if service_type else "all",
        "services": services,
        "count": len(services),
    }), 200
