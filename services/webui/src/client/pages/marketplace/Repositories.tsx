import { useState, useEffect } from 'react';
import { useHelmRepositories, useDockerRegistries } from '../../hooks/useMarketplace';
import Card from '../../components/Card';
import Button from '../../components/Button';
import type {
  HelmRepository,
  DockerRegistry,
  RegistryAuthType,
  RegistryType,
  DockerRegistryFormData,
} from '../../types/marketplace';

const REGISTRY_TYPES: { value: RegistryType; label: string }[] = [
  { value: 'dockerhub', label: 'Docker Hub' },
  { value: 'ghcr', label: 'GitHub Container Registry' },
  { value: 'ecr', label: 'AWS ECR' },
  { value: 'gcr', label: 'Google GCR' },
  { value: 'acr', label: 'Azure ACR' },
  { value: 'quay', label: 'Quay.io' },
  { value: 'custom', label: 'Custom Registry' },
];

const AUTH_TYPES: { value: RegistryAuthType; label: string; description: string }[] = [
  { value: 'none', label: 'None', description: 'Public registry, no authentication' },
  { value: 'basic', label: 'Basic Auth', description: 'Username and password' },
  { value: 'token', label: 'Bearer Token', description: 'Token-based authentication' },
  { value: 'aws', label: 'AWS IAM', description: 'AWS access key and secret' },
  { value: 'gcp', label: 'GCP Service Account', description: 'GCP service account JSON' },
  { value: 'azure', label: 'Azure AD', description: 'Azure client credentials' },
];

const DEFAULT_URLS: Record<RegistryType, string> = {
  dockerhub: 'https://registry-1.docker.io',
  ghcr: 'https://ghcr.io',
  ecr: 'https://<account-id>.dkr.ecr.<region>.amazonaws.com',
  gcr: 'https://gcr.io',
  acr: 'https://<registry-name>.azurecr.io',
  quay: 'https://quay.io',
  custom: '',
};

const DEFAULT_AUTH_FOR_TYPE: Record<RegistryType, RegistryAuthType> = {
  dockerhub: 'none',
  ghcr: 'token',
  ecr: 'aws',
  gcr: 'gcp',
  acr: 'azure',
  quay: 'none',
  custom: 'none',
};

export default function Repositories() {
  const [activeTab, setActiveTab] = useState<'helm' | 'docker'>('helm');
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  // Helm Repositories
  const helmApi = useHelmRepositories();
  const [helmRepos, setHelmRepos] = useState<HelmRepository[]>([]);

  // Docker Registries
  const dockerApi = useDockerRegistries();
  const [dockerRepos, setDockerRepos] = useState<DockerRegistry[]>([]);

  // Helm form state
  const [helmFormData, setHelmFormData] = useState({
    name: '',
    url: '',
    category: '',
  });

  // Docker form state
  const [dockerFormData, setDockerFormData] = useState<DockerRegistryFormData>({
    name: '',
    url: '',
    registry_type: 'custom',
    auth_type: 'none',
    auth_username: '',
    auth_password: '',
    aws_access_key: '',
    aws_secret_key: '',
    aws_region: '',
    gcp_service_account_json: '',
    azure_client_id: '',
    azure_client_secret: '',
    azure_tenant_id: '',
  });

  const fetchHelmRepositories = async () => {
    try {
      const response = await helmApi.list();
      setHelmRepos(response.items || []);
    } catch (err) {
      console.error('Failed to load Helm repositories');
    }
  };

  const fetchDockerRegistries = async () => {
    try {
      const response = await dockerApi.list();
      setDockerRepos(response.items || []);
    } catch (err) {
      console.error('Failed to load Docker registries');
    }
  };

  useEffect(() => {
    fetchHelmRepositories();
    fetchDockerRegistries();
  }, []);

  const handleAddRepository = () => {
    setEditingId(null);
    setTestResult(null);
    if (activeTab === 'helm') {
      setHelmFormData({ name: '', url: '', category: '' });
    } else {
      setDockerFormData({
        name: '',
        url: '',
        registry_type: 'custom',
        auth_type: 'none',
        auth_username: '',
        auth_password: '',
        aws_access_key: '',
        aws_secret_key: '',
        aws_region: '',
        gcp_service_account_json: '',
        azure_client_id: '',
        azure_client_secret: '',
        azure_tenant_id: '',
      });
    }
    setShowModal(true);
  };

  const handleEditHelmRepository = (repo: HelmRepository) => {
    setEditingId(repo.id);
    setHelmFormData({
      name: repo.name,
      url: repo.url,
      category: repo.category || '',
    });
    setShowModal(true);
  };

  const handleEditDockerRegistry = (registry: DockerRegistry) => {
    setEditingId(registry.id);
    setTestResult(null);
    setDockerFormData({
      name: registry.name,
      url: registry.url,
      registry_type: registry.registry_type,
      auth_type: registry.auth_type,
      auth_username: registry.auth_username || '',
      auth_password: '',
      aws_access_key: '',
      aws_secret_key: '',
      aws_region: registry.aws_region || '',
      gcp_service_account_json: '',
      azure_client_id: '',
      azure_client_secret: '',
      azure_tenant_id: '',
    });
    setShowModal(true);
  };

  const handleRegistryTypeChange = (type: RegistryType) => {
    setDockerFormData((prev) => ({
      ...prev,
      registry_type: type,
      url: DEFAULT_URLS[type],
      auth_type: DEFAULT_AUTH_FOR_TYPE[type],
    }));
  };

  const handleSaveHelmRepository = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        await helmApi.update(editingId, helmFormData);
      } else {
        await helmApi.create(helmFormData);
      }
      fetchHelmRepositories();
      setShowModal(false);
    } catch (err) {
      console.error('Failed to save repository');
    }
  };

  const handleSaveDockerRegistry = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        await dockerApi.update(editingId, dockerFormData);
      } else {
        await dockerApi.create(dockerFormData);
      }
      fetchDockerRegistries();
      setShowModal(false);
    } catch (err) {
      console.error('Failed to save registry');
    }
  };

  const handleDeleteRepository = async (id: string, isBuiltin: boolean) => {
    if (isBuiltin) {
      alert('Built-in repositories cannot be deleted');
      return;
    }
    if (!confirm('Are you sure you want to delete this repository?')) return;

    try {
      if (activeTab === 'helm') {
        await helmApi.delete(id);
        fetchHelmRepositories();
      } else {
        await dockerApi.delete(id);
        fetchDockerRegistries();
      }
    } catch (err) {
      console.error('Failed to delete repository');
    }
  };

  const handleSyncRepository = async (id: string) => {
    setSyncing(id);
    try {
      await helmApi.sync(id);
      fetchHelmRepositories();
    } catch (err) {
      console.error('Failed to sync repository');
    } finally {
      setSyncing(null);
    }
  };

  const handleTestConnection = async (id: string) => {
    setTesting(id);
    try {
      const result = await dockerApi.testConnection(id);
      setTestResult({
        success: result.success,
        message: result.success ? 'Connection successful!' : result.error,
      });
      fetchDockerRegistries();
    } catch (err) {
      setTestResult({
        success: false,
        message: err instanceof Error ? err.message : 'Connection test failed',
      });
    } finally {
      setTesting(null);
    }
  };

  const handleToggleEnabled = async (id: string, currentlyEnabled: boolean) => {
    try {
      await dockerApi.toggle(id, !currentlyEnabled);
      fetchDockerRegistries();
    } catch (err) {
      console.error('Failed to toggle registry');
    }
  };

  const renderAuthFields = () => {
    switch (dockerFormData.auth_type) {
      case 'basic':
        return (
          <>
            <div>
              <label className="block text-sm text-dark-400 mb-1">Username</label>
              <input
                type="text"
                value={dockerFormData.auth_username}
                onChange={(e) =>
                  setDockerFormData({ ...dockerFormData, auth_username: e.target.value })
                }
                className="input"
                placeholder="Registry username"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">Password</label>
              <input
                type="password"
                value={dockerFormData.auth_password}
                onChange={(e) =>
                  setDockerFormData({ ...dockerFormData, auth_password: e.target.value })
                }
                className="input"
                placeholder={editingId ? '(unchanged)' : 'Registry password'}
              />
            </div>
          </>
        );
      case 'token':
        return (
          <div>
            <label className="block text-sm text-dark-400 mb-1">Access Token</label>
            <input
              type="password"
              value={dockerFormData.auth_password}
              onChange={(e) =>
                setDockerFormData({ ...dockerFormData, auth_password: e.target.value })
              }
              className="input"
              placeholder={editingId ? '(unchanged)' : 'Personal access token'}
            />
          </div>
        );
      case 'aws':
        return (
          <>
            <div>
              <label className="block text-sm text-dark-400 mb-1">AWS Region</label>
              <input
                type="text"
                value={dockerFormData.aws_region}
                onChange={(e) =>
                  setDockerFormData({ ...dockerFormData, aws_region: e.target.value })
                }
                className="input"
                placeholder="us-east-1"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">AWS Access Key ID</label>
              <input
                type="text"
                value={dockerFormData.aws_access_key}
                onChange={(e) =>
                  setDockerFormData({ ...dockerFormData, aws_access_key: e.target.value })
                }
                className="input"
                placeholder="AKIAIOSFODNN7EXAMPLE"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">AWS Secret Access Key</label>
              <input
                type="password"
                value={dockerFormData.aws_secret_key}
                onChange={(e) =>
                  setDockerFormData({ ...dockerFormData, aws_secret_key: e.target.value })
                }
                className="input"
                placeholder={editingId ? '(unchanged)' : 'Secret access key'}
              />
            </div>
          </>
        );
      case 'gcp':
        return (
          <div>
            <label className="block text-sm text-dark-400 mb-1">
              Service Account JSON
            </label>
            <textarea
              value={dockerFormData.gcp_service_account_json}
              onChange={(e) =>
                setDockerFormData({
                  ...dockerFormData,
                  gcp_service_account_json: e.target.value,
                })
              }
              className="input min-h-[120px] font-mono text-sm"
              placeholder={editingId ? '(unchanged)' : 'Paste service account JSON here'}
            />
          </div>
        );
      case 'azure':
        return (
          <>
            <div>
              <label className="block text-sm text-dark-400 mb-1">Tenant ID</label>
              <input
                type="text"
                value={dockerFormData.azure_tenant_id}
                onChange={(e) =>
                  setDockerFormData({ ...dockerFormData, azure_tenant_id: e.target.value })
                }
                className="input"
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">Client ID</label>
              <input
                type="text"
                value={dockerFormData.azure_client_id}
                onChange={(e) =>
                  setDockerFormData({ ...dockerFormData, azure_client_id: e.target.value })
                }
                className="input"
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">Client Secret</label>
              <input
                type="password"
                value={dockerFormData.azure_client_secret}
                onChange={(e) =>
                  setDockerFormData({
                    ...dockerFormData,
                    azure_client_secret: e.target.value,
                  })
                }
                className="input"
                placeholder={editingId ? '(unchanged)' : 'Client secret'}
              />
            </div>
          </>
        );
      default:
        return null;
    }
  };

  const currentRepos = activeTab === 'helm' ? helmRepos : dockerRepos;
  const isLoading = activeTab === 'helm' ? helmApi.loading : dockerApi.loading;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gold-400">Repositories</h1>
          <p className="text-dark-400 mt-1">
            Manage Helm repositories and Docker registries for pull-through caching
          </p>
        </div>
        <Button onClick={handleAddRepository}>+ Add Repository</Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-dark-900 p-1 rounded-lg w-fit">
        <button
          onClick={() => setActiveTab('helm')}
          className={`px-4 py-2 rounded-md font-medium transition-colors ${
            activeTab === 'helm'
              ? 'bg-gold-400 text-dark-950'
              : 'text-dark-300 hover:text-gold-400'
          }`}
        >
          Helm Repositories
        </button>
        <button
          onClick={() => setActiveTab('docker')}
          className={`px-4 py-2 rounded-md font-medium transition-colors ${
            activeTab === 'docker'
              ? 'bg-gold-400 text-dark-950'
              : 'text-dark-300 hover:text-gold-400'
          }`}
        >
          Docker Registries
        </button>
      </div>

      {/* Repositories Table */}
      <Card>
        {isLoading ? (
          <div className="animate-pulse space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-dark-700 rounded"></div>
            ))}
          </div>
        ) : currentRepos.length === 0 ? (
          <div className="text-center py-8 text-dark-400">
            No {activeTab === 'helm' ? 'Helm repositories' : 'Docker registries'} configured
          </div>
        ) : activeTab === 'helm' ? (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Category</th>
                <th>URL</th>
                <th>Status</th>
                <th>Last Synced</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {helmRepos.map((repo) => (
                <tr key={repo.id}>
                  <td>
                    <div className="flex items-center gap-2">
                      <span className="text-gold-400 font-medium">{repo.name}</span>
                      {repo.is_builtin && (
                        <span className="px-2 py-1 bg-gold-400/10 text-gold-400 text-xs rounded border border-gold-400/30">
                          Built-in
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="text-dark-300">{repo.category || 'N/A'}</td>
                  <td className="text-dark-400 truncate max-w-xs">{repo.url}</td>
                  <td>
                    <span
                      className={`inline-flex items-center gap-1 ${
                        repo.is_enabled ? 'text-green-400' : 'text-dark-500'
                      }`}
                    >
                      {repo.is_enabled ? '● Enabled' : '○ Disabled'}
                    </span>
                  </td>
                  <td className="text-dark-400 text-sm">
                    {repo.last_synced
                      ? new Date(repo.last_synced).toLocaleDateString()
                      : 'Never'}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleSyncRepository(repo.id)}
                        disabled={syncing === repo.id}
                        className="text-blue-400 hover:text-blue-300 disabled:text-dark-500"
                      >
                        {syncing === repo.id ? 'Syncing...' : 'Sync'}
                      </button>
                      <button
                        onClick={() => handleEditHelmRepository(repo)}
                        className="text-gold-400 hover:text-gold-300"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDeleteRepository(repo.id, repo.is_builtin)}
                        disabled={repo.is_builtin}
                        className={`${
                          repo.is_builtin
                            ? 'text-dark-500 cursor-not-allowed'
                            : 'text-red-400 hover:text-red-300'
                        }`}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>URL</th>
                <th>Auth</th>
                <th>Status</th>
                <th>Connection</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {dockerRepos.map((registry) => (
                <tr key={registry.id}>
                  <td>
                    <div className="flex items-center gap-2">
                      <span className="text-gold-400 font-medium">{registry.name}</span>
                      {registry.is_builtin && (
                        <span className="px-2 py-1 bg-gold-400/10 text-gold-400 text-xs rounded border border-gold-400/30">
                          Built-in
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="text-dark-300">
                    {REGISTRY_TYPES.find((t) => t.value === registry.registry_type)?.label ||
                      registry.registry_type}
                  </td>
                  <td className="text-dark-400 truncate max-w-xs">{registry.url}</td>
                  <td className="text-dark-300">
                    {AUTH_TYPES.find((t) => t.value === registry.auth_type)?.label ||
                      registry.auth_type}
                  </td>
                  <td>
                    <button
                      onClick={() => handleToggleEnabled(registry.id, registry.is_enabled)}
                      disabled={registry.is_builtin}
                      className={`inline-flex items-center gap-1 ${
                        registry.is_enabled ? 'text-green-400' : 'text-dark-500'
                      } ${!registry.is_builtin ? 'hover:opacity-80 cursor-pointer' : ''}`}
                    >
                      {registry.is_enabled ? '● Enabled' : '○ Disabled'}
                    </button>
                  </td>
                  <td>
                    {registry.connection_test_success !== undefined && (
                      <span
                        className={`text-sm ${
                          registry.connection_test_success
                            ? 'text-green-400'
                            : 'text-red-400'
                        }`}
                        title={registry.connection_test_error || 'Connection OK'}
                      >
                        {registry.connection_test_success ? '✓ OK' : '✗ Failed'}
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleTestConnection(registry.id)}
                        disabled={testing === registry.id}
                        className="text-blue-400 hover:text-blue-300 disabled:text-dark-500"
                      >
                        {testing === registry.id ? 'Testing...' : 'Test'}
                      </button>
                      <button
                        onClick={() => handleEditDockerRegistry(registry)}
                        className="text-gold-400 hover:text-gold-300"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDeleteRepository(registry.id, registry.is_builtin)}
                        disabled={registry.is_builtin}
                        className={`${
                          registry.is_builtin
                            ? 'text-dark-500 cursor-not-allowed'
                            : 'text-red-400 hover:text-red-300'
                        }`}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Add/Edit Repository Modal */}
      {showModal && activeTab === 'helm' && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="card w-full max-w-md">
            <h2 className="text-xl font-bold text-gold-400 mb-4">
              {editingId ? 'Edit Helm Repository' : 'Add Helm Repository'}
            </h2>
            <form onSubmit={handleSaveHelmRepository} className="space-y-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">Name</label>
                <input
                  type="text"
                  value={helmFormData.name}
                  onChange={(e) => setHelmFormData({ ...helmFormData, name: e.target.value })}
                  className="input"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">URL</label>
                <input
                  type="url"
                  value={helmFormData.url}
                  onChange={(e) => setHelmFormData({ ...helmFormData, url: e.target.value })}
                  className="input"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">Category</label>
                <input
                  type="text"
                  value={helmFormData.category}
                  onChange={(e) =>
                    setHelmFormData({ ...helmFormData, category: e.target.value })
                  }
                  className="input"
                  placeholder="e.g., monitoring, databases"
                />
              </div>
              <div className="flex justify-end gap-3 mt-6">
                <Button type="button" variant="secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" isLoading={helmApi.loading}>
                  {editingId ? 'Update' : 'Add'} Repository
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add/Edit Docker Registry Modal */}
      {showModal && activeTab === 'docker' && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto py-8">
          <div className="card w-full max-w-lg mx-4">
            <h2 className="text-xl font-bold text-gold-400 mb-4">
              {editingId ? 'Edit Docker Registry' : 'Add Docker Registry'}
            </h2>
            <form onSubmit={handleSaveDockerRegistry} className="space-y-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">Name</label>
                <input
                  type="text"
                  value={dockerFormData.name}
                  onChange={(e) =>
                    setDockerFormData({ ...dockerFormData, name: e.target.value })
                  }
                  className="input"
                  placeholder="my-ecr-registry"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-dark-400 mb-1">Registry Type</label>
                <select
                  value={dockerFormData.registry_type}
                  onChange={(e) => handleRegistryTypeChange(e.target.value as RegistryType)}
                  className="input"
                >
                  {REGISTRY_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-dark-400 mb-1">URL</label>
                <input
                  type="url"
                  value={dockerFormData.url}
                  onChange={(e) =>
                    setDockerFormData({ ...dockerFormData, url: e.target.value })
                  }
                  className="input"
                  placeholder="https://registry.example.com"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-dark-400 mb-1">Authentication Type</label>
                <select
                  value={dockerFormData.auth_type}
                  onChange={(e) =>
                    setDockerFormData({
                      ...dockerFormData,
                      auth_type: e.target.value as RegistryAuthType,
                    })
                  }
                  className="input"
                >
                  {AUTH_TYPES.map((auth) => (
                    <option key={auth.value} value={auth.value}>
                      {auth.label} - {auth.description}
                    </option>
                  ))}
                </select>
              </div>

              {/* Dynamic auth fields */}
              {renderAuthFields()}

              {/* Test result */}
              {testResult && (
                <div
                  className={`p-3 rounded-lg ${
                    testResult.success
                      ? 'bg-green-900/30 border border-green-500/30'
                      : 'bg-red-900/30 border border-red-500/30'
                  }`}
                >
                  <p
                    className={`text-sm ${
                      testResult.success ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {testResult.message}
                  </p>
                </div>
              )}

              <div className="flex justify-between gap-3 mt-6">
                <div>
                  {editingId && (
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => handleTestConnection(editingId)}
                      isLoading={testing === editingId}
                    >
                      Test Connection
                    </Button>
                  )}
                </div>
                <div className="flex gap-3">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => setShowModal(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" isLoading={dockerApi.loading}>
                    {editingId ? 'Update' : 'Add'} Registry
                  </Button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
