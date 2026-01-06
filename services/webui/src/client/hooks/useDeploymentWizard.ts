import { useState } from 'react';

export interface DeploymentConfig {
  clusterId: string;
  dependencies: {
    database: string[];
    cache: string[];
  };
  storage: {
    pvcSize: string;
    storageClass: string;
  };
  network: {
    isPublic: boolean;
    ingressType: string;
  };
}

export function useDeploymentWizard() {
  const [config, setConfig] = useState<DeploymentConfig>({
    clusterId: '',
    dependencies: {
      database: [],
      cache: [],
    },
    storage: {
      pvcSize: '10Gi',
      storageClass: 'standard',
    },
    network: {
      isPublic: false,
      ingressType: 'nginx',
    },
  });

  const updateConfig = (updates: Partial<DeploymentConfig>) => {
    setConfig((prev) => ({ ...prev, ...updates }));
  };

  const updateDependencies = (type: 'database' | 'cache', values: string[]) => {
    setConfig((prev) => ({
      ...prev,
      dependencies: {
        ...prev.dependencies,
        [type]: values,
      },
    }));
  };

  const updateStorage = (updates: Partial<DeploymentConfig['storage']>) => {
    setConfig((prev) => ({
      ...prev,
      storage: {
        ...prev.storage,
        ...updates,
      },
    }));
  };

  const updateNetwork = (updates: Partial<DeploymentConfig['network']>) => {
    setConfig((prev) => ({
      ...prev,
      network: {
        ...prev.network,
        ...updates,
      },
    }));
  };

  return {
    config,
    updateConfig,
    updateDependencies,
    updateStorage,
    updateNetwork,
  };
}
