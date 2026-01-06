import { useState, useEffect } from 'react';
import { useInventory } from '../../hooks/useMarketplace';
import Card from '../../components/Card';

interface InventorySummary {
  total_apps: number;
  running: number;
  failed: number;
  deploying: number;
  updates_available: number;
}

interface ClusterNode {
  id: string;
  name: string;
  environment: string;
  namespaces: NamespaceNode[];
}

interface NamespaceNode {
  name: string;
  apps: AppNode[];
}

interface AppNode {
  id: string;
  name: string;
  status: 'running' | 'deploying' | 'pending' | 'failed' | 'degraded';
  version: string;
  update_available: boolean;
  available_version?: string;
}

const statusColors = {
  running: 'bg-green-500/10 text-green-400 border-green-500/30',
  deploying: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  pending: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  failed: 'bg-red-500/10 text-red-400 border-red-500/30',
  degraded: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
};

const statusDotColors = {
  running: 'bg-green-400',
  deploying: 'bg-blue-400',
  pending: 'bg-yellow-400',
  failed: 'bg-red-400',
  degraded: 'bg-orange-400',
};

export default function Inventory() {
  const inventory = useInventory();
  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [clusters, setClusters] = useState<ClusterNode[]>([]);
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());
  const [expandedNamespaces, setExpandedNamespaces] = useState<Set<string>>(new Set());
  const [filterEnvironment, setFilterEnvironment] = useState<string>('');
  const [filterCluster, setFilterCluster] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [availableEnvironments, setAvailableEnvironments] = useState<string[]>([]);

  // Fetch inventory data
  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await inventory.getAll();
        if (data) {
          setSummary(data.summary || {
            total_apps: 0,
            running: 0,
            failed: 0,
            deploying: 0,
            updates_available: 0,
          });
          setClusters(data.clusters || []);

          // Extract unique environments
          const envs = new Set<string>();
          (data.clusters || []).forEach((cluster: ClusterNode) => {
            if (cluster.environment) {
              envs.add(cluster.environment);
            }
          });
          setAvailableEnvironments(Array.from(envs));
        }
      } catch (err) {
        console.error('Failed to fetch inventory:', err);
      }
    };

    fetchData();
  }, []);

  // Auto-refresh effect
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(async () => {
      try {
        const data = await inventory.getAll();
        if (data) {
          setSummary(data.summary || summary);
          setClusters(data.clusters || []);
        }
      } catch (err) {
        console.error('Failed to refresh inventory:', err);
      }
    }, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, [autoRefresh, summary]);

  const toggleClusterExpand = (clusterId: string) => {
    const newExpanded = new Set(expandedClusters);
    if (newExpanded.has(clusterId)) {
      newExpanded.delete(clusterId);
    } else {
      newExpanded.add(clusterId);
    }
    setExpandedClusters(newExpanded);
  };

  const toggleNamespaceExpand = (key: string) => {
    const newExpanded = new Set(expandedNamespaces);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedNamespaces(newExpanded);
  };

  const filterApps = (app: AppNode): boolean => {
    if (filterStatus && app.status !== filterStatus) return false;
    if (searchQuery && !app.name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  };

  const filteredClusters = clusters.filter((cluster) => {
    if (filterEnvironment && cluster.environment !== filterEnvironment) return false;
    if (filterCluster && cluster.id !== filterCluster) return false;
    return true;
  });

  const handleRefresh = async () => {
    try {
      const data = await inventory.getAll();
      if (data) {
        setSummary(data.summary || summary);
        setClusters(data.clusters || []);
      }
    } catch (err) {
      console.error('Failed to refresh inventory:', err);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gold-400">Inventory</h1>
        <p className="text-dark-400 mt-1">
          Manage and monitor your deployed applications across clusters
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        <Card title="Total Apps">
          <div className="text-3xl font-bold text-gold-400">
            {summary?.total_apps || 0}
          </div>
        </Card>
        <Card title="Running">
          <div className="text-3xl font-bold text-green-400">
            {summary?.running || 0}
          </div>
        </Card>
        <Card title="Deploying">
          <div className="text-3xl font-bold text-blue-400">
            {summary?.deploying || 0}
          </div>
        </Card>
        <Card title="Updates Available">
          <div className="text-3xl font-bold text-yellow-400">
            {summary?.updates_available || 0}
          </div>
        </Card>
        <Card title="Failed">
          <div className="text-3xl font-bold text-red-400">
            {summary?.failed || 0}
          </div>
        </Card>
      </div>

      {/* Filter and Refresh Bar */}
      <Card
        title="Filters & Actions"
        actions={
          <div className="flex gap-2">
            <button
              onClick={handleRefresh}
              disabled={inventory.loading}
              className="px-4 py-2 bg-gold-400 text-dark-950 rounded font-semibold hover:bg-gold-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {inventory.loading ? 'Refreshing...' : 'Refresh'}
            </button>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-4 h-4 rounded"
              />
              <span className="text-dark-300 text-sm">Auto-refresh (30s)</span>
            </label>
          </div>
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Environment Filter */}
          <div>
            <label className="block text-sm text-dark-400 mb-2">Environment</label>
            <select
              value={filterEnvironment}
              onChange={(e) => setFilterEnvironment(e.target.value)}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded text-dark-300 focus:outline-none focus:border-gold-400"
            >
              <option value="">All Environments</option>
              {availableEnvironments.map((env) => (
                <option key={env} value={env}>
                  {env}
                </option>
              ))}
            </select>
          </div>

          {/* Cluster Filter */}
          <div>
            <label className="block text-sm text-dark-400 mb-2">Cluster</label>
            <select
              value={filterCluster}
              onChange={(e) => setFilterCluster(e.target.value)}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded text-dark-300 focus:outline-none focus:border-gold-400"
            >
              <option value="">All Clusters</option>
              {filteredClusters.map((cluster) => (
                <option key={cluster.id} value={cluster.id}>
                  {cluster.name}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-sm text-dark-400 mb-2">Status</label>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded text-dark-300 focus:outline-none focus:border-gold-400"
            >
              <option value="">All Statuses</option>
              <option value="running">Running</option>
              <option value="deploying">Deploying</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
              <option value="degraded">Degraded</option>
            </select>
          </div>

          {/* Search */}
          <div>
            <label className="block text-sm text-dark-400 mb-2">Search</label>
            <input
              type="text"
              placeholder="Search apps..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded text-dark-300 placeholder-dark-500 focus:outline-none focus:border-gold-400"
            />
          </div>
        </div>
      </Card>

      {/* Tree View */}
      <Card title="Clusters & Applications" className="mt-8">
        <div className="space-y-2">
          {filteredClusters.length === 0 ? (
            <div className="text-dark-400 text-center py-8">
              No clusters found matching your filters
            </div>
          ) : (
            filteredClusters.map((cluster) => (
              <div key={cluster.id} className="border border-dark-700 rounded overflow-hidden">
                {/* Cluster Header */}
                <button
                  onClick={() => toggleClusterExpand(cluster.id)}
                  className="w-full px-4 py-3 bg-dark-800 hover:bg-dark-700 transition-colors flex items-center gap-3 text-left"
                >
                  <span className={`transform transition-transform ${expandedClusters.has(cluster.id) ? 'rotate-90' : ''}`}>
                    ▶
                  </span>
                  <span className="text-gold-400 font-semibold">{cluster.name}</span>
                  <span className="text-dark-500 text-sm">({cluster.environment})</span>
                </button>

                {/* Expanded Content */}
                {expandedClusters.has(cluster.id) && (
                  <div className="bg-dark-900 border-t border-dark-700">
                    {cluster.namespaces.map((namespace) => {
                      const nsKey = `${cluster.id}-${namespace.name}`;
                      const filteredApps = namespace.apps.filter(filterApps);

                      return (
                        <div key={nsKey} className="border-t border-dark-800">
                          {/* Namespace Header */}
                          <button
                            onClick={() => toggleNamespaceExpand(nsKey)}
                            className="w-full px-6 py-2 bg-dark-800 hover:bg-dark-700 transition-colors flex items-center gap-3 text-left"
                          >
                            <span className={`transform transition-transform text-sm ${expandedNamespaces.has(nsKey) ? 'rotate-90' : ''}`}>
                              ▶
                            </span>
                            <span className="text-dark-300">{namespace.name}</span>
                            <span className="text-dark-500 text-sm">({filteredApps.length})</span>
                          </button>

                          {/* Apps List */}
                          {expandedNamespaces.has(nsKey) && (
                            <div className="bg-dark-900">
                              {filteredApps.length === 0 ? (
                                <div className="px-8 py-3 text-dark-500 text-sm">
                                  No apps found
                                </div>
                              ) : (
                                filteredApps.map((app) => (
                                  <div
                                    key={app.id}
                                    className="px-8 py-3 border-t border-dark-800 flex items-center justify-between hover:bg-dark-800 transition-colors group"
                                  >
                                    {/* App Info */}
                                    <div className="flex items-center gap-4 flex-1">
                                      <div className="flex items-center gap-3 flex-1">
                                        {/* Status Dot */}
                                        <div className={`w-2 h-2 rounded-full ${statusDotColors[app.status]}`} />

                                        {/* App Name */}
                                        <div className="flex-1">
                                          <div className="text-dark-300 font-medium">{app.name}</div>
                                          <div className="text-dark-500 text-sm">v{app.version}</div>
                                        </div>
                                      </div>

                                      {/* Status Badge */}
                                      <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${statusColors[app.status]}`}>
                                        {app.status.charAt(0).toUpperCase() + app.status.slice(1)}
                                      </span>

                                      {/* Update Indicator */}
                                      {app.update_available && (
                                        <div className="px-3 py-1 bg-yellow-500/10 text-yellow-400 rounded-full text-xs font-semibold border border-yellow-500/30">
                                          v{app.available_version} available
                                        </div>
                                      )}
                                    </div>

                                    {/* Quick Actions */}
                                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                      <button className="px-3 py-1 text-xs bg-dark-700 hover:bg-dark-600 text-dark-300 rounded transition-colors">
                                        View
                                      </button>
                                      {app.update_available && (
                                        <button className="px-3 py-1 text-xs bg-yellow-600 hover:bg-yellow-500 text-dark-950 rounded font-semibold transition-colors">
                                          Update
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                ))
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
