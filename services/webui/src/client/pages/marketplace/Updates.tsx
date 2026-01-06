import { useState, useEffect } from 'react';
import { useVersionTracking } from '../../hooks/useMarketplace';
import Card from '../../components/Card';

interface Update {
  id: string;
  type: 'kubernetes' | 'addons' | 'apps';
  resourceName: string;
  currentVersion: string;
  latestVersion: string;
  urgency: 'critical' | 'high' | 'medium' | 'low';
  releaseNotes?: string;
  releaseNotesUrl?: string;
}

interface UpdatesData {
  kubernetes: Update[];
  addons: Update[];
  apps: Update[];
  summary: {
    totalUpdates: number;
    criticalCount: number;
    highCount: number;
    mediumCount: number;
    lowCount: number;
    lastChecked?: string;
  };
}

const urgencyConfig = {
  critical: {
    color: 'bg-red-900/20 border-red-500/50 text-red-400',
    badge: 'bg-red-500 text-white',
    label: 'Critical',
  },
  high: {
    color: 'bg-orange-900/20 border-orange-500/50 text-orange-400',
    badge: 'bg-orange-500 text-white',
    label: 'High',
  },
  medium: {
    color: 'bg-yellow-900/20 border-yellow-500/50 text-yellow-400',
    badge: 'bg-yellow-500 text-dark-900',
    label: 'Medium',
  },
  low: {
    color: 'bg-blue-900/20 border-blue-500/50 text-blue-400',
    badge: 'bg-blue-500 text-white',
    label: 'Low',
  },
};

export default function Updates() {
  const { getUpdates, forceCheck, loading, error, data } = useVersionTracking();
  const [isChecking, setIsChecking] = useState(false);
  const [expandedType, setExpandedType] = useState<string | null>('kubernetes');

  useEffect(() => {
    loadUpdates();
  }, []);

  const loadUpdates = async () => {
    try {
      await getUpdates();
    } catch (err) {
      console.error('Failed to load updates:', err);
    }
  };

  const handleCheckForUpdates = async () => {
    setIsChecking(true);
    try {
      await forceCheck();
      await loadUpdates();
    } catch (err) {
      console.error('Failed to check for updates:', err);
    } finally {
      setIsChecking(false);
    }
  };

  const updatesData = data as UpdatesData | null;
  const summary = updatesData?.summary || {
    totalUpdates: 0,
    criticalCount: 0,
    highCount: 0,
    mediumCount: 0,
    lowCount: 0,
  };

  const handleUpgrade = (updateId: string, resourceName: string) => {
    console.log(`Upgrading: ${resourceName} (ID: ${updateId})`);
    // TODO: Navigate to upgrade workflow or show upgrade modal
  };

  const handleReleaseNotes = (url?: string, notes?: string) => {
    if (url) {
      window.open(url, '_blank');
    } else if (notes) {
      // TODO: Show release notes modal
      console.log('Release notes:', notes);
    }
  };

  const renderUpdateCard = (update: Update) => (
    <Card key={update.id} className="border-l-4" style={{ borderLeftColor: getUrgencyColor(update.urgency) }}>
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <h4 className="text-lg font-semibold text-gold-400">{update.resourceName}</h4>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-sm text-dark-400">
                {update.currentVersion} → {update.latestVersion}
              </span>
            </div>
          </div>
          <span className={`inline-block px-3 py-1 rounded text-sm font-semibold ${urgencyConfig[update.urgency].badge}`}>
            {urgencyConfig[update.urgency].label}
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 pt-2">
          <button
            onClick={() => handleUpgrade(update.id, update.resourceName)}
            className="btn-primary text-sm"
          >
            Upgrade
          </button>
          {(update.releaseNotesUrl || update.releaseNotes) && (
            <button
              onClick={() => handleReleaseNotes(update.releaseNotesUrl, update.releaseNotes)}
              className="px-3 py-2 rounded-lg text-sm text-gold-400 hover:bg-gold-500/10 transition-colors"
            >
              Release Notes
            </button>
          )}
        </div>
      </div>
    </Card>
  );

  const getUrgencyColor = (urgency: string): string => {
    const colors: Record<string, string> = {
      critical: '#ef4444',
      high: '#f97316',
      medium: '#eab308',
      low: '#3b82f6',
    };
    return colors[urgency] || '#6b7280';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gold-400">Updates</h1>
          <p className="text-dark-400 mt-1">Manage and track updates for your infrastructure</p>
        </div>
        <button
          onClick={handleCheckForUpdates}
          disabled={isChecking || loading}
          className="btn-primary"
        >
          {isChecking ? 'Checking...' : 'Check for Updates'}
        </button>
      </div>

      {/* Last Checked Info */}
      {summary.lastChecked && (
        <div className="text-sm text-dark-400">
          Last checked: {new Date(summary.lastChecked).toLocaleString()}
        </div>
      )}

      {/* Error State */}
      {error && (
        <Card className="border-red-500/50 bg-red-900/20">
          <p className="text-red-400">Error: {error}</p>
        </Card>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <Card>
          <div className="text-center">
            <div className="text-3xl font-bold text-gold-400">{summary.totalUpdates}</div>
            <div className="text-sm text-dark-400 mt-1">Total Updates</div>
          </div>
        </Card>

        <Card>
          <div className="text-center">
            <div className="text-3xl font-bold text-red-400">{summary.criticalCount}</div>
            <div className="text-sm text-dark-400 mt-1">Critical</div>
          </div>
        </Card>

        <Card>
          <div className="text-center">
            <div className="text-3xl font-bold text-orange-400">{summary.highCount}</div>
            <div className="text-sm text-dark-400 mt-1">High</div>
          </div>
        </Card>

        <Card>
          <div className="text-center">
            <div className="text-3xl font-bold text-yellow-400">{summary.mediumCount}</div>
            <div className="text-sm text-dark-400 mt-1">Medium</div>
          </div>
        </Card>

        <Card>
          <div className="text-center">
            <div className="text-3xl font-bold text-blue-400">{summary.lowCount}</div>
            <div className="text-sm text-dark-400 mt-1">Low</div>
          </div>
        </Card>
      </div>

      {/* Loading State */}
      {(loading || !updatesData) && (
        <div className="space-y-6">
          {['Kubernetes', 'Addons', 'Apps'].map((title) => (
            <Card key={title} title={title}>
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="animate-pulse h-20 bg-dark-700 rounded"></div>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Updates by Type */}
      {updatesData && (
        <div className="space-y-6">
          {/* Kubernetes Updates */}
          {updatesData.kubernetes.length > 0 && (
            <Card
              title="Kubernetes"
              actions={
                <button
                  onClick={() =>
                    setExpandedType(expandedType === 'kubernetes' ? null : 'kubernetes')
                  }
                  className="text-dark-400 hover:text-gold-400 transition-colors"
                >
                  {expandedType === 'kubernetes' ? '−' : '+'}
                </button>
              }
            >
              {expandedType === 'kubernetes' && (
                <div className="space-y-3">
                  {updatesData.kubernetes.map((update) => renderUpdateCard(update))}
                </div>
              )}
              {expandedType !== 'kubernetes' && (
                <div className="text-sm text-dark-400">
                  {updatesData.kubernetes.length} update{updatesData.kubernetes.length !== 1 ? 's' : ''} available
                </div>
              )}
            </Card>
          )}

          {/* Addons Updates */}
          {updatesData.addons.length > 0 && (
            <Card
              title="Addons"
              actions={
                <button
                  onClick={() => setExpandedType(expandedType === 'addons' ? null : 'addons')}
                  className="text-dark-400 hover:text-gold-400 transition-colors"
                >
                  {expandedType === 'addons' ? '−' : '+'}
                </button>
              }
            >
              {expandedType === 'addons' && (
                <div className="space-y-3">
                  {updatesData.addons.map((update) => renderUpdateCard(update))}
                </div>
              )}
              {expandedType !== 'addons' && (
                <div className="text-sm text-dark-400">
                  {updatesData.addons.length} update{updatesData.addons.length !== 1 ? 's' : ''} available
                </div>
              )}
            </Card>
          )}

          {/* Apps Updates */}
          {updatesData.apps.length > 0 && (
            <Card
              title="Apps"
              actions={
                <button
                  onClick={() => setExpandedType(expandedType === 'apps' ? null : 'apps')}
                  className="text-dark-400 hover:text-gold-400 transition-colors"
                >
                  {expandedType === 'apps' ? '−' : '+'}
                </button>
              }
            >
              {expandedType === 'apps' && (
                <div className="space-y-3">
                  {updatesData.apps.map((update) => renderUpdateCard(update))}
                </div>
              )}
              {expandedType !== 'apps' && (
                <div className="text-sm text-dark-400">
                  {updatesData.apps.length} update{updatesData.apps.length !== 1 ? 's' : ''} available
                </div>
              )}
            </Card>
          )}

          {/* No Updates State */}
          {updatesData.kubernetes.length === 0 &&
            updatesData.addons.length === 0 &&
            updatesData.apps.length === 0 && (
              <Card>
                <div className="text-center py-8">
                  <div className="text-2xl font-semibold text-gold-400 mb-2">Everything is up to date!</div>
                  <p className="text-dark-400">
                    All your infrastructure components are running the latest versions.
                  </p>
                </div>
              </Card>
            )}
        </div>
      )}
    </div>
  );
}
