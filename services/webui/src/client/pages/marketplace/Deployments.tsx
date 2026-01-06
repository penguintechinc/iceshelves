import { useState, useEffect } from 'react';
import { useDeployments, useClusters } from '../../hooks/useMarketplace';
import Card from '../../components/Card';
import Button from '../../components/Button';
import type { DeployedApp, Cluster } from '../../types/marketplace';

export default function Deployments() {
  const deploymentsApi = useDeployments();
  const clustersApi = useClusters();
  const [deployments, setDeployments] = useState<DeployedApp[]>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [filteredDeployments, setFilteredDeployments] = useState<DeployedApp[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [filters, setFilters] = useState({
    cluster: '' as string,
    namespace: '' as string,
    status: '' as string,
  });

  // Fetch deployments and clusters
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const [deploymentsData, clustersData] = await Promise.all([
          deploymentsApi.list(),
          clustersApi.list(),
        ]);

        setDeployments(deploymentsData?.items || []);
        setClusters(clustersData?.items || []);
        setError(null);
      } catch (err) {
        setError('Failed to load deployments');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  // Apply filters
  useEffect(() => {
    let filtered = [...deployments];

    if (filters.cluster) {
      filtered = filtered.filter((d) => d.cluster_id === filters.cluster);
    }

    if (filters.namespace) {
      filtered = filtered.filter((d) =>
        d.namespace.toLowerCase().includes(filters.namespace.toLowerCase())
      );
    }

    if (filters.status) {
      filtered = filtered.filter((d) => d.status === filters.status);
    }

    setFilteredDeployments(filtered);
  }, [deployments, filters]);

  const getStatusBadgeClass = (status: string): string => {
    switch (status) {
      case 'running':
        return 'bg-green-900/30 text-green-400 border border-green-700';
      case 'deploying':
        return 'bg-blue-900/30 text-blue-400 border border-blue-700';
      case 'failed':
        return 'bg-red-900/30 text-red-400 border border-red-700';
      case 'pending':
        return 'bg-yellow-900/30 text-yellow-400 border border-yellow-700';
      case 'degraded':
        return 'bg-orange-900/30 text-orange-400 border border-orange-700';
      default:
        return 'bg-dark-700 text-dark-300 border border-dark-600';
    }
  };

  const getHealthBadgeClass = (health: string): string => {
    switch (health) {
      case 'healthy':
        return 'text-green-400';
      case 'unhealthy':
        return 'text-red-400';
      case 'degraded':
        return 'text-yellow-400';
      default:
        return 'text-dark-400';
    }
  };

  const handleUpgrade = async (deploymentId: string) => {
    if (!confirm('Are you sure you want to upgrade this deployment?')) return;
    try {
      await deploymentsApi.upgrade(deploymentId, {});
      // Refresh the list
      const updated = await deploymentsApi.list();
      setDeployments(updated?.items || []);
    } catch (err) {
      setError('Failed to upgrade deployment');
    }
  };

  const handleUninstall = async (deploymentId: string) => {
    if (!confirm('Are you sure you want to uninstall this deployment?')) return;
    try {
      await deploymentsApi.delete(deploymentId);
      // Refresh the list
      const updated = await deploymentsApi.list();
      setDeployments(updated?.items || []);
    } catch (err) {
      setError('Failed to uninstall deployment');
    }
  };

  const getClusterName = (clusterId: string): string => {
    const cluster = clusters.find((c) => c.id === clusterId);
    return cluster?.display_name || clusterId;
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gold-400">Deployments</h1>
          <p className="text-dark-400 mt-1">Manage deployed applications across clusters</p>
        </div>
        <Button>+ New Deployment</Button>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-400">
          {error}
        </div>
      )}

      {/* Filters */}
      <Card className="mb-6">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-dark-400 mb-2">Filter by Cluster</label>
            <select
              value={filters.cluster}
              onChange={(e) => setFilters({ ...filters, cluster: e.target.value })}
              className="input"
            >
              <option value="">All Clusters</option>
              {clusters.map((cluster) => (
                <option key={cluster.id} value={cluster.id}>
                  {cluster.display_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-2">Filter by Namespace</label>
            <input
              type="text"
              placeholder="Search namespace..."
              value={filters.namespace}
              onChange={(e) => setFilters({ ...filters, namespace: e.target.value })}
              className="input"
            />
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-2">Filter by Status</label>
            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              className="input"
            >
              <option value="">All Status</option>
              <option value="running">Running</option>
              <option value="deploying">Deploying</option>
              <option value="failed">Failed</option>
              <option value="pending">Pending</option>
              <option value="degraded">Degraded</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Deployments Table */}
      <Card>
        {isLoading ? (
          <div className="animate-pulse space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-dark-700 rounded"></div>
            ))}
          </div>
        ) : filteredDeployments.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-dark-400">No deployments found</p>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Namespace</th>
                <th>Cluster</th>
                <th>Version</th>
                <th>Status</th>
                <th>Health</th>
                <th>Replicas</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDeployments.map((deployment) => (
                <tr key={deployment.id}>
                  <td className="text-gold-400 font-semibold">{deployment.name}</td>
                  <td className="text-dark-300">{deployment.namespace}</td>
                  <td className="text-dark-300">{getClusterName(deployment.cluster_id)}</td>
                  <td className="text-dark-300">{deployment.installed_version}</td>
                  <td>
                    <span className={`inline-block px-3 py-1 rounded text-sm ${getStatusBadgeClass(deployment.status)}`}>
                      {deployment.status.charAt(0).toUpperCase() + deployment.status.slice(1)}
                    </span>
                  </td>
                  <td>
                    <span className={`flex items-center gap-2 ${getHealthBadgeClass(deployment.health_status)}`}>
                      ● {deployment.health_status.charAt(0).toUpperCase() + deployment.health_status.slice(1)}
                    </span>
                  </td>
                  <td className="text-dark-300">
                    <span title={`${deployment.replicas_ready}/${deployment.replicas_desired} ready`}>
                      {deployment.replicas_ready}/{deployment.replicas_desired}
                    </span>
                  </td>
                  <td>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => alert(`View details for ${deployment.name}`)}
                        className="text-gold-400 hover:text-gold-300 transition-colors"
                      >
                        Details
                      </button>
                      <button
                        onClick={() => handleUpgrade(deployment.id)}
                        className="text-blue-400 hover:text-blue-300 transition-colors"
                      >
                        Upgrade
                      </button>
                      <button
                        onClick={() => handleUninstall(deployment.id)}
                        className="text-red-400 hover:text-red-300 transition-colors"
                      >
                        Uninstall
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Summary Stats */}
      {filteredDeployments.length > 0 && (
        <Card className="mt-6">
          <div className="grid grid-cols-5 gap-4">
            <div>
              <p className="text-dark-400 text-sm">Total</p>
              <p className="text-2xl font-bold text-gold-400">{filteredDeployments.length}</p>
            </div>
            <div>
              <p className="text-dark-400 text-sm">Running</p>
              <p className="text-2xl font-bold text-green-400">
                {filteredDeployments.filter((d) => d.status === 'running').length}
              </p>
            </div>
            <div>
              <p className="text-dark-400 text-sm">Deploying</p>
              <p className="text-2xl font-bold text-blue-400">
                {filteredDeployments.filter((d) => d.status === 'deploying').length}
              </p>
            </div>
            <div>
              <p className="text-dark-400 text-sm">Failed</p>
              <p className="text-2xl font-bold text-red-400">
                {filteredDeployments.filter((d) => d.status === 'failed').length}
              </p>
            </div>
            <div>
              <p className="text-dark-400 text-sm">Degraded</p>
              <p className="text-2xl font-bold text-yellow-400">
                {filteredDeployments.filter((d) => d.status === 'degraded').length}
              </p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
