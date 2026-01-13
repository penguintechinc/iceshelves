/**
 * Marketplace Types
 *
 * Comprehensive TypeScript types and interfaces for the iceshelves marketplace
 * including application sources, deployments, clusters, and configurations.
 */

/**
 * Supported application source types
 */
export type AppSourceType = 'helm' | 'docker' | 'aws' | 'gcp' | 'manifest';

/**
 * Deployment status enum
 */
export type DeploymentStatus = 'pending' | 'deploying' | 'running' | 'failed' | 'deleted' | 'degraded' | 'unknown';

/**
 * Types of dependencies an application may require
 */
export type DependencyType = 'database' | 'cache' | 'storage' | 'messaging';

/**
 * Supported cloud providers
 */
export type CloudProvider = 'aws' | 'gcp' | 'azure' | 'generic';

/**
 * Supported webhook notification types
 */
export type WebhookType = 'slack' | 'discord' | 'teams' | 'generic';

/**
 * Kubernetes cluster information
 */
export interface Cluster {
  id: string;
  name: string;
  display_name: string;
  cloud_provider: CloudProvider;
  region: string;
  k8s_version: string;
  is_default: boolean;
  is_active: boolean;
  detected_ingress: string[];
  detected_storage_classes: string[];
}

/**
 * Helm Chart Repository configuration
 */
export interface HelmRepository {
  id: string;
  name: string;
  url: string;
  description: string;
  category: string;
  is_builtin: boolean;
  is_enabled: boolean;
  helm_version: string;
  last_synced: string;
  chart_count: number;
}

/**
 * Registry authentication types
 */
export type RegistryAuthType = 'none' | 'basic' | 'bearer' | 'token' | 'aws' | 'gcp' | 'azure';

/**
 * Registry types
 */
export type RegistryType = 'dockerhub' | 'ghcr' | 'ecr' | 'gcr' | 'acr' | 'quay' | 'custom';

/**
 * Docker Registry configuration
 */
export interface DockerRegistry {
  id: string;
  name: string;
  url: string;
  registry_type: RegistryType;
  is_builtin: boolean;
  is_enabled: boolean;
  auth_type: RegistryAuthType;
  auth_username?: string;
  // AWS ECR specific
  aws_region?: string;
  // Connection test status
  last_connection_test?: string;
  connection_test_success?: boolean;
  connection_test_error?: string;
}

/**
 * Docker Registry form data for creating/updating
 */
export interface DockerRegistryFormData {
  name: string;
  url: string;
  registry_type: RegistryType;
  auth_type: RegistryAuthType;
  auth_username?: string;
  auth_password?: string;
  aws_access_key?: string;
  aws_secret_key?: string;
  aws_region?: string;
  gcp_service_account_json?: string;
  azure_client_id?: string;
  azure_client_secret?: string;
  azure_tenant_id?: string;
}

/**
 * Marketplace application listing
 */
export interface MarketplaceApp {
  id: string;
  source_type: AppSourceType;
  app_name: string;
  app_version: string;
  latest_version: string;
  description: string;
  icon_url: string;
  category: string;
  tags: string[];
  dependencies: DependencyType[];
}

/**
 * Deployed application instance
 */
export interface DeployedApp {
  id: string;
  name: string;
  namespace: string;
  cluster_id: string;
  app_id: string;
  source_type: AppSourceType;
  installed_version: string;
  status: DeploymentStatus;
  health_status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown';
  replicas_desired: number;
  replicas_ready: number;
  replicas_available: number;
  cpu_usage: string;
  memory_usage: string;
  deployed_by: string;
  created_at: string;
}

/**
 * Dependency configuration for applications
 */
export interface DependencyConfig {
  type: DependencyType;
  provider: CloudProvider;
  use_managed: boolean;
  managed_service_id?: string;
  connection_config: Record<string, unknown>;
}

/**
 * Deployment wizard state management
 */
export interface WizardState {
  app_id: string;
  cluster_id: string;
  name: string;
  namespace: string;
  dependencies: DependencyConfig[];
  storage: {
    storage_class: string;
    size: string;
  };
  network: {
    ingress_class: string;
    ingress_annotations: Record<string, string>;
  };
  custom_values: Record<string, unknown>;
  current_step: number;
}

/**
 * Summary of deployed applications inventory
 */
export interface InventorySummary {
  total_apps: number;
  running: number;
  failed: number;
  deploying: number;
  pending: number;
  degraded: number;
  updates_available: number;
}

/**
 * Application version information
 */
export interface VersionInfo {
  resource_type: 'app' | 'helm_chart' | 'docker_image' | 'cluster';
  resource_name: string;
  current_version: string;
  latest_version: string;
  update_available: boolean;
  update_urgency: 'critical' | 'high' | 'medium' | 'low';
}

/**
 * Ingress configuration option
 */
export interface IngressOption {
  name: string;
  type: 'nginx' | 'traefik' | 'istio' | 'aws-alb' | 'gcp-gclb';
  cloud_specific: boolean;
  annotations: Record<string, string>;
}

/**
 * User notification preferences
 */
export interface NotificationPreferences {
  email_enabled: boolean;
  email_frequency: 'immediate' | 'daily' | 'weekly';
  in_app_enabled: boolean;
  critical_updates_only: boolean;
}

/**
 * Webhook notification configuration
 */
export interface Webhook {
  id: string;
  name: string;
  url: string;
  webhook_type: WebhookType;
  is_enabled: boolean;
  events: string[];
  last_triggered?: string;
  failure_count: number;
}
