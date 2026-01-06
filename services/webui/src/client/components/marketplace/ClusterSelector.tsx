import { useState } from 'react';

interface Cluster {
  id: string;
  name: string;
  provider: 'aws' | 'gcp' | 'azure' | 'local';
  region?: string;
}

interface ClusterSelectorProps {
  clusters: Cluster[];
  selectedId?: string;
  onSelect: (clusterId: string) => void;
}

export default function ClusterSelector({
  clusters,
  selectedId,
  onSelect,
}: ClusterSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);

  const selectedCluster = clusters.find((c) => c.id === selectedId) || clusters[0];

  const providerIcons = {
    aws: '☁️',
    gcp: '☁️',
    azure: '☁️',
    local: '🖥️',
  };

  const providerLabels = {
    aws: 'AWS',
    gcp: 'GCP',
    azure: 'Azure',
    local: 'Local',
  };

  return (
    <div className="relative inline-block w-full max-w-xs">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-dark-900 border border-dark-800 rounded-lg text-gray-100 hover:border-gold-400 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">{providerIcons[selectedCluster.provider]}</span>
          <div className="text-left">
            <div className="text-sm font-medium">{selectedCluster.name}</div>
            <div className="text-xs text-gray-400">
              {providerLabels[selectedCluster.provider]}
              {selectedCluster.region && ` • ${selectedCluster.region}`}
            </div>
          </div>
        </div>
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 14l-7 7m0 0l-7-7m7 7V3"
          />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-dark-900 border border-dark-800 rounded-lg shadow-lg z-10">
          {clusters.map((cluster) => (
            <button
              key={cluster.id}
              onClick={() => {
                onSelect(cluster.id);
                setIsOpen(false);
              }}
              className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors ${
                cluster.id === selectedId
                  ? 'bg-dark-800 border-l-2 border-gold-400'
                  : 'hover:bg-dark-800'
              }`}
            >
              <span className="text-lg">{providerIcons[cluster.provider]}</span>
              <div className="flex-1">
                <div className="text-sm font-medium text-gray-100">
                  {cluster.name}
                </div>
                <div className="text-xs text-gray-400">
                  {providerLabels[cluster.provider]}
                  {cluster.region && ` • ${cluster.region}`}
                </div>
              </div>
              {cluster.id === selectedId && (
                <svg className="w-5 h-5 text-gold-400" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
