"""
Helm client wrapper supporting both Helm v2 and v3.

This module provides a Python wrapper around the Helm CLI, with automatic detection
and support for both Helm v2 and v3 command syntax differences.
"""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class HelmVersion(Enum):
    """Helm version enum."""
    V2 = "v2"
    V3 = "v3"


@dataclass(slots=True)
class HelmClientConfig:
    """Configuration for Helm client."""
    kubeconfig: Optional[str] = None
    helm_version: Optional[HelmVersion] = None
    helm_binary: str = "helm"
    timeout: int = 300
    debug: bool = False


@dataclass(slots=True)
class HelmMaintainer:
    """Helm chart maintainer information."""
    name: str
    email: Optional[str] = None
    url: Optional[str] = None


@dataclass(slots=True)
class HelmDependency:
    """Helm chart dependency."""
    name: str
    version: str
    repository: str
    condition: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    enabled: bool = True


@dataclass(slots=True)
class HelmChart:
    """Helm chart metadata."""
    name: str
    version: str
    app_version: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    home: Optional[str] = None
    sources: List[str] = field(default_factory=list)
    maintainers: List[HelmMaintainer] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    dependencies: List[HelmDependency] = field(default_factory=list)
    repository: Optional[str] = None
    deprecated: bool = False


@dataclass(slots=True)
class HelmRelease:
    """Helm release information."""
    name: str
    namespace: str
    revision: int
    status: str
    chart: str
    app_version: Optional[str] = None
    updated: Optional[str] = None


class HelmCommandError(Exception):
    """Exception raised when a Helm command fails."""
    pass


class HelmClient:
    """
    Helm client wrapper supporting v2 and v3.

    Automatically detects Helm version and adapts commands accordingly.
    """

    def __init__(self, config: Optional[HelmClientConfig] = None):
        """
        Initialize Helm client.

        Args:
            config: HelmClientConfig instance or None for defaults
        """
        self.config = config or HelmClientConfig()
        self.version: Optional[HelmVersion] = self.config.helm_version
        self.binary: str = self.config.helm_binary

        if self.version is None:
            self.version = self._detect_version()

    def _detect_version(self) -> HelmVersion:
        """
        Detect Helm version by running helm version command.

        Returns:
            HelmVersion enum value

        Raises:
            HelmCommandError: If helm binary not found or version detection fails
        """
        try:
            result = subprocess.run(
                [self.binary, "version", "--short"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                raise HelmCommandError(f"Failed to detect Helm version: {result.stderr}")

            version_output = result.stdout.strip()

            # v3.x.x format: v3.10.0+g123abc
            # v2.x.x format: Client: v2.17.0+g...
            if version_output.startswith("v3") or "v3." in version_output:
                return HelmVersion.V3
            elif version_output.startswith("v2") or "v2." in version_output:
                return HelmVersion.V2
            else:
                # Default to v3 if unclear
                return HelmVersion.V3

        except FileNotFoundError:
            raise HelmCommandError(f"Helm binary not found: {self.binary}")
        except subprocess.TimeoutExpired:
            raise HelmCommandError("Helm version detection timed out")
        except Exception as e:
            raise HelmCommandError(f"Error detecting Helm version: {e}")

    def _build_base_command(self) -> List[str]:
        """
        Build base Helm command with common flags.

        Returns:
            List of command components
        """
        cmd = [self.binary]

        if self.config.kubeconfig:
            cmd.extend(["--kubeconfig", self.config.kubeconfig])

        if self.config.debug:
            cmd.append("--debug")

        return cmd

    def _run_command(self, args: List[str], capture_json: bool = False) -> str:
        """
        Run Helm command with error handling.

        Args:
            args: Command arguments to append to base command
            capture_json: If True, add --output json flag for v3

        Returns:
            Command stdout as string

        Raises:
            HelmCommandError: If command fails
        """
        cmd = self._build_base_command()
        cmd.extend(args)

        if capture_json and self.version == HelmVersion.V3:
            if "--output" not in cmd and "-o" not in cmd:
                cmd.extend(["--output", "json"])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout
            )

            if result.returncode != 0:
                raise HelmCommandError(
                    f"Helm command failed: {' '.join(cmd)}\n"
                    f"Error: {result.stderr}"
                )

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise HelmCommandError(f"Helm command timed out: {' '.join(cmd)}")
        except Exception as e:
            raise HelmCommandError(f"Error running Helm command: {e}")

    def add_repo(
        self,
        name: str,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> None:
        """
        Add Helm repository.

        Args:
            name: Repository name
            url: Repository URL
            username: Optional HTTP basic auth username
            password: Optional HTTP basic auth password

        Raises:
            HelmCommandError: If command fails
        """
        args = ["repo", "add", name, url]

        if username:
            args.extend(["--username", username])
        if password:
            args.extend(["--password", password])

        self._run_command(args)

    def update_repos(self) -> None:
        """
        Update all Helm repositories.

        Raises:
            HelmCommandError: If command fails
        """
        self._run_command(["repo", "update"])

    def search_charts(
        self,
        repo: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> List[HelmChart]:
        """
        Search for charts in repositories.

        Args:
            repo: Repository name to search (None for all repos)
            keyword: Search keyword (None for all charts)

        Returns:
            List of HelmChart objects

        Raises:
            HelmCommandError: If command fails
        """
        if self.version == HelmVersion.V3:
            args = ["search", "repo"]
            if repo and keyword:
                args.append(f"{repo}/{keyword}")
            elif repo:
                args.append(f"{repo}/")
            elif keyword:
                args.append(keyword)
            else:
                args.append("")
            args.extend(["--output", "json"])
        else:  # v2
            args = ["search"]
            if repo and keyword:
                args.append(f"{repo}/{keyword}")
            elif repo:
                args.append(repo)
            elif keyword:
                args.append(keyword)

        output = self._run_command(args)

        if not output:
            return []

        charts: List[HelmChart] = []

        if self.version == HelmVersion.V3:
            try:
                results = json.loads(output)
                for item in results:
                    charts.append(HelmChart(
                        name=item.get("name", ""),
                        version=item.get("version", ""),
                        app_version=item.get("app_version"),
                        description=item.get("description"),
                        deprecated=item.get("deprecated", False)
                    ))
            except json.JSONDecodeError:
                raise HelmCommandError("Failed to parse search results")
        else:  # v2 - parse table format
            lines = output.split("\n")
            for line in lines[1:]:  # Skip header
                if not line.strip():
                    continue
                parts = re.split(r"\s+", line.strip(), maxsplit=3)
                if len(parts) >= 3:
                    charts.append(HelmChart(
                        name=parts[0],
                        version=parts[1],
                        app_version=parts[2] if len(parts) > 2 else None,
                        description=parts[3] if len(parts) > 3 else None
                    ))

        return charts

    def get_chart_info(
        self,
        chart: str,
        version: Optional[str] = None
    ) -> HelmChart:
        """
        Get detailed chart information.

        Args:
            chart: Chart name (repo/chart)
            version: Specific chart version (None for latest)

        Returns:
            HelmChart object with full metadata

        Raises:
            HelmCommandError: If command fails
        """
        args = ["show", "chart", chart]

        if version:
            args.extend(["--version", version])

        output = self._run_command(args)

        try:
            import yaml
            metadata = yaml.safe_load(output)

            maintainers = [
                HelmMaintainer(
                    name=m.get("name", ""),
                    email=m.get("email"),
                    url=m.get("url")
                )
                for m in metadata.get("maintainers", [])
            ]

            dependencies = [
                HelmDependency(
                    name=d.get("name", ""),
                    version=d.get("version", ""),
                    repository=d.get("repository", ""),
                    condition=d.get("condition"),
                    tags=d.get("tags", []),
                    enabled=d.get("enabled", True)
                )
                for d in metadata.get("dependencies", [])
            ]

            return HelmChart(
                name=metadata.get("name", ""),
                version=metadata.get("version", ""),
                app_version=metadata.get("appVersion"),
                description=metadata.get("description"),
                icon=metadata.get("icon"),
                home=metadata.get("home"),
                sources=metadata.get("sources", []),
                maintainers=maintainers,
                keywords=metadata.get("keywords", []),
                dependencies=dependencies,
                deprecated=metadata.get("deprecated", False)
            )
        except Exception as e:
            raise HelmCommandError(f"Failed to parse chart metadata: {e}")

    def get_values_schema(
        self,
        chart: str,
        version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get chart values schema (values.schema.json).

        Args:
            chart: Chart name (repo/chart)
            version: Specific chart version (None for latest)

        Returns:
            JSON schema dict or None if not available

        Raises:
            HelmCommandError: If command fails
        """
        args = ["show", "values", chart]

        if version:
            args.extend(["--version", version])

        try:
            output = self._run_command(args)

            # Try to parse as JSON first (values.schema.json)
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                # Not JSON schema, return None
                return None

        except HelmCommandError:
            return None

    def install(
        self,
        release: str,
        chart: str,
        namespace: str = "default",
        values: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
        create_namespace: bool = False
    ) -> HelmRelease:
        """
        Install Helm chart.

        Args:
            release: Release name
            chart: Chart name (repo/chart)
            namespace: Kubernetes namespace
            values: Custom values dict
            version: Chart version (None for latest)
            create_namespace: Create namespace if not exists (v3 only)

        Returns:
            HelmRelease object

        Raises:
            HelmCommandError: If command fails
        """
        if self.version == HelmVersion.V3:
            args = ["install", release, chart]
        else:  # v2
            args = ["install", chart, "--name", release]

        args.extend(["--namespace", namespace])

        if version:
            args.extend(["--version", version])

        if create_namespace and self.version == HelmVersion.V3:
            args.append("--create-namespace")

        if values:
            # Write values to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                import yaml
                yaml.dump(values, f)
                values_file = f.name

            try:
                args.extend(["--values", values_file])
                output = self._run_command(args)
            finally:
                os.unlink(values_file)
        else:
            output = self._run_command(args)

        return self.get_release_status(release, namespace)

    def upgrade(
        self,
        release: str,
        chart: str,
        namespace: str = "default",
        values: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
        install: bool = True
    ) -> HelmRelease:
        """
        Upgrade Helm release.

        Args:
            release: Release name
            chart: Chart name (repo/chart)
            namespace: Kubernetes namespace
            values: Custom values dict
            version: Chart version (None for latest)
            install: Install if release doesn't exist

        Returns:
            HelmRelease object

        Raises:
            HelmCommandError: If command fails
        """
        args = ["upgrade", release, chart]
        args.extend(["--namespace", namespace])

        if version:
            args.extend(["--version", version])

        if install:
            args.append("--install")

        if values:
            # Write values to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                import yaml
                yaml.dump(values, f)
                values_file = f.name

            try:
                args.extend(["--values", values_file])
                output = self._run_command(args)
            finally:
                os.unlink(values_file)
        else:
            output = self._run_command(args)

        return self.get_release_status(release, namespace)

    def uninstall(self, release: str, namespace: str = "default") -> None:
        """
        Uninstall Helm release.

        Args:
            release: Release name
            namespace: Kubernetes namespace

        Raises:
            HelmCommandError: If command fails
        """
        if self.version == HelmVersion.V3:
            args = ["uninstall", release]
        else:  # v2
            args = ["delete", release, "--purge"]

        args.extend(["--namespace", namespace])
        self._run_command(args)

    def list_releases(
        self,
        namespace: Optional[str] = None,
        all_namespaces: bool = False
    ) -> List[HelmRelease]:
        """
        List Helm releases.

        Args:
            namespace: Kubernetes namespace (None for default)
            all_namespaces: List releases from all namespaces (v3 only)

        Returns:
            List of HelmRelease objects

        Raises:
            HelmCommandError: If command fails
        """
        args = ["list"]

        if self.version == HelmVersion.V3:
            if all_namespaces:
                args.append("--all-namespaces")
            elif namespace:
                args.extend(["--namespace", namespace])
            args.extend(["--output", "json"])
        else:  # v2
            if namespace:
                args.extend(["--namespace", namespace])

        output = self._run_command(args)

        if not output:
            return []

        releases: List[HelmRelease] = []

        if self.version == HelmVersion.V3:
            try:
                results = json.loads(output)
                for item in results:
                    releases.append(HelmRelease(
                        name=item.get("name", ""),
                        namespace=item.get("namespace", ""),
                        revision=item.get("revision", 0),
                        status=item.get("status", ""),
                        chart=item.get("chart", ""),
                        app_version=item.get("app_version"),
                        updated=item.get("updated")
                    ))
            except json.JSONDecodeError:
                raise HelmCommandError("Failed to parse list results")
        else:  # v2 - parse table format
            lines = output.split("\n")
            for line in lines[1:]:  # Skip header
                if not line.strip():
                    continue
                parts = re.split(r"\s+", line.strip(), maxsplit=8)
                if len(parts) >= 3:
                    releases.append(HelmRelease(
                        name=parts[0],
                        namespace=parts[8] if len(parts) > 8 else "default",
                        revision=int(parts[1]) if len(parts) > 1 else 0,
                        status=parts[7] if len(parts) > 7 else "",
                        chart=parts[8] if len(parts) > 8 else "",
                        app_version=parts[4] if len(parts) > 4 else None,
                        updated=parts[2] if len(parts) > 2 else None
                    ))

        return releases

    def get_release_status(
        self,
        release: str,
        namespace: str = "default"
    ) -> HelmRelease:
        """
        Get Helm release status.

        Args:
            release: Release name
            namespace: Kubernetes namespace

        Returns:
            HelmRelease object

        Raises:
            HelmCommandError: If command fails
        """
        args = ["status", release]
        args.extend(["--namespace", namespace])

        if self.version == HelmVersion.V3:
            args.extend(["--output", "json"])
            output = self._run_command(args)

            try:
                result = json.loads(output)
                info = result.get("info", {})
                return HelmRelease(
                    name=result.get("name", ""),
                    namespace=result.get("namespace", ""),
                    revision=result.get("version", 0),
                    status=info.get("status", ""),
                    chart=result.get("chart", {}).get("metadata", {}).get("name", ""),
                    app_version=result.get("chart", {}).get("metadata", {}).get("appVersion"),
                    updated=info.get("last_deployed")
                )
            except (json.JSONDecodeError, KeyError) as e:
                raise HelmCommandError(f"Failed to parse status results: {e}")
        else:  # v2 - parse text format
            output = self._run_command(args)

            # Parse v2 text output
            name = release
            ns = namespace
            revision = 0
            status = ""
            chart = ""

            for line in output.split("\n"):
                if "STATUS:" in line:
                    status = line.split("STATUS:")[-1].strip()
                elif "CHART:" in line:
                    chart = line.split("CHART:")[-1].strip()
                elif "REVISION:" in line:
                    try:
                        revision = int(line.split("REVISION:")[-1].strip())
                    except ValueError:
                        pass

            return HelmRelease(
                name=name,
                namespace=ns,
                revision=revision,
                status=status,
                chart=chart,
                app_version=None,
                updated=None
            )
