"""Kubernetes manifest parser and validator.

This module provides functionality to parse, validate, and analyze Kubernetes
manifests in YAML format. It supports multi-document YAML files and provides
validation for common Kubernetes resource types.
"""

from dataclasses import dataclass, field
from typing import Any
import yaml
import re


@dataclass(slots=True)
class ParsedManifest:
    """Parsed Kubernetes manifest with validation results."""

    kind: str
    api_version: str
    name: str
    namespace: str | None
    raw_yaml: str
    parsed: dict[str, Any]
    validation_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ManifestParser:
    """Parser and validator for Kubernetes manifests."""

    SUPPORTED_KINDS = [
        "ConfigMap",
        "Secret",
        "Deployment",
        "StatefulSet",
        "Service",
        "Ingress",
        "PersistentVolumeClaim",
        "ServiceAccount",
        "Role",
        "RoleBinding",
        "ClusterRole",
        "ClusterRoleBinding",
        "HorizontalPodAutoscaler",
    ]

    def parse(self, yaml_content: str) -> list[ParsedManifest]:
        """Parse YAML content into list of manifests.

        Supports multi-document YAML files separated by '---'.

        Args:
            yaml_content: Raw YAML string content

        Returns:
            List of ParsedManifest objects

        Raises:
            yaml.YAMLError: If YAML parsing fails
        """
        manifests: list[ParsedManifest] = []

        # Split multi-document YAML
        documents = yaml_content.split('\n---\n')

        for doc in documents:
            doc = doc.strip()
            if not doc:
                continue

            try:
                parsed = yaml.safe_load(doc)

                # Skip empty documents
                if not parsed:
                    continue

                # Extract basic fields
                kind = parsed.get('kind', '')
                api_version = parsed.get('apiVersion', '')
                metadata = parsed.get('metadata', {})
                name = metadata.get('name', '')
                namespace = metadata.get('namespace')

                manifest = ParsedManifest(
                    kind=kind,
                    api_version=api_version,
                    name=name,
                    namespace=namespace,
                    raw_yaml=doc,
                    parsed=parsed,
                )

                # Validate manifest
                errors = self.validate(manifest)
                manifest.validation_errors.extend(errors)

                manifests.append(manifest)

            except yaml.YAMLError as e:
                # Create error manifest
                error_manifest = ParsedManifest(
                    kind='Unknown',
                    api_version='',
                    name='',
                    namespace=None,
                    raw_yaml=doc,
                    parsed={},
                    validation_errors=[f"YAML parsing error: {str(e)}"],
                )
                manifests.append(error_manifest)

        return manifests

    def validate(self, manifest: ParsedManifest) -> list[str]:
        """Validate manifest structure and fields.

        Args:
            manifest: ParsedManifest object to validate

        Returns:
            List of validation error messages
        """
        errors: list[str] = []

        # Check required top-level fields
        if not manifest.kind:
            errors.append("Missing required field: 'kind'")

        if not manifest.api_version:
            errors.append("Missing required field: 'apiVersion'")

        # Check if kind is supported
        if manifest.kind and manifest.kind not in self.SUPPORTED_KINDS:
            manifest.warnings.append(
                f"Unsupported kind '{manifest.kind}'. "
                f"Supported kinds: {', '.join(self.SUPPORTED_KINDS)}"
            )

        # Check metadata
        if 'metadata' not in manifest.parsed:
            errors.append("Missing required field: 'metadata'")
        else:
            metadata = manifest.parsed['metadata']

            if not manifest.name:
                errors.append("Missing required field: 'metadata.name'")

            # Validate name format (DNS-1123 subdomain)
            if manifest.name:
                if not self._validate_dns_name(manifest.name):
                    errors.append(
                        f"Invalid name '{manifest.name}'. Must be a valid "
                        "DNS-1123 subdomain (lowercase alphanumeric, '-', '.')"
                    )

        # Kind-specific validation
        if manifest.kind == 'Deployment':
            errors.extend(self._validate_deployment(manifest))
        elif manifest.kind == 'StatefulSet':
            errors.extend(self._validate_statefulset(manifest))
        elif manifest.kind == 'Service':
            errors.extend(self._validate_service(manifest))
        elif manifest.kind == 'ConfigMap':
            errors.extend(self._validate_configmap(manifest))
        elif manifest.kind == 'Secret':
            errors.extend(self._validate_secret(manifest))
        elif manifest.kind == 'Ingress':
            errors.extend(self._validate_ingress(manifest))
        elif manifest.kind == 'PersistentVolumeClaim':
            errors.extend(self._validate_pvc(manifest))

        return errors

    def categorize(self, manifests: list[ParsedManifest]) -> dict[str, list[ParsedManifest]]:
        """Categorize manifests by type.

        Args:
            manifests: List of ParsedManifest objects

        Returns:
            Dictionary mapping resource types to lists of manifests
        """
        categories: dict[str, list[ParsedManifest]] = {
            'workloads': [],
            'configs': [],
            'services': [],
            'storage': [],
            'rbac': [],
            'autoscaling': [],
            'other': [],
        }

        workload_kinds = {'Deployment', 'StatefulSet', 'DaemonSet', 'Job', 'CronJob'}
        config_kinds = {'ConfigMap', 'Secret'}
        service_kinds = {'Service', 'Ingress'}
        storage_kinds = {'PersistentVolumeClaim', 'PersistentVolume', 'StorageClass'}
        rbac_kinds = {'Role', 'RoleBinding', 'ClusterRole', 'ClusterRoleBinding', 'ServiceAccount'}
        autoscaling_kinds = {'HorizontalPodAutoscaler', 'VerticalPodAutoscaler'}

        for manifest in manifests:
            if manifest.kind in workload_kinds:
                categories['workloads'].append(manifest)
            elif manifest.kind in config_kinds:
                categories['configs'].append(manifest)
            elif manifest.kind in service_kinds:
                categories['services'].append(manifest)
            elif manifest.kind in storage_kinds:
                categories['storage'].append(manifest)
            elif manifest.kind in rbac_kinds:
                categories['rbac'].append(manifest)
            elif manifest.kind in autoscaling_kinds:
                categories['autoscaling'].append(manifest)
            else:
                categories['other'].append(manifest)

        return categories

    def check_references(self, manifests: list[ParsedManifest]) -> list[str]:
        """Check for missing ConfigMap and Secret references.

        Args:
            manifests: List of ParsedManifest objects

        Returns:
            List of warning messages about missing references
        """
        warnings: list[str] = []

        # Collect all ConfigMap and Secret names
        configmaps = set()
        secrets = set()

        for manifest in manifests:
            if manifest.kind == 'ConfigMap' and manifest.name:
                configmaps.add(manifest.name)
            elif manifest.kind == 'Secret' and manifest.name:
                secrets.add(manifest.name)

        # Check references in workloads
        for manifest in manifests:
            if manifest.kind not in ['Deployment', 'StatefulSet', 'DaemonSet', 'Job', 'CronJob']:
                continue

            # Check pod template spec
            spec = manifest.parsed.get('spec', {})
            template = spec.get('template', {})
            pod_spec = template.get('spec', {})

            # Check configMapRef and secretRef in envFrom
            for container in pod_spec.get('containers', []):
                for env_from in container.get('envFrom', []):
                    if 'configMapRef' in env_from:
                        cm_name = env_from['configMapRef'].get('name')
                        if cm_name and cm_name not in configmaps:
                            warnings.append(
                                f"{manifest.kind}/{manifest.name} references "
                                f"ConfigMap '{cm_name}' which is not defined"
                            )

                    if 'secretRef' in env_from:
                        secret_name = env_from['secretRef'].get('name')
                        if secret_name and secret_name not in secrets:
                            warnings.append(
                                f"{manifest.kind}/{manifest.name} references "
                                f"Secret '{secret_name}' which is not defined"
                            )

                # Check valueFrom in env
                for env in container.get('env', []):
                    value_from = env.get('valueFrom', {})

                    if 'configMapKeyRef' in value_from:
                        cm_name = value_from['configMapKeyRef'].get('name')
                        if cm_name and cm_name not in configmaps:
                            warnings.append(
                                f"{manifest.kind}/{manifest.name} references "
                                f"ConfigMap '{cm_name}' which is not defined"
                            )

                    if 'secretKeyRef' in value_from:
                        secret_name = value_from['secretKeyRef'].get('name')
                        if secret_name and secret_name not in secrets:
                            warnings.append(
                                f"{manifest.kind}/{manifest.name} references "
                                f"Secret '{secret_name}' which is not defined"
                            )

            # Check volumes
            for volume in pod_spec.get('volumes', []):
                if 'configMap' in volume:
                    cm_name = volume['configMap'].get('name')
                    if cm_name and cm_name not in configmaps:
                        warnings.append(
                            f"{manifest.kind}/{manifest.name} references "
                            f"ConfigMap '{cm_name}' in volumes which is not defined"
                        )

                if 'secret' in volume:
                    secret_name = volume['secret'].get('secretName')
                    if secret_name and secret_name not in secrets:
                        warnings.append(
                            f"{manifest.kind}/{manifest.name} references "
                            f"Secret '{secret_name}' in volumes which is not defined"
                        )

        return warnings

    def _validate_dns_name(self, name: str) -> bool:
        """Validate DNS-1123 subdomain name.

        Args:
            name: Name to validate

        Returns:
            True if valid, False otherwise
        """
        # DNS-1123 subdomain: lowercase alphanumeric, '-', and '.'
        # Must start and end with alphanumeric
        # Max 253 characters
        pattern = r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$'
        return bool(re.match(pattern, name) and len(name) <= 253)

    def _validate_deployment(self, manifest: ParsedManifest) -> list[str]:
        """Validate Deployment-specific fields."""
        errors: list[str] = []
        spec = manifest.parsed.get('spec', {})

        if 'selector' not in spec:
            errors.append("Deployment missing required field: 'spec.selector'")

        if 'template' not in spec:
            errors.append("Deployment missing required field: 'spec.template'")
        else:
            template = spec['template']
            if 'spec' not in template:
                errors.append("Deployment missing required field: 'spec.template.spec'")
            else:
                pod_spec = template['spec']
                if 'containers' not in pod_spec or not pod_spec['containers']:
                    errors.append("Deployment must define at least one container")

        return errors

    def _validate_statefulset(self, manifest: ParsedManifest) -> list[str]:
        """Validate StatefulSet-specific fields."""
        errors: list[str] = []
        spec = manifest.parsed.get('spec', {})

        if 'serviceName' not in spec:
            errors.append("StatefulSet missing required field: 'spec.serviceName'")

        if 'selector' not in spec:
            errors.append("StatefulSet missing required field: 'spec.selector'")

        if 'template' not in spec:
            errors.append("StatefulSet missing required field: 'spec.template'")

        return errors

    def _validate_service(self, manifest: ParsedManifest) -> list[str]:
        """Validate Service-specific fields."""
        errors: list[str] = []
        spec = manifest.parsed.get('spec', {})

        if 'ports' not in spec or not spec['ports']:
            errors.append("Service must define at least one port")

        return errors

    def _validate_configmap(self, manifest: ParsedManifest) -> list[str]:
        """Validate ConfigMap-specific fields."""
        errors: list[str] = []

        # ConfigMap should have either 'data' or 'binaryData'
        if 'data' not in manifest.parsed and 'binaryData' not in manifest.parsed:
            manifest.warnings.append(
                "ConfigMap has neither 'data' nor 'binaryData' fields"
            )

        return errors

    def _validate_secret(self, manifest: ParsedManifest) -> list[str]:
        """Validate Secret-specific fields."""
        errors: list[str] = []

        # Secret should have 'data' or 'stringData'
        if 'data' not in manifest.parsed and 'stringData' not in manifest.parsed:
            manifest.warnings.append(
                "Secret has neither 'data' nor 'stringData' fields"
            )

        return errors

    def _validate_ingress(self, manifest: ParsedManifest) -> list[str]:
        """Validate Ingress-specific fields."""
        errors: list[str] = []
        spec = manifest.parsed.get('spec', {})

        # Ingress should have rules or defaultBackend
        if 'rules' not in spec and 'defaultBackend' not in spec:
            errors.append("Ingress must define either 'rules' or 'defaultBackend'")

        return errors

    def _validate_pvc(self, manifest: ParsedManifest) -> list[str]:
        """Validate PersistentVolumeClaim-specific fields."""
        errors: list[str] = []
        spec = manifest.parsed.get('spec', {})

        if 'accessModes' not in spec or not spec['accessModes']:
            errors.append("PVC missing required field: 'spec.accessModes'")

        if 'resources' not in spec:
            errors.append("PVC missing required field: 'spec.resources'")

        return errors
