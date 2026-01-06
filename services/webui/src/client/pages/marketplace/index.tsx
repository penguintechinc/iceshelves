import { useState, useEffect } from 'react';
import { useMarketplaceApps, useDeployments, useInventory } from '../../hooks/useMarketplace';
import Card from '../../components/Card';
import Button from '../../components/Button';
import type { MarketplaceApp, DeployedApp, InventorySummary } from '../../types/marketplace';

export default function Marketplace() {
  const appsApi = useMarketplaceApps();
  const deploymentsApi = useDeployments();
  const inventoryApi = useInventory();

  const [apps, setApps] = useState<MarketplaceApp[]>([]);
  const [deployments, setDeployments] = useState<DeployedApp[]>([]);
  const [inventory, setInventory] = useState<InventorySummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch initial data
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const [appsData, deploymentsData, inventoryData] = await Promise.all([
          appsApi.list(1, 4),
          deploymentsApi.list(undefined, 1, 5),
          inventoryApi.getSummary(),
        ]);

        setApps(appsData?.items || []);
        setDeployments(deploymentsData?.items || []);
        setInventory(inventoryData || null);
        setError(null);
      } catch (err) {
        setError('Failed to load marketplace data');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

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

  const getUpdateUrgencyColor = (urgency: string): string => {
    switch (urgency) {
      case 'critical':
        return 'text-red-400';
      case 'high':
        return 'text-orange-400';
      case 'medium':
        return 'text-yellow-400';
      case 'low':
        return 'text-blue-400';
      default:
        return 'text-dark-400';
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gold-400 mb-2">App Marketplace</h1>
        <p className="text-dark-400 text-lg">Discover, deploy, and manage applications across your infrastructure</p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-400">
          {error}
        </div>
      )}

      {/* Quick Stats Cards */}
      {!isLoading && inventory && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* Total Apps Available */}
          <Card>
            <div className="text-center">
              <div className="text-4xl font-bold text-gold-400 mb-2">{inventory.total_apps}</div>
              <div className="text-dark-400 text-sm">Total Apps Available</div>
            </div>
          </Card>

          {/* Deployed Apps */}
          <Card>
            <div className="text-center">
              <div className="text-4xl font-bold text-green-400 mb-2">{inventory.running}</div>
              <div className="text-dark-400 text-sm">Deployed Apps</div>
              <div className="text-xs text-dark-500 mt-2">
                {inventory.deploying > 0 && `${inventory.deploying} deploying`}
                {inventory.failed > 0 && (inventory.deploying > 0 ? ', ' : '') + `${inventory.failed} failed`}
              </div>
            </div>
          </Card>

          {/* Updates Available */}
          <Card>
            <div className="text-center">
              <div className={`text-4xl font-bold mb-2 ${inventory.updates_available > 0 ? 'text-yellow-400' : 'text-green-400'}`}>
                {inventory.updates_available}
              </div>
              <div className="text-dark-400 text-sm">Updates Available</div>
            </div>
          </Card>
        </div>
      )}

      {/* Loading State for Stats */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <div className="animate-pulse h-20 bg-dark-700 rounded"></div>
            </Card>
          ))}
        </div>
      )}

      {/* Quick Action Buttons */}
      <div className="mb-8 flex flex-wrap gap-4">
        <Button
          variant="primary"
          onClick={() => window.location.href = '/marketplace/catalog'}
        >
          Browse Catalog
        </Button>
        <Button
          variant="secondary"
          onClick={() => window.location.href = '/marketplace/deployments'}
        >
          View Deployments
        </Button>
        <Button
          variant="secondary"
          onClick={() => alert('Upload Manifest functionality coming soon')}
        >
          Upload Manifest
        </Button>
      </div>

      {/* Recent Deployments */}
      <Card title="Recent Deployments" className="mb-8">
        {isLoading ? (
          <div className="animate-pulse space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-dark-700 rounded"></div>
            ))}
          </div>
        ) : deployments.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-dark-400">No deployments yet. Start by browsing the catalog!</p>
          </div>
        ) : (
          <div className="space-y-3">
            {deployments.slice(0, 5).map((deployment) => (
              <div
                key={deployment.id}
                className="flex items-center justify-between p-4 bg-dark-800 rounded-lg border border-dark-700 hover:border-gold-400/50 transition-colors"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <div>
                      <h4 className="text-gold-400 font-semibold">{deployment.name}</h4>
                      <p className="text-sm text-dark-400">{deployment.namespace}</p>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <div className="text-right">
                    <span className="text-dark-400">Version:</span>
                    <p className="text-gold-400">{deployment.installed_version}</p>
                  </div>
                  <span className={`inline-block px-3 py-1 rounded text-xs ${getStatusBadgeClass(deployment.status)}`}>
                    {deployment.status.charAt(0).toUpperCase() + deployment.status.slice(1)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Featured/Popular Apps */}
      <Card title="Featured Apps">
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse space-y-3">
                <div className="h-32 bg-dark-700 rounded"></div>
                <div className="h-4 bg-dark-700 rounded w-3/4"></div>
                <div className="h-3 bg-dark-700 rounded w-1/2"></div>
              </div>
            ))}
          </div>
        ) : apps.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-dark-400">No apps available yet</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {apps.map((app) => (
              <div
                key={app.id}
                className="p-5 bg-dark-800 rounded-lg border border-dark-700 hover:border-gold-400/50 transition-all hover:shadow-lg"
              >
                {/* App Icon */}
                {app.icon_url && (
                  <div className="mb-4 h-24 w-24 bg-dark-700 rounded-lg flex items-center justify-center overflow-hidden">
                    <img
                      src={app.icon_url}
                      alt={app.app_name}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.currentTarget.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"%3E%3Crect x="3" y="3" width="18" height="18" rx="2"%3E%3C/rect%3E%3C/svg%3E';
                      }}
                    />
                  </div>
                )}

                {/* App Name */}
                <h3 className="text-lg font-semibold text-gold-400 mb-2">{app.app_name}</h3>

                {/* Description */}
                <p className="text-sm text-dark-400 mb-4 line-clamp-2">{app.description}</p>

                {/* Version Info */}
                <div className="mb-4 space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-dark-500">Current:</span>
                    <span className="text-dark-300">{app.app_version}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-dark-500">Latest:</span>
                    <span className={app.latest_version !== app.app_version ? 'text-yellow-400' : 'text-green-400'}>
                      {app.latest_version}
                    </span>
                  </div>
                </div>

                {/* Tags */}
                <div className="mb-4 flex flex-wrap gap-2">
                  <span className="px-2 py-1 text-xs bg-dark-700 text-dark-300 rounded">{app.category}</span>
                  {app.tags.slice(0, 1).map((tag) => (
                    <span key={tag} className="px-2 py-1 text-xs bg-gold-900/30 text-gold-400 rounded">
                      {tag}
                    </span>
                  ))}
                </div>

                {/* Deploy Button */}
                <Button
                  variant="primary"
                  size="sm"
                  className="w-full"
                  onClick={() => window.location.href = `/marketplace/catalog?app=${app.id}`}
                >
                  View Details
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
