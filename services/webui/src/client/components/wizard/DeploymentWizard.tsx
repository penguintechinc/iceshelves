import React, { useState } from 'react';
import WizardContainer from './WizardContainer';
import Button from '../Button';
import { useDeploymentWizard } from '../../hooks/useDeploymentWizard';
import { useCloudDetection } from '../../hooks/useCloudDetection';

interface DeploymentWizardProps {
  appId: number;
  onComplete: () => void;
  onCancel: () => void;
}

const DeploymentWizard: React.FC<DeploymentWizardProps> = ({
  appId,
  onComplete,
  onCancel,
}) => {
  const [currentStep, setCurrentStep] = useState(0);
  const { config, updateConfig, updateDependencies, updateStorage, updateNetwork } = useDeploymentWizard();
  const { detectedProvider } = useCloudDetection();

  const steps = [
    {
      id: 'cluster',
      title: 'Select Cluster',
      description: 'Choose the target cluster for deployment',
    },
    {
      id: 'dependencies',
      title: 'Configure Dependencies',
      description: 'Select required database and cache services',
    },
    {
      id: 'storage',
      title: 'Configure Storage',
      description: 'Configure persistent volume and storage class',
    },
    {
      id: 'network',
      title: 'Configure Network',
      description: 'Configure network exposure and ingress',
    },
    {
      id: 'review',
      title: 'Review & Deploy',
      description: 'Review configuration and deploy',
    },
  ];

  const clusters = [
    { id: 'prod-us-east-1', name: 'Production - US East 1', provider: 'AWS' },
    { id: 'prod-us-west-2', name: 'Production - US West 2', provider: 'AWS' },
    { id: 'prod-gcp-us-central1', name: 'Production - GCP Central 1', provider: 'GCP' },
    { id: 'staging-us-east-1', name: 'Staging - US East 1', provider: 'AWS' },
    { id: 'dev-local', name: 'Development - Local', provider: 'On-Premise' },
  ];

  const databaseOptions = [
    'MariaDB',
    'MySQL',
    'PostgreSQL',
    'MongoDB',
    'Cloud SQL',
  ];

  const cacheOptions = [
    'Redis',
    'Memcached',
    'Cloud Cache',
  ];

  const storageClasses = [
    'standard',
    'fast',
    'gp2',
    'gp3',
    'pd-standard',
    'pd-ssd',
  ];

  const ingressTypes = [
    { value: 'aws-alb', label: 'AWS Application Load Balancer', provider: 'AWS' },
    { value: 'gcp-alb', label: 'GCP Load Balancer', provider: 'GCP' },
    { value: 'nginx', label: 'NGINX Ingress', provider: 'All' },
    { value: 'cluster-ip', label: 'ClusterIP (Internal)', provider: 'All' },
    { value: 'node-port', label: 'NodePort', provider: 'All' },
    { value: 'marchproxy', label: 'MarchProxy', provider: 'All' },
  ];

  const handleDatabaseToggle = (db: string) => {
    const current = config.dependencies.database;
    const updated = current.includes(db)
      ? current.filter((d) => d !== db)
      : [...current, db];
    updateDependencies('database', updated);
  };

  const handleCacheToggle = (cache: string) => {
    const current = config.dependencies.cache;
    const updated = current.includes(cache)
      ? current.filter((c) => c !== cache)
      : [...current, cache];
    updateDependencies('cache', updated);
  };

  const handleDeploy = async () => {
    // Deployment logic here
    console.log('Deploying with config:', config);
    onComplete();
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <div className="space-y-4">
            <label className="block">
              <span className="text-gray-300 font-medium mb-2 block">
                Target Cluster
              </span>
              <select
                value={config.clusterId}
                onChange={(e) => updateConfig({ clusterId: e.target.value })}
                className="w-full px-4 py-2 bg-dark-900 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-gold-400"
              >
                <option value="">Select a cluster...</option>
                {clusters.map((cluster) => (
                  <option key={cluster.id} value={cluster.id}>
                    {cluster.name} ({cluster.provider})
                  </option>
                ))}
              </select>
            </label>
            {detectedProvider && (
              <div className="mt-4 p-4 bg-gold-400/10 border border-gold-400/30 rounded-lg">
                <p className="text-gold-400 text-sm">
                  Detected cloud provider: <strong>{detectedProvider}</strong>
                </p>
              </div>
            )}
          </div>
        );

      case 1:
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-gold-400 mb-3">
                Database Services
              </h3>
              <div className="grid grid-cols-2 gap-3">
                {databaseOptions.map((db) => (
                  <label
                    key={db}
                    className="flex items-center space-x-3 p-3 bg-dark-900 border border-gray-700 rounded-lg cursor-pointer hover:border-gold-400 transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={config.dependencies.database.includes(db)}
                      onChange={() => handleDatabaseToggle(db)}
                      className="w-4 h-4 text-gold-400 bg-dark-800 border-gray-700 rounded focus:ring-gold-400"
                    />
                    <span className="text-gray-300">{db}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-lg font-semibold text-gold-400 mb-3">
                Cache Services
              </h3>
              <div className="grid grid-cols-2 gap-3">
                {cacheOptions.map((cache) => (
                  <label
                    key={cache}
                    className="flex items-center space-x-3 p-3 bg-dark-900 border border-gray-700 rounded-lg cursor-pointer hover:border-gold-400 transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={config.dependencies.cache.includes(cache)}
                      onChange={() => handleCacheToggle(cache)}
                      className="w-4 h-4 text-gold-400 bg-dark-800 border-gray-700 rounded focus:ring-gold-400"
                    />
                    <span className="text-gray-300">{cache}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-4">
            <label className="block">
              <span className="text-gray-300 font-medium mb-2 block">
                PVC Size
              </span>
              <input
                type="text"
                value={config.storage.pvcSize}
                onChange={(e) => updateStorage({ pvcSize: e.target.value })}
                placeholder="e.g., 10Gi, 50Gi, 100Gi"
                className="w-full px-4 py-2 bg-dark-900 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-gold-400"
              />
              <p className="text-gray-400 text-sm mt-1">
                Specify size with unit (Gi, Mi, Ti)
              </p>
            </label>

            <label className="block">
              <span className="text-gray-300 font-medium mb-2 block">
                Storage Class
              </span>
              <select
                value={config.storage.storageClass}
                onChange={(e) => updateStorage({ storageClass: e.target.value })}
                className="w-full px-4 py-2 bg-dark-900 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-gold-400"
              >
                {storageClasses.map((sc) => (
                  <option key={sc} value={sc}>
                    {sc}
                  </option>
                ))}
              </select>
            </label>
          </div>
        );

      case 3:
        return (
          <div className="space-y-4">
            <label className="flex items-center space-x-3 p-4 bg-dark-900 border border-gray-700 rounded-lg cursor-pointer hover:border-gold-400 transition-colors">
              <input
                type="checkbox"
                checked={config.network.isPublic}
                onChange={(e) => updateNetwork({ isPublic: e.target.checked })}
                className="w-5 h-5 text-gold-400 bg-dark-800 border-gray-700 rounded focus:ring-gold-400"
              />
              <div>
                <div className="text-gray-100 font-medium">Public Access</div>
                <div className="text-gray-400 text-sm">
                  Enable public internet access to this deployment
                </div>
              </div>
            </label>

            <label className="block">
              <span className="text-gray-300 font-medium mb-2 block">
                Ingress Type
              </span>
              <select
                value={config.network.ingressType}
                onChange={(e) => updateNetwork({ ingressType: e.target.value })}
                className="w-full px-4 py-2 bg-dark-900 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-gold-400"
              >
                {ingressTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label} - {type.provider}
                  </option>
                ))}
              </select>
            </label>
          </div>
        );

      case 4:
        return (
          <div className="space-y-6">
            <div className="bg-dark-900 border border-gray-700 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-gold-400 mb-4">
                Deployment Summary
              </h3>

              <div className="space-y-4">
                <div>
                  <div className="text-gray-400 text-sm">Cluster</div>
                  <div className="text-gray-100 font-medium">
                    {clusters.find((c) => c.id === config.clusterId)?.name || 'Not selected'}
                  </div>
                </div>

                <div>
                  <div className="text-gray-400 text-sm">Database Services</div>
                  <div className="text-gray-100">
                    {config.dependencies.database.length > 0
                      ? config.dependencies.database.join(', ')
                      : 'None'}
                  </div>
                </div>

                <div>
                  <div className="text-gray-400 text-sm">Cache Services</div>
                  <div className="text-gray-100">
                    {config.dependencies.cache.length > 0
                      ? config.dependencies.cache.join(', ')
                      : 'None'}
                  </div>
                </div>

                <div>
                  <div className="text-gray-400 text-sm">Storage</div>
                  <div className="text-gray-100">
                    {config.storage.pvcSize} ({config.storage.storageClass})
                  </div>
                </div>

                <div>
                  <div className="text-gray-400 text-sm">Network</div>
                  <div className="text-gray-100">
                    {config.network.isPublic ? 'Public' : 'Private'} - {config.network.ingressType}
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-dark-900 border border-gray-700 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-gold-400 mb-4">
                Generated Values Preview
              </h3>
              <pre className="bg-dark-950 p-4 rounded-lg overflow-x-auto text-sm text-gray-300">
{`apiVersion: v1
kind: Namespace
metadata:
  name: app-${appId}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-${appId}-pvc
  namespace: app-${appId}
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ${config.storage.storageClass}
  resources:
    requests:
      storage: ${config.storage.pvcSize}
---
apiVersion: v1
kind: Service
metadata:
  name: app-${appId}-svc
  namespace: app-${appId}
spec:
  type: ${config.network.ingressType === 'cluster-ip' ? 'ClusterIP' : 'LoadBalancer'}
  ports:
    - port: 80
      targetPort: 8080`}
              </pre>
            </div>

            <Button
              onClick={handleDeploy}
              variant="primary"
              className="w-full bg-gold-400 hover:bg-gold-500 text-dark-950 font-semibold py-3"
            >
              Deploy Application
            </Button>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <WizardContainer
      steps={steps}
      currentStep={currentStep}
      onStepChange={setCurrentStep}
      onComplete={onComplete}
      onCancel={onCancel}
    >
      {renderStepContent()}
    </WizardContainer>
  );
};

export default DeploymentWizard;
