"""
IceShelves Secrets Management

Provides abstraction layer for storing and retrieving sensitive credentials
using various secrets management solutions.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SecretsManager(ABC):
    """
    Abstract base class for secrets management.

    All secrets managers must implement these methods for storing
    and retrieving sensitive data.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize secrets manager with configuration.

        Args:
            config: Configuration dictionary specific to the secrets backend
        """
        self.config = config or {}
        self._cache = {}
        self._cache_ttl = timedelta(minutes=5)  # Cache secrets for 5 minutes
        self._cache_timestamps = {}

    @abstractmethod
    def get_secret(self, key: str) -> Optional[str]:
        """
        Retrieve a secret by key.

        Args:
            key: Secret identifier

        Returns:
            Secret value or None if not found
        """
        pass

    @abstractmethod
    def store_secret(self, key: str, value: str) -> bool:
        """
        Store a secret.

        Args:
            key: Secret identifier
            value: Secret value

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret.

        Args:
            key: Secret identifier

        Returns:
            True if successful, False otherwise
        """
        pass

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached secret is still valid."""
        if key not in self._cache_timestamps:
            return False
        return datetime.now() - self._cache_timestamps[key] < self._cache_ttl

    def _cache_secret(self, key: str, value: str):
        """Cache a secret value."""
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()

    def _get_cached_secret(self, key: str) -> Optional[str]:
        """Get secret from cache if valid."""
        if self._is_cache_valid(key):
            return self._cache.get(key)
        return None


class DatabaseSecretsManager(SecretsManager):
    """
    Store secrets directly in the database (current behavior).

    This is the default/fallback method. Secrets are stored as-is in
    the database fields. Not recommended for production use.
    """

    def __init__(self, db, target_id: int, config: Optional[Dict[str, Any]] = None):
        """
        Initialize database secrets manager.

        Args:
            db: PyDAL database instance
            target_id: Deployment target ID
            config: Optional configuration
        """
        super().__init__(config)
        self.db = db
        self.target_id = target_id

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve secret from database field."""
        target = self.db.deployment_targets[self.target_id]
        if not target:
            return None

        # Map key to database field
        field_map = {
            'ssh_key': 'ssh_key',
            'client_key': 'client_key',
            'client_cert': 'client_cert',
            'server_cert': 'server_cert',
            'trust_password': 'trust_password',
            'agent_key': 'agent_key',
        }

        field = field_map.get(key)
        if field:
            return getattr(target, field, None)

        return None

    def store_secret(self, key: str, value: str) -> bool:
        """Store secret in database field."""
        field_map = {
            'ssh_key': 'ssh_key',
            'client_key': 'client_key',
            'client_cert': 'client_cert',
            'server_cert': 'server_cert',
            'trust_password': 'trust_password',
            'agent_key': 'agent_key',
        }

        field = field_map.get(key)
        if field:
            try:
                self.db(self.db.deployment_targets.id == self.target_id).update(**{field: value})
                self.db.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to store secret in database: {e}")
                return False

        return False

    def delete_secret(self, key: str) -> bool:
        """Delete secret from database field."""
        return self.store_secret(key, None)


class AWSSecretsManager(SecretsManager):
    """
    Store secrets in AWS Secrets Manager.

    Configuration format:
    {
        "region": "us-east-1",
        "secret_prefix": "iceshelves/target-name/"
    }
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize AWS Secrets Manager client.

        Args:
            config: AWS configuration (region, secret_prefix, etc.)
        """
        super().__init__(config)

        try:
            import boto3
            from botocore.exceptions import ClientError

            self.boto3 = boto3
            self.ClientError = ClientError

            region = self.config.get('region', os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
            self.client = boto3.client('secretsmanager', region_name=region)
            self.secret_prefix = self.config.get('secret_prefix', 'iceshelves/')

        except ImportError:
            logger.error("boto3 not installed. Cannot use AWS Secrets Manager.")
            raise

    def _get_secret_name(self, key: str) -> str:
        """Get full secret name with prefix."""
        return f"{self.secret_prefix}{key}"

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve secret from AWS Secrets Manager."""
        # Check cache first
        cached = self._get_cached_secret(key)
        if cached:
            return cached

        try:
            response = self.client.get_secret_value(SecretId=self._get_secret_name(key))

            # Secrets can be string or binary
            if 'SecretString' in response:
                secret_value = response['SecretString']
            else:
                secret_value = response['SecretBinary'].decode('utf-8')

            # Cache the secret
            self._cache_secret(key, secret_value)

            return secret_value

        except self.ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.warning(f"Secret not found: {key}")
            else:
                logger.error(f"Failed to retrieve AWS secret {key}: {e}")
            return None

    def store_secret(self, key: str, value: str) -> bool:
        """Store secret in AWS Secrets Manager."""
        try:
            secret_name = self._get_secret_name(key)

            # Try to update existing secret
            try:
                self.client.put_secret_value(
                    SecretId=secret_name,
                    SecretString=value
                )
            except self.ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    # Create new secret
                    self.client.create_secret(
                        Name=secret_name,
                        SecretString=value,
                        Description=f"IceShelves secret: {key}"
                    )
                else:
                    raise

            # Invalidate cache
            if key in self._cache:
                del self._cache[key]
                del self._cache_timestamps[key]

            return True

        except Exception as e:
            logger.error(f"Failed to store AWS secret {key}: {e}")
            return False

    def delete_secret(self, key: str) -> bool:
        """Delete secret from AWS Secrets Manager."""
        try:
            self.client.delete_secret(
                SecretId=self._get_secret_name(key),
                ForceDeleteWithoutRecovery=True
            )

            # Invalidate cache
            if key in self._cache:
                del self._cache[key]
                del self._cache_timestamps[key]

            return True

        except Exception as e:
            logger.error(f"Failed to delete AWS secret {key}: {e}")
            return False


class GCPSecretsManager(SecretsManager):
    """
    Store secrets in GCP Secret Manager.

    Configuration format:
    {
        "project_id": "my-project",
        "secret_prefix": "iceshelves-target-name-"
    }
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize GCP Secret Manager client.

        Args:
            config: GCP configuration (project_id, secret_prefix, etc.)
        """
        super().__init__(config)

        try:
            from google.cloud import secretmanager

            self.secretmanager = secretmanager
            self.client = secretmanager.SecretManagerServiceClient()

            self.project_id = self.config.get('project_id', os.getenv('GCP_PROJECT_ID'))
            if not self.project_id:
                raise ValueError("GCP project_id is required")

            self.secret_prefix = self.config.get('secret_prefix', 'iceshelves-')

        except ImportError:
            logger.error("google-cloud-secret-manager not installed. Cannot use GCP Secret Manager.")
            raise

    def _get_secret_name(self, key: str) -> str:
        """Get full secret resource name."""
        secret_id = f"{self.secret_prefix}{key}".replace('_', '-')
        return f"projects/{self.project_id}/secrets/{secret_id}"

    def _get_latest_version(self, secret_name: str) -> str:
        """Get latest version resource name."""
        return f"{secret_name}/versions/latest"

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve secret from GCP Secret Manager."""
        # Check cache first
        cached = self._get_cached_secret(key)
        if cached:
            return cached

        try:
            secret_name = self._get_secret_name(key)
            version_name = self._get_latest_version(secret_name)

            response = self.client.access_secret_version(request={"name": version_name})
            secret_value = response.payload.data.decode('UTF-8')

            # Cache the secret
            self._cache_secret(key, secret_value)

            return secret_value

        except Exception as e:
            logger.error(f"Failed to retrieve GCP secret {key}: {e}")
            return None

    def store_secret(self, key: str, value: str) -> bool:
        """Store secret in GCP Secret Manager."""
        try:
            parent = f"projects/{self.project_id}"
            secret_id = f"{self.secret_prefix}{key}".replace('_', '-')

            # Try to create secret first
            try:
                secret = self.client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": secret_id,
                        "secret": {
                            "replication": {"automatic": {}},
                            "labels": {"managed-by": "iceshelves"}
                        }
                    }
                )
            except Exception as e:
                # Secret might already exist
                logger.debug(f"Secret {secret_id} might already exist: {e}")
                secret_name = f"{parent}/secrets/{secret_id}"
            else:
                secret_name = secret.name

            # Add secret version
            self.client.add_secret_version(
                request={
                    "parent": secret_name,
                    "payload": {"data": value.encode('UTF-8')}
                }
            )

            # Invalidate cache
            if key in self._cache:
                del self._cache[key]
                del self._cache_timestamps[key]

            return True

        except Exception as e:
            logger.error(f"Failed to store GCP secret {key}: {e}")
            return False

    def delete_secret(self, key: str) -> bool:
        """Delete secret from GCP Secret Manager."""
        try:
            secret_name = self._get_secret_name(key)
            self.client.delete_secret(request={"name": secret_name})

            # Invalidate cache
            if key in self._cache:
                del self._cache[key]
                del self._cache_timestamps[key]

            return True

        except Exception as e:
            logger.error(f"Failed to delete GCP secret {key}: {e}")
            return False


class InfisicalSecretsManager(SecretsManager):
    """
    Store secrets in Infisical.

    Configuration format:
    {
        "client_id": "universal-auth-client-id",
        "client_secret": "universal-auth-client-secret",
        "project_id": "project-id",
        "environment": "prod",
        "secret_path": "/iceshelves/target-name"
    }
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Infisical client.

        Args:
            config: Infisical configuration
        """
        super().__init__(config)

        try:
            from infisical_client import ClientSettings, InfisicalClient, AuthenticationOptions, UniversalAuthMethod

            # Initialize Infisical client
            client_settings = ClientSettings(
                client_id=self.config.get('client_id'),
                client_secret=self.config.get('client_secret'),
            )

            self.client = InfisicalClient(client_settings)

            auth = AuthenticationOptions(
                universal_auth=UniversalAuthMethod(
                    client_id=self.config.get('client_id'),
                    client_secret=self.config.get('client_secret'),
                )
            )

            self.client.auth(auth)

            self.project_id = self.config['project_id']
            self.environment = self.config.get('environment', 'prod')
            self.secret_path = self.config.get('secret_path', '/')

        except ImportError:
            logger.error("infisical-python not installed. Cannot use Infisical.")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Infisical client: {e}")
            raise

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve secret from Infisical."""
        # Check cache first
        cached = self._get_cached_secret(key)
        if cached:
            return cached

        try:
            secret = self.client.getSecret(options={
                "environment": self.environment,
                "projectId": self.project_id,
                "path": self.secret_path,
                "secretName": key,
            })

            secret_value = secret.secret_value

            # Cache the secret
            self._cache_secret(key, secret_value)

            return secret_value

        except Exception as e:
            logger.error(f"Failed to retrieve Infisical secret {key}: {e}")
            return None

    def store_secret(self, key: str, value: str) -> bool:
        """Store secret in Infisical."""
        try:
            self.client.createSecret(options={
                "environment": self.environment,
                "projectId": self.project_id,
                "path": self.secret_path,
                "secretName": key,
                "secretValue": value,
                "type": "shared",
            })

            # Invalidate cache
            if key in self._cache:
                del self._cache[key]
                del self._cache_timestamps[key]

            return True

        except Exception as e:
            # Try updating if create failed
            try:
                self.client.updateSecret(options={
                    "environment": self.environment,
                    "projectId": self.project_id,
                    "path": self.secret_path,
                    "secretName": key,
                    "secretValue": value,
                })

                # Invalidate cache
                if key in self._cache:
                    del self._cache[key]
                    del self._cache_timestamps[key]

                return True
            except Exception as update_error:
                logger.error(f"Failed to store/update Infisical secret {key}: {update_error}")
                return False

    def delete_secret(self, key: str) -> bool:
        """Delete secret from Infisical."""
        try:
            self.client.deleteSecret(options={
                "environment": self.environment,
                "projectId": self.project_id,
                "path": self.secret_path,
                "secretName": key,
            })

            # Invalidate cache
            if key in self._cache:
                del self._cache[key]
                del self._cache_timestamps[key]

            return True

        except Exception as e:
            logger.error(f"Failed to delete Infisical secret {key}: {e}")
            return False


def get_secrets_manager(target_config: Dict[str, Any], db=None, target_id: int = None) -> SecretsManager:
    """
    Factory function to get appropriate secrets manager.

    Args:
        target_config: Deployment target configuration
        db: PyDAL database instance (required for database secrets manager)
        target_id: Deployment target ID (required for database secrets manager)

    Returns:
        SecretsManager instance

    Raises:
        ValueError: If configuration is invalid
    """
    secrets_type = target_config.get('secrets_manager_type', 'database')
    secrets_config = target_config.get('secrets_config', {})

    if secrets_type == 'database':
        if not db or not target_id:
            raise ValueError("Database and target_id required for database secrets manager")
        return DatabaseSecretsManager(db, target_id, secrets_config)

    elif secrets_type == 'aws':
        return AWSSecretsManager(secrets_config)

    elif secrets_type == 'gcp':
        return GCPSecretsManager(secrets_config)

    elif secrets_type == 'infisical':
        return InfisicalSecretsManager(secrets_config)

    else:
        raise ValueError(f"Unknown secrets manager type: {secrets_type}")
