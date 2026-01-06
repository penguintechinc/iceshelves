import { useState, useEffect } from 'react';
import { useClusters } from '../../hooks/useMarketplace';
import Card from '../../components/Card';
import Button from '../../components/Button';
import type { Cluster, CloudProvider } from '../../types/marketplace';

export default function Clusters() {
  const clustersApi = useClusters();
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [healthCheckLoading, setHealthCheckLoading] = useState<string | null>(null);

  // Modal form state
  const [formData, setFormData] = useState({
    name: '',
    display_name: '',
    cloud_provider: 'generic' as CloudProvider,
    region: '',
    k8s_version: '',
    kubeconfig: '',
  });

  const fetchClusters = async () => {
    try {
      const response = await clustersApi.list();
      setClusters(response.items || []);
    } catch (err) {
      console.error('Failed to load clusters');
    }
  };

  useEffect(() => {
    fetchClusters();
  }, []);

  const getCloudProviderIcon = (provider: CloudProvider): JSX.Element => {
    const iconMap = {
      aws: (
        <span className="inline-flex items-center justify-center w-6 h-6 bg-orange-600/20 text-orange-400 rounded text-xs font-bold">
          AWS
        </span>
      ),
      gcp: (
        <span className="inline-flex items-center justify-center w-6 h-6 bg-blue-600/20 text-blue-400 rounded text-xs font-bold">
          GCP
        </span>
      ),
      azure: (
        <span className="inline-flex items-center justify-center w-6 h-6 bg-cyan-600/20 text-cyan-400 rounded text-xs font-bold">
          AZU
        </span>
      ),
      generic: (
        <span className="inline-flex items-center justify-center w-6 h-6 bg-dark-700 text-dark-300 rounded text-xs font-bold">
          K8S
        </span>
      ),
    };
    return iconMap[provider] || iconMap.generic;
  };

  const handleAddCluster = () => {
    setEditingId(null);
    setFormData({
      name: '',
      display_name: '',
      cloud_provider: 'generic',
      region: '',
      k8s_version: '',
      kubeconfig: '',
    });
    setShowModal(true);
  };

  const handleEditCluster = (cluster: Cluster) => {
    setEditingId(cluster.id);
    setFormData({
      name: cluster.name,
      display_name: cluster.display_name,
      cloud_provider: cluster.cloud_provider,
      region: cluster.region,
      k8s_version: cluster.k8s_version,
      kubeconfig: '',
    });
    setShowModal(true);
  };

  const handleSaveCluster = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        await clustersApi.update(editingId, formData);
      } else {
        await clustersApi.create(formData);
      }
      setShowModal(false);
      setFormData({
        name: '',
        display_name: '',
        cloud_provider: 'generic',
        region: '',
        k8s_version: '',
        kubeconfig: '',
      });
      fetchClusters();
    } catch (err) {
      console.error('Failed to save cluster');
    }
  };

  const handleDeleteCluster = async (id: string) => {
    if (!confirm('Are you sure you want to delete this cluster?')) return;

    try {
      await clustersApi.delete(id);
      fetchClusters();
    } catch (err) {
      console.error('Failed to delete cluster');
    }
  };

  const handleSetDefault = async (id: string) => {
    try {
      await clustersApi.update(id, { is_default: true });
      fetchClusters();
    } catch (err) {
      console.error('Failed to set default cluster');
    }
  };

  const handleHealthCheck = async (id: string) => {
    setHealthCheckLoading(id);
    try {
      // Placeholder for health check API endpoint
      // await clustersApi.healthCheck(id);
      fetchClusters();
    } catch (err) {
      console.error('Failed to perform health check');
    } finally {
      setHealthCheckLoading(null);
    }
  };

  const handleKubeconfigChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const content = event.target?.result as string;
        setFormData({ ...formData, kubeconfig: content });
      };
      reader.readAsText(file);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gold-400">Kubernetes Clusters</h1>
          <p className="text-dark-400 mt-1">Manage cluster configurations and deployments</p>
        </div>
        <Button onClick={handleAddCluster}>+ Add Cluster</Button>
      </div>

      {/* Clusters Table */}
      <Card>
        {clustersApi.loading ? (
          <div className="animate-pulse space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-dark-700 rounded"></div>
            ))}
          </div>
        ) : clusters.length === 0 ? (
          <div className="text-center py-8 text-dark-400">
            No Kubernetes clusters configured
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Cloud Provider</th>
                <th>Region</th>
                <th>K8s Version</th>
                <th>Status</th>
                <th>Default</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {clusters.map((cluster) => (
                <tr key={cluster.id}>
                  <td>
                    <div className="flex items-center gap-2">
                      <span className="text-gold-400 font-medium">{cluster.display_name}</span>
                    </div>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      {getCloudProviderIcon(cluster.cloud_provider)}
                      <span className="text-dark-300">{cluster.cloud_provider.toUpperCase()}</span>
                    </div>
                  </td>
                  <td className="text-dark-400">{cluster.region}</td>
                  <td className="text-dark-400">{cluster.k8s_version}</td>
                  <td>
                    <span
                      className={`inline-flex items-center gap-1 ${
                        cluster.is_active ? 'text-green-400' : 'text-red-400'
                      }`}
                    >
                      {cluster.is_active ? '● Active' : '○ Inactive'}
                    </span>
                  </td>
                  <td>
                    {cluster.is_default ? (
                      <span className="px-2 py-1 bg-gold-400/10 text-gold-400 text-xs rounded border border-gold-400/30">
                        Default
                      </span>
                    ) : (
                      <span className="text-dark-500 text-xs">-</span>
                    )}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleEditCluster(cluster)}
                        className="text-gold-400 hover:text-gold-300"
                        title="Edit cluster"
                      >
                        Edit
                      </button>
                      {!cluster.is_default && (
                        <button
                          onClick={() => handleSetDefault(cluster.id)}
                          className="text-blue-400 hover:text-blue-300"
                          title="Set as default cluster"
                        >
                          Set Default
                        </button>
                      )}
                      <button
                        onClick={() => handleHealthCheck(cluster.id)}
                        disabled={healthCheckLoading === cluster.id}
                        className="text-green-400 hover:text-green-300 disabled:text-dark-500"
                        title="Check cluster health"
                      >
                        {healthCheckLoading === cluster.id ? 'Checking...' : 'Health'}
                      </button>
                      <button
                        onClick={() => handleDeleteCluster(cluster.id)}
                        className="text-red-400 hover:text-red-300"
                        title="Delete cluster"
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

      {/* Add/Edit Cluster Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="card w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold text-gold-400 mb-4">
              {editingId ? 'Edit Cluster' : 'Add New Cluster'}
            </h2>
            <form onSubmit={handleSaveCluster} className="space-y-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">Cluster Name (Identifier)</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="input"
                  placeholder="e.g., prod-us-east"
                  required
                  disabled={!!editingId}
                />
              </div>

              <div>
                <label className="block text-sm text-dark-400 mb-1">Display Name</label>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                  className="input"
                  placeholder="e.g., Production US East"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-dark-400 mb-1">Cloud Provider</label>
                <select
                  value={formData.cloud_provider}
                  onChange={(e) => setFormData({ ...formData, cloud_provider: e.target.value as CloudProvider })}
                  className="input"
                  required
                >
                  <option value="generic">Generic Kubernetes</option>
                  <option value="aws">Amazon Web Services (AWS)</option>
                  <option value="gcp">Google Cloud Platform (GCP)</option>
                  <option value="azure">Microsoft Azure</option>
                </select>
              </div>

              <div>
                <label className="block text-sm text-dark-400 mb-1">Region</label>
                <input
                  type="text"
                  value={formData.region}
                  onChange={(e) => setFormData({ ...formData, region: e.target.value })}
                  className="input"
                  placeholder="e.g., us-east-1"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-dark-400 mb-1">Kubernetes Version</label>
                <input
                  type="text"
                  value={formData.k8s_version}
                  onChange={(e) => setFormData({ ...formData, k8s_version: e.target.value })}
                  className="input"
                  placeholder="e.g., 1.28.0"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-dark-400 mb-1">Kubeconfig File</label>
                <input
                  type="file"
                  onChange={handleKubeconfigChange}
                  className="input cursor-pointer"
                  accept=".yaml,.yml,.conf"
                  {...(editingId ? {} : { required: true })}
                />
                <p className="text-xs text-dark-500 mt-1">Upload kubeconfig file for cluster authentication</p>
              </div>

              <div className="flex justify-end gap-3 mt-6">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" isLoading={clustersApi.loading}>
                  {editingId ? 'Update Cluster' : 'Add Cluster'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
