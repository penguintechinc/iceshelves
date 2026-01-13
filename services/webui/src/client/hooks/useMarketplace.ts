import { useState, useCallback } from 'react';
import api from '../lib/api';

// Generic hook for marketplace API calls with loading/error states
export function useMarketplaceApi<T>() {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const execute = useCallback(async (apiCall: () => Promise<T>) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await apiCall();
      setData(result);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An error occurred';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refetch = useCallback(async (apiCall: () => Promise<T>) => {
    return execute(apiCall);
  }, [execute]);

  return { data, error, loading: isLoading, execute, setData, refetch };
}

// Clusters API
export const useClusters = () => {
  const api_state = useMarketplaceApi<any>();

  return {
    ...api_state,
    list: async (page = 1, perPage = 20) => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/clusters', {
          params: { page, per_page: perPage },
        });
        return response.data;
      });
    },
    get: async (clusterId: string) => {
      return api_state.execute(async () => {
        const response = await api.get(`/marketplace/clusters/${clusterId}`);
        return response.data;
      });
    },
    create: async (clusterData: any) => {
      return api_state.execute(async () => {
        const response = await api.post('/marketplace/clusters', clusterData);
        return response.data;
      });
    },
    update: async (clusterId: string, clusterData: any) => {
      return api_state.execute(async () => {
        const response = await api.put(
          `/marketplace/clusters/${clusterId}`,
          clusterData
        );
        return response.data;
      });
    },
    delete: async (clusterId: string) => {
      return api_state.execute(async () => {
        await api.delete(`/marketplace/clusters/${clusterId}`);
        return { success: true };
      });
    },
  };
};

// Helm Repositories API
export const useHelmRepositories = () => {
  const api_state = useMarketplaceApi<any>();

  return {
    ...api_state,
    list: async (page = 1, perPage = 20) => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/helm-repositories', {
          params: { page, per_page: perPage },
        });
        return response.data;
      });
    },
    get: async (repoId: string) => {
      return api_state.execute(async () => {
        const response = await api.get(
          `/marketplace/helm-repositories/${repoId}`
        );
        return response.data;
      });
    },
    create: async (repoData: any) => {
      return api_state.execute(async () => {
        const response = await api.post(
          '/marketplace/helm-repositories',
          repoData
        );
        return response.data;
      });
    },
    update: async (repoId: string, repoData: any) => {
      return api_state.execute(async () => {
        const response = await api.put(
          `/marketplace/helm-repositories/${repoId}`,
          repoData
        );
        return response.data;
      });
    },
    delete: async (repoId: string) => {
      return api_state.execute(async () => {
        await api.delete(`/marketplace/helm-repositories/${repoId}`);
        return { success: true };
      });
    },
    sync: async (repoId: string) => {
      return api_state.execute(async () => {
        const response = await api.post(
          `/marketplace/helm-repositories/${repoId}/sync`,
          {}
        );
        return response.data;
      });
    },
  };
};

// Docker Registries API
export const useDockerRegistries = () => {
  const api_state = useMarketplaceApi<any>();

  return {
    ...api_state,
    list: async (page = 1, perPage = 20) => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/docker-registries', {
          params: { page, per_page: perPage },
        });
        return response.data;
      });
    },
    get: async (registryId: string) => {
      return api_state.execute(async () => {
        const response = await api.get(
          `/marketplace/docker-registries/${registryId}`
        );
        return response.data;
      });
    },
    create: async (registryData: any) => {
      return api_state.execute(async () => {
        const response = await api.post(
          '/marketplace/docker-registries',
          registryData
        );
        return response.data;
      });
    },
    update: async (registryId: string, registryData: any) => {
      return api_state.execute(async () => {
        const response = await api.put(
          `/marketplace/docker-registries/${registryId}`,
          registryData
        );
        return response.data;
      });
    },
    delete: async (registryId: string) => {
      return api_state.execute(async () => {
        await api.delete(`/marketplace/docker-registries/${registryId}`);
        return { success: true };
      });
    },
    testConnection: async (registryId: string) => {
      return api_state.execute(async () => {
        const response = await api.post(
          `/marketplace/docker-registries/${registryId}/test`,
          {}
        );
        return response.data;
      });
    },
    toggle: async (registryId: string, enabled: boolean) => {
      return api_state.execute(async () => {
        const response = await api.patch(
          `/marketplace/docker-registries/${registryId}`,
          { is_enabled: enabled }
        );
        return response.data;
      });
    },
  };
};

// Marketplace Apps API
export const useMarketplaceApps = () => {
  const api_state = useMarketplaceApi<any>();

  return {
    ...api_state,
    list: async (page = 1, perPage = 20, category?: string) => {
      return api_state.execute(async () => {
        const params: any = { page, per_page: perPage };
        if (category) params.category = category;
        const response = await api.get('/marketplace/apps', { params });
        return response.data;
      });
    },
    search: async (query: string, page = 1, perPage = 20) => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/apps/search', {
          params: { q: query, page, per_page: perPage },
        });
        return response.data;
      });
    },
    get: async (appId: string) => {
      return api_state.execute(async () => {
        const response = await api.get(`/marketplace/apps/${appId}`);
        return response.data;
      });
    },
    getVersions: async (appId: string) => {
      return api_state.execute(async () => {
        const response = await api.get(`/marketplace/apps/${appId}/versions`);
        return response.data;
      });
    },
    getCategories: async () => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/apps/categories');
        return response.data;
      });
    },
  };
};

// Deployments API
export const useDeployments = () => {
  const api_state = useMarketplaceApi<any>();

  return {
    ...api_state,
    list: async (clusterId?: string, page = 1, perPage = 20) => {
      return api_state.execute(async () => {
        const params: any = { page, per_page: perPage };
        if (clusterId) params.cluster_id = clusterId;
        const response = await api.get('/marketplace/deployments', { params });
        return response.data;
      });
    },
    get: async (deploymentId: string) => {
      return api_state.execute(async () => {
        const response = await api.get(
          `/marketplace/deployments/${deploymentId}`
        );
        return response.data;
      });
    },
    delete: async (deploymentId: string) => {
      return api_state.execute(async () => {
        await api.delete(`/marketplace/deployments/${deploymentId}`);
        return { success: true };
      });
    },
    upgrade: async (deploymentId: string, upgradeData: any) => {
      return api_state.execute(async () => {
        const response = await api.post(
          `/marketplace/deployments/${deploymentId}/upgrade`,
          upgradeData
        );
        return response.data;
      });
    },
  };
};

// Deployment Wizard API
export const useDeploymentWizard = () => {
  const api_state = useMarketplaceApi<any>();

  return {
    ...api_state,
    start: async (appId: string) => {
      return api_state.execute(async () => {
        const response = await api.post('/marketplace/wizard/start', {
          app_id: appId,
        });
        return response.data;
      });
    },
    getState: async (wizardId: string) => {
      return api_state.execute(async () => {
        const response = await api.get(`/marketplace/wizard/${wizardId}/state`);
        return response.data;
      });
    },
    updateState: async (wizardId: string, stateData: any) => {
      return api_state.execute(async () => {
        const response = await api.put(
          `/marketplace/wizard/${wizardId}/state`,
          stateData
        );
        return response.data;
      });
    },
    preview: async (wizardId: string) => {
      return api_state.execute(async () => {
        const response = await api.post(
          `/marketplace/wizard/${wizardId}/preview`,
          {}
        );
        return response.data;
      });
    },
    deploy: async (wizardId: string) => {
      return api_state.execute(async () => {
        const response = await api.post(
          `/marketplace/wizard/${wizardId}/deploy`,
          {}
        );
        return response.data;
      });
    },
    cancel: async (wizardId: string) => {
      return api_state.execute(async () => {
        await api.post(`/marketplace/wizard/${wizardId}/cancel`, {});
        return { success: true };
      });
    },
  };
};

// Inventory API
export const useInventory = () => {
  const api_state = useMarketplaceApi<any>();

  return {
    ...api_state,
    getAll: async () => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/inventory');
        return response.data;
      });
    },
    getByCluster: async (clusterId: string) => {
      return api_state.execute(async () => {
        const response = await api.get(
          `/marketplace/inventory/cluster/${clusterId}`
        );
        return response.data;
      });
    },
    getSummary: async () => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/inventory/summary');
        return response.data;
      });
    },
    refresh: async (clusterId?: string) => {
      return api_state.execute(async () => {
        const params: any = {};
        if (clusterId) params.cluster_id = clusterId;
        const response = await api.post('/marketplace/inventory/refresh', {
          params,
        });
        return response.data;
      });
    },
  };
};

// Version Tracking API
export const useVersionTracking = () => {
  const api_state = useMarketplaceApi<any>();

  return {
    ...api_state,
    getAll: async () => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/versions');
        return response.data;
      });
    },
    getKubernetes: async () => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/versions/kubernetes');
        return response.data;
      });
    },
    getAddons: async () => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/versions/addons');
        return response.data;
      });
    },
    getUpdates: async () => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/versions/updates');
        return response.data;
      });
    },
    forceCheck: async () => {
      return api_state.execute(async () => {
        const response = await api.post('/marketplace/versions/check', {});
        return response.data;
      });
    },
  };
};

// Notifications API
export const useNotifications = () => {
  const api_state = useMarketplaceApi<any>();

  return {
    ...api_state,
    getPreferences: async () => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/notifications/preferences');
        return response.data;
      });
    },
    updatePreferences: async (preferences: any) => {
      return api_state.execute(async () => {
        const response = await api.put(
          '/marketplace/notifications/preferences',
          preferences
        );
        return response.data;
      });
    },
    listWebhooks: async () => {
      return api_state.execute(async () => {
        const response = await api.get('/marketplace/notifications/webhooks');
        return response.data;
      });
    },
    createWebhook: async (webhookData: any) => {
      return api_state.execute(async () => {
        const response = await api.post(
          '/marketplace/notifications/webhooks',
          webhookData
        );
        return response.data;
      });
    },
    updateWebhook: async (webhookId: string, webhookData: any) => {
      return api_state.execute(async () => {
        const response = await api.put(
          `/marketplace/notifications/webhooks/${webhookId}`,
          webhookData
        );
        return response.data;
      });
    },
    deleteWebhook: async (webhookId: string) => {
      return api_state.execute(async () => {
        await api.delete(`/marketplace/notifications/webhooks/${webhookId}`);
        return { success: true };
      });
    },
    testWebhook: async (webhookId: string) => {
      return api_state.execute(async () => {
        const response = await api.post(
          `/marketplace/notifications/webhooks/${webhookId}/test`,
          {}
        );
        return response.data;
      });
    },
  };
};

// Cloud Detection API
export const useCloudDetection = () => {
  const api_state = useMarketplaceApi<any>();

  return {
    ...api_state,
    detect: async (clusterId: string) => {
      return api_state.execute(async () => {
        const response = await api.post(
          `/marketplace/cloud-detection/${clusterId}/detect`,
          {}
        );
        return response.data;
      });
    },
    getIngressOptions: async (clusterId: string) => {
      return api_state.execute(async () => {
        const response = await api.get(
          `/marketplace/cloud-detection/${clusterId}/ingress`
        );
        return response.data;
      });
    },
    getStorageClasses: async (clusterId: string) => {
      return api_state.execute(async () => {
        const response = await api.get(
          `/marketplace/cloud-detection/${clusterId}/storage`
        );
        return response.data;
      });
    },
    getManagedServices: async (clusterId: string) => {
      return api_state.execute(async () => {
        const response = await api.get(
          `/marketplace/cloud-detection/${clusterId}/services`
        );
        return response.data;
      });
    },
  };
};
