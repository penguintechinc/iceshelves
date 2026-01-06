"""Kubernetes client wrapper for marketplace operations.

This module provides a Kubernetes client wrapper using the kubernetes Python library
with dataclasses for DTOs and comprehensive cluster interaction capabilities.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import yaml

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NamespaceInfo:
    """Namespace information DTO."""

    name: str
    status: str
    creation_timestamp: str


@dataclass(slots=True)
class DeploymentStatus:
    """Deployment status information DTO."""

    name: str
    namespace: str
    replicas: int
    available_replicas: int
    ready_replicas: int
    updated_replicas: int
    conditions: List[Dict[str, Any]]


@dataclass(slots=True)
class StorageClassInfo:
    """Storage class information DTO."""

    name: str
    provisioner: str
    reclaim_policy: str
    volume_binding_mode: str
    is_default: bool


@dataclass(slots=True)
class IngressControllerInfo:
    """Ingress controller detection result DTO."""

    detected: bool
    controller_type: Optional[str]
    namespace: Optional[str]
    version: Optional[str]


@dataclass(slots=True)
class CloudProviderInfo:
    """Cloud provider detection result DTO."""

    detected: bool
    provider: Optional[str]
    region: Optional[str]
    metadata: Dict[str, str]


class K8sClient:
    """Kubernetes client wrapper for marketplace operations."""

    def __init__(self, kubeconfig: Optional[str] = None) -> None:
        """Initialize Kubernetes client.

        Args:
            kubeconfig: Path to kubeconfig file. If None, uses default config loading.
        """
        try:
            if kubeconfig:
                config.load_kube_config(config_file=kubeconfig)
            else:
                # Try in-cluster config first, then fallback to default kubeconfig
                try:
                    config.load_incluster_config()
                    logger.info("Loaded in-cluster Kubernetes configuration")
                except config.ConfigException:
                    config.load_kube_config()
                    logger.info("Loaded Kubernetes configuration from default kubeconfig")

            self.core_v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self.storage_v1 = client.StorageV1Api()
            self.networking_v1 = client.NetworkingV1Api()
            self.version_api = client.VersionApi()
            self.api_client = client.ApiClient()

        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            raise

    def list_namespaces(self) -> List[NamespaceInfo]:
        """List all namespaces in the cluster.

        Returns:
            List of NamespaceInfo objects.
        """
        try:
            namespaces = self.core_v1.list_namespace()
            return [
                NamespaceInfo(
                    name=ns.metadata.name,
                    status=ns.status.phase,
                    creation_timestamp=ns.metadata.creation_timestamp.isoformat()
                    if ns.metadata.creation_timestamp
                    else "",
                )
                for ns in namespaces.items
            ]
        except ApiException as e:
            logger.error(f"Failed to list namespaces: {e}")
            raise

    def get_deployment_status(
        self, name: str, namespace: str = "default"
    ) -> Optional[DeploymentStatus]:
        """Get deployment status with replica information.

        Args:
            name: Deployment name.
            namespace: Namespace containing the deployment.

        Returns:
            DeploymentStatus object or None if not found.
        """
        try:
            deployment = self.apps_v1.read_namespaced_deployment(
                name=name, namespace=namespace
            )

            conditions = []
            if deployment.status.conditions:
                conditions = [
                    {
                        "type": cond.type,
                        "status": cond.status,
                        "reason": cond.reason,
                        "message": cond.message,
                        "last_update_time": cond.last_update_time.isoformat()
                        if cond.last_update_time
                        else None,
                    }
                    for cond in deployment.status.conditions
                ]

            return DeploymentStatus(
                name=deployment.metadata.name,
                namespace=deployment.metadata.namespace,
                replicas=deployment.status.replicas or 0,
                available_replicas=deployment.status.available_replicas or 0,
                ready_replicas=deployment.status.ready_replicas or 0,
                updated_replicas=deployment.status.updated_replicas or 0,
                conditions=conditions,
            )
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Deployment {name} not found in namespace {namespace}")
                return None
            logger.error(f"Failed to get deployment status: {e}")
            raise

    def get_pod_logs(
        self,
        name: str,
        namespace: str = "default",
        container: Optional[str] = None,
        tail_lines: int = 100,
    ) -> str:
        """Get pod logs.

        Args:
            name: Pod name.
            namespace: Namespace containing the pod.
            container: Container name (optional, uses first container if not specified).
            tail_lines: Number of lines to retrieve from the end of the logs.

        Returns:
            Pod logs as string.
        """
        try:
            logs = self.core_v1.read_namespaced_pod_log(
                name=name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines,
            )
            return logs
        except ApiException as e:
            logger.error(f"Failed to get pod logs for {name}: {e}")
            raise

    def apply_manifest(self, manifest_yaml: str) -> Dict[str, Any]:
        """Apply Kubernetes manifest.

        Args:
            manifest_yaml: YAML manifest content.

        Returns:
            Dictionary with applied resources information.
        """
        try:
            manifests = list(yaml.safe_load_all(manifest_yaml))
            applied_resources = []

            for manifest in manifests:
                if not manifest:
                    continue

                kind = manifest.get("kind")
                api_version = manifest.get("apiVersion")
                metadata = manifest.get("metadata", {})
                name = metadata.get("name")
                namespace = metadata.get("namespace", "default")

                # Use dynamic client to apply the manifest
                try:
                    # This is a simplified version - production code should use
                    # kubernetes.dynamic for better handling of all resource types
                    if kind == "Namespace":
                        self.core_v1.create_namespace(body=manifest)
                    elif kind == "Deployment":
                        self.apps_v1.create_namespaced_deployment(
                            namespace=namespace, body=manifest
                        )
                    elif kind == "Service":
                        self.core_v1.create_namespaced_service(
                            namespace=namespace, body=manifest
                        )
                    elif kind == "ConfigMap":
                        self.core_v1.create_namespaced_config_map(
                            namespace=namespace, body=manifest
                        )
                    elif kind == "Secret":
                        self.core_v1.create_namespaced_secret(
                            namespace=namespace, body=manifest
                        )
                    else:
                        logger.warning(
                            f"Unsupported resource kind: {kind} - skipping"
                        )
                        continue

                    applied_resources.append(
                        {
                            "kind": kind,
                            "name": name,
                            "namespace": namespace,
                            "status": "created",
                        }
                    )
                    logger.info(f"Applied {kind}/{name} in namespace {namespace}")

                except ApiException as e:
                    if e.status == 409:  # Already exists, try to update
                        logger.info(
                            f"Resource {kind}/{name} already exists, attempting update"
                        )
                        # Update logic would go here
                        applied_resources.append(
                            {
                                "kind": kind,
                                "name": name,
                                "namespace": namespace,
                                "status": "already_exists",
                            }
                        )
                    else:
                        raise

            return {"applied_resources": applied_resources, "total": len(applied_resources)}

        except Exception as e:
            logger.error(f"Failed to apply manifest: {e}")
            raise

    def delete_manifest(self, manifest_yaml: str) -> Dict[str, Any]:
        """Delete resources defined in Kubernetes manifest.

        Args:
            manifest_yaml: YAML manifest content.

        Returns:
            Dictionary with deleted resources information.
        """
        try:
            manifests = list(yaml.safe_load_all(manifest_yaml))
            deleted_resources = []

            for manifest in manifests:
                if not manifest:
                    continue

                kind = manifest.get("kind")
                metadata = manifest.get("metadata", {})
                name = metadata.get("name")
                namespace = metadata.get("namespace", "default")

                try:
                    if kind == "Namespace":
                        self.core_v1.delete_namespace(name=name)
                    elif kind == "Deployment":
                        self.apps_v1.delete_namespaced_deployment(
                            name=name, namespace=namespace
                        )
                    elif kind == "Service":
                        self.core_v1.delete_namespaced_service(
                            name=name, namespace=namespace
                        )
                    elif kind == "ConfigMap":
                        self.core_v1.delete_namespaced_config_map(
                            name=name, namespace=namespace
                        )
                    elif kind == "Secret":
                        self.core_v1.delete_namespaced_secret(
                            name=name, namespace=namespace
                        )
                    else:
                        logger.warning(
                            f"Unsupported resource kind: {kind} - skipping"
                        )
                        continue

                    deleted_resources.append(
                        {
                            "kind": kind,
                            "name": name,
                            "namespace": namespace,
                            "status": "deleted",
                        }
                    )
                    logger.info(f"Deleted {kind}/{name} from namespace {namespace}")

                except ApiException as e:
                    if e.status == 404:
                        logger.warning(f"Resource {kind}/{name} not found - skipping")
                        deleted_resources.append(
                            {
                                "kind": kind,
                                "name": name,
                                "namespace": namespace,
                                "status": "not_found",
                            }
                        )
                    else:
                        raise

            return {"deleted_resources": deleted_resources, "total": len(deleted_resources)}

        except Exception as e:
            logger.error(f"Failed to delete manifest resources: {e}")
            raise

    def get_cluster_version(self) -> str:
        """Get Kubernetes cluster version.

        Returns:
            Cluster version string.
        """
        try:
            version_info = self.version_api.get_code()
            return f"{version_info.major}.{version_info.minor}"
        except ApiException as e:
            logger.error(f"Failed to get cluster version: {e}")
            raise

    def get_storage_classes(self) -> List[StorageClassInfo]:
        """List all storage classes in the cluster.

        Returns:
            List of StorageClassInfo objects.
        """
        try:
            storage_classes = self.storage_v1.list_storage_class()
            return [
                StorageClassInfo(
                    name=sc.metadata.name,
                    provisioner=sc.provisioner,
                    reclaim_policy=sc.reclaim_policy or "Delete",
                    volume_binding_mode=sc.volume_binding_mode or "Immediate",
                    is_default=(
                        sc.metadata.annotations.get(
                            "storageclass.kubernetes.io/is-default-class"
                        )
                        == "true"
                        if sc.metadata.annotations
                        else False
                    ),
                )
                for sc in storage_classes.items
            ]
        except ApiException as e:
            logger.error(f"Failed to list storage classes: {e}")
            raise

    def detect_ingress_controller(self) -> IngressControllerInfo:
        """Detect installed ingress controller.

        Returns:
            IngressControllerInfo object with detection results.
        """
        try:
            # Check common ingress controller namespaces and deployments
            ingress_controllers = [
                ("ingress-nginx", "nginx"),
                ("traefik", "traefik"),
                ("kong", "kong"),
                ("haproxy-controller", "haproxy"),
            ]

            for namespace, controller_type in ingress_controllers:
                try:
                    deployments = self.apps_v1.list_namespaced_deployment(
                        namespace=namespace
                    )
                    if deployments.items:
                        deployment = deployments.items[0]
                        version = (
                            deployment.metadata.labels.get("version")
                            or deployment.metadata.labels.get("app.kubernetes.io/version")
                            or "unknown"
                        )
                        return IngressControllerInfo(
                            detected=True,
                            controller_type=controller_type,
                            namespace=namespace,
                            version=version,
                        )
                except ApiException:
                    continue

            # If not found in dedicated namespaces, check all namespaces
            all_deployments = self.apps_v1.list_deployment_for_all_namespaces()
            for deployment in all_deployments.items:
                labels = deployment.metadata.labels or {}
                name_lower = deployment.metadata.name.lower()

                if any(
                    ing in name_lower
                    for ing in ["ingress", "nginx", "traefik", "kong", "haproxy"]
                ):
                    controller_type = "nginx" if "nginx" in name_lower else "unknown"
                    if "traefik" in name_lower:
                        controller_type = "traefik"
                    elif "kong" in name_lower:
                        controller_type = "kong"
                    elif "haproxy" in name_lower:
                        controller_type = "haproxy"

                    return IngressControllerInfo(
                        detected=True,
                        controller_type=controller_type,
                        namespace=deployment.metadata.namespace,
                        version=labels.get("version", "unknown"),
                    )

            return IngressControllerInfo(
                detected=False,
                controller_type=None,
                namespace=None,
                version=None,
            )

        except ApiException as e:
            logger.error(f"Failed to detect ingress controller: {e}")
            return IngressControllerInfo(
                detected=False,
                controller_type=None,
                namespace=None,
                version=None,
            )

    def detect_cloud_provider(self) -> CloudProviderInfo:
        """Detect cloud provider from node labels and metadata.

        Returns:
            CloudProviderInfo object with detection results.
        """
        try:
            nodes = self.core_v1.list_node()
            if not nodes.items:
                return CloudProviderInfo(
                    detected=False, provider=None, region=None, metadata={}
                )

            # Check first node for cloud provider labels
            node = nodes.items[0]
            labels = node.metadata.labels or {}

            # AWS detection
            if "eks.amazonaws.com/nodegroup" in labels or "node.kubernetes.io/instance-type" in labels:
                region = labels.get("topology.kubernetes.io/region") or labels.get(
                    "failure-domain.beta.kubernetes.io/region"
                )
                return CloudProviderInfo(
                    detected=True,
                    provider="aws",
                    region=region,
                    metadata={
                        "instance_type": labels.get("node.kubernetes.io/instance-type", ""),
                        "zone": labels.get("topology.kubernetes.io/zone", ""),
                    },
                )

            # GCP detection
            if "cloud.google.com/gke-nodepool" in labels:
                region = labels.get("topology.kubernetes.io/region") or labels.get(
                    "failure-domain.beta.kubernetes.io/region"
                )
                return CloudProviderInfo(
                    detected=True,
                    provider="gcp",
                    region=region,
                    metadata={
                        "instance_type": labels.get("node.kubernetes.io/instance-type", ""),
                        "zone": labels.get("topology.kubernetes.io/zone", ""),
                        "nodepool": labels.get("cloud.google.com/gke-nodepool", ""),
                    },
                )

            # Azure detection
            if "kubernetes.azure.com/cluster" in labels or "agentpool" in labels:
                region = labels.get("topology.kubernetes.io/region") or labels.get(
                    "failure-domain.beta.kubernetes.io/region"
                )
                return CloudProviderInfo(
                    detected=True,
                    provider="azure",
                    region=region,
                    metadata={
                        "instance_type": labels.get("node.kubernetes.io/instance-type", ""),
                        "zone": labels.get("topology.kubernetes.io/zone", ""),
                        "agentpool": labels.get("agentpool", ""),
                    },
                )

            # Generic on-premises or unknown provider
            return CloudProviderInfo(
                detected=True,
                provider="on-premises",
                region=None,
                metadata={
                    "hostname": labels.get("kubernetes.io/hostname", ""),
                },
            )

        except ApiException as e:
            logger.error(f"Failed to detect cloud provider: {e}")
            return CloudProviderInfo(
                detected=False, provider=None, region=None, metadata={}
            )
