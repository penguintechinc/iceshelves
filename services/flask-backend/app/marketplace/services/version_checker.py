"""Version tracking service for Kubernetes clusters and applications."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum
import re

import requests
from kubernetes import client as k8s_client


class UpdateUrgency(str, Enum):
    """Update urgency levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(slots=True)
class VersionInfo:
    """Version information for a resource."""
    resource_type: str
    resource_name: str
    current_version: str
    latest_version: str
    update_available: bool
    update_urgency: UpdateUrgency
    release_notes_url: str


class VersionChecker:
    """Service for checking and tracking version availability."""

    # Common addon image patterns
    ADDON_CONFIGS = {
        "ingress-nginx": {
            "namespace": "ingress-nginx",
            "deployment": "ingress-nginx-controller",
            "repo_url": "https://raw.githubusercontent.com/kubernetes/ingress-nginx/main",
        },
        "cert-manager": {
            "namespace": "cert-manager",
            "deployment": "cert-manager",
            "repo_url": "https://raw.githubusercontent.com/jetstack/cert-manager/master",
        },
        "metrics-server": {
            "namespace": "kube-system",
            "deployment": "metrics-server",
            "repo_url": "https://raw.githubusercontent.com/kubernetes-sigs/metrics-server/master",
        },
    }

    def check_kubernetes_version(self, k8s_client_instance: k8s_client.ApiClient) -> VersionInfo:
        """
        Check Kubernetes version vs latest stable.

        Args:
            k8s_client_instance: Kubernetes client instance

        Returns:
            VersionInfo with K8s version information
        """
        v1 = k8s_client.VersionApi(k8s_client_instance)
        version_info = v1.get_code()

        current_version = version_info.git_version.lstrip("v")

        # Fetch latest stable version from Kubernetes release page
        latest_version = self._get_latest_k8s_version()

        update_available = self.compare_versions(current_version, latest_version)
        update_urgency = self._determine_k8s_urgency(current_version, latest_version)

        return VersionInfo(
            resource_type="kubernetes",
            resource_name="kubernetes",
            current_version=current_version,
            latest_version=latest_version,
            update_available=update_available,
            update_urgency=update_urgency,
            release_notes_url=f"https://kubernetes.io/releases/notes/v{latest_version}/",
        )

    def check_addon_versions(self, k8s_client_instance: k8s_client.ApiClient) -> list[VersionInfo]:
        """
        Check addon versions (ingress-nginx, cert-manager, etc.).

        Args:
            k8s_client_instance: Kubernetes client instance

        Returns:
            List of VersionInfo for each addon
        """
        addon_versions = []
        v1 = k8s_client.AppsV1Api(k8s_client_instance)

        for addon_name, config in self.ADDON_CONFIGS.items():
            try:
                deployment = v1.read_namespaced_deployment(
                    name=config["deployment"],
                    namespace=config["namespace"],
                )

                # Extract version from image
                image = deployment.spec.template.spec.containers[0].image
                current_version = self._extract_version_from_image(image)

                # Get latest version
                latest_version = self._get_latest_addon_version(addon_name, config["repo_url"])

                update_available = self.compare_versions(current_version, latest_version)
                update_urgency = self._determine_addon_urgency(addon_name, current_version, latest_version)

                addon_versions.append(
                    VersionInfo(
                        resource_type="addon",
                        resource_name=addon_name,
                        current_version=current_version,
                        latest_version=latest_version,
                        update_available=update_available,
                        update_urgency=update_urgency,
                        release_notes_url=f"{config['repo_url']}/releases/tag/v{latest_version}",
                    )
                )
            except Exception:
                # Addon not installed, skip
                continue

        return addon_versions

    def check_app_versions(self, db) -> list[VersionInfo]:
        """
        Check deployed app versions vs Helm repo latest.

        Args:
            db: Database connection

        Returns:
            List of VersionInfo for each deployed application
        """
        app_versions = []

        try:
            # Query deployed applications from database
            # This assumes a table structure exists for deployed applications
            rows = db.executesql(
                "SELECT id, name, helm_chart, current_version FROM deployed_applications WHERE status = 'active'"
            )

            for row in rows:
                app_id, app_name, helm_chart, current_version = row

                # Get latest version from Helm repository
                latest_version = self._get_latest_helm_version(helm_chart)

                update_available = self.compare_versions(current_version, latest_version)
                update_urgency = self._determine_app_urgency(app_name, current_version, latest_version)

                app_versions.append(
                    VersionInfo(
                        resource_type="application",
                        resource_name=app_name,
                        current_version=current_version,
                        latest_version=latest_version,
                        update_available=update_available,
                        update_urgency=update_urgency,
                        release_notes_url=f"https://artifacthub.io/packages/helm/{helm_chart}",
                    )
                )
        except Exception:
            # Database query failed, return empty list
            pass

        return app_versions

    def get_all_updates(self, db, cluster_id: str) -> list[VersionInfo]:
        """
        Get all available updates for a cluster.

        Args:
            db: Database connection
            cluster_id: Cluster identifier

        Returns:
            List of all available updates
        """
        all_updates = []

        try:
            # Get K8s version
            # Note: In production, would fetch from stored cluster info
            # For now, this is a placeholder
            pass
        except Exception:
            pass

        # Get addon versions
        try:
            # Note: Would need to enhance to get k8s_client from cluster_id
            addon_versions = []
            all_updates.extend(addon_versions)
        except Exception:
            pass

        # Get app versions
        try:
            app_versions = self.check_app_versions(db)
            all_updates.extend(app_versions)
        except Exception:
            pass

        # Filter to only updates that are available
        return [u for u in all_updates if u.update_available]

    @staticmethod
    def compare_versions(current: str, latest: str) -> bool:
        """
        Compare semantic versions using semver logic.

        Args:
            current: Current version string (e.g., "1.28.0")
            latest: Latest version string (e.g., "1.29.0")

        Returns:
            True if latest > current, False otherwise
        """
        def parse_semver(version: str) -> tuple[int, ...]:
            """Parse semver string into tuple of integers."""
            # Remove 'v' prefix if present
            version = version.lstrip("v")
            # Extract numeric parts (handling pre-release and build metadata)
            match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
            if not match:
                return (0, 0, 0)
            return tuple(int(x) for x in match.groups())

        current_tuple = parse_semver(current)
        latest_tuple = parse_semver(latest)

        return latest_tuple > current_tuple

    @staticmethod
    def _extract_version_from_image(image: str) -> str:
        """Extract version from Docker image string."""
        if ":" in image:
            return image.split(":")[-1]
        return "unknown"

    @staticmethod
    def _get_latest_k8s_version() -> str:
        """Fetch latest stable Kubernetes version."""
        try:
            response = requests.get(
                "https://api.github.com/repos/kubernetes/kubernetes/releases/latest",
                timeout=5,
            )
            if response.status_code == 200:
                tag = response.json().get("tag_name", "v1.28.0")
                return tag.lstrip("v")
            return "1.28.0"
        except Exception:
            return "1.28.0"

    @staticmethod
    def _get_latest_addon_version(addon_name: str, repo_url: str) -> str:
        """Fetch latest addon version from repository."""
        try:
            response = requests.get(
                f"{repo_url}/releases/latest",
                timeout=5,
            )
            if response.status_code == 200:
                tag = response.json().get("tag_name", "v0.0.0")
                return tag.lstrip("v")
            return "0.0.0"
        except Exception:
            return "0.0.0"

    @staticmethod
    def _get_latest_helm_version(helm_chart: str) -> str:
        """Fetch latest Helm chart version from repository."""
        try:
            response = requests.get(
                f"https://artifacthub.io/api/v1/packages/helm/{helm_chart}",
                timeout=5,
            )
            if response.status_code == 200:
                return response.json().get("version", "0.0.0")
            return "0.0.0"
        except Exception:
            return "0.0.0"

    @staticmethod
    def _determine_k8s_urgency(current: str, latest: str) -> UpdateUrgency:
        """Determine update urgency for Kubernetes version."""
        current_tuple = tuple(int(x) for x in current.split(".")[:2])
        latest_tuple = tuple(int(x) for x in latest.split(".")[:2])

        # Critical if minor version difference > 2
        if latest_tuple[0] > current_tuple[0]:
            return UpdateUrgency.CRITICAL if latest_tuple[0] - current_tuple[0] > 1 else UpdateUrgency.HIGH

        if latest_tuple[1] - current_tuple[1] > 2:
            return UpdateUrgency.CRITICAL

        if latest_tuple[1] - current_tuple[1] > 0:
            return UpdateUrgency.HIGH

        return UpdateUrgency.LOW

    @staticmethod
    def _determine_addon_urgency(addon_name: str, current: str, latest: str) -> UpdateUrgency:
        """Determine update urgency for addon."""
        # Cert-manager and security-related addons are higher priority
        if addon_name in ["cert-manager"]:
            return UpdateUrgency.HIGH

        current_tuple = tuple(int(x) for x in (current + ".0.0").split(".")[:2])
        latest_tuple = tuple(int(x) for x in (latest + ".0.0").split(".")[:2])

        if latest_tuple[0] > current_tuple[0]:
            return UpdateUrgency.HIGH

        if latest_tuple[1] - current_tuple[1] > 1:
            return UpdateUrgency.MEDIUM

        return UpdateUrgency.LOW

    @staticmethod
    def _determine_app_urgency(app_name: str, current: str, latest: str) -> UpdateUrgency:
        """Determine update urgency for application."""
        # Parse versions
        try:
            current_tuple = tuple(int(x) for x in current.split(".")[:3])
            latest_tuple = tuple(int(x) for x in latest.split(".")[:3])
        except (ValueError, IndexError):
            return UpdateUrgency.MEDIUM

        # Major version bump is high priority
        if latest_tuple[0] > current_tuple[0]:
            return UpdateUrgency.HIGH

        # Minor version bump is medium
        if latest_tuple[1] > current_tuple[1]:
            return UpdateUrgency.MEDIUM

        # Patch version bump is low
        return UpdateUrgency.LOW
