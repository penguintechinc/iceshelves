import { useState, useEffect } from 'react';
import { useHelmRepositories, useDockerRegistries } from '../../hooks/useMarketplace';
import Card from '../../components/Card';
import Button from '../../components/Button';
import type { HelmRepository, DockerRegistry } from '../../types/marketplace';

export default function Repositories() {
  const [activeTab, setActiveTab] = useState<'helm' | 'docker'>('helm');
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);

  // Helm Repositories
  const helmApi = useHelmRepositories();
  const [helmRepos, setHelmRepos] = useState<HelmRepository[]>([]);

  // Docker Registries
  const dockerApi = useDockerRegistries();
  const [dockerRepos, setDockerRepos] = useState<DockerRegistry[]>([]);

  // Modal form state
  const [formData, setFormData] = useState({
    name: '',
    url: '',
    category: '',
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
    setFormData({ name: '', url: '', category: '' });
    setShowModal(true);
  };

  const handleEditRepository = (repo: HelmRepository | DockerRegistry) => {
    setEditingId(repo.id);
    setFormData({
      name: repo.name,
      url: repo.url,
      category: 'category' in repo ? repo.category : '',
    });
    setShowModal(true);
  };

  const handleSaveRepository = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (activeTab === 'helm') {
        if (editingId) {
          await helmApi.update(editingId, formData);
        } else {
          await helmApi.create(formData);
        }
        fetchHelmRepositories();
      } else {
        if (editingId) {
          await dockerApi.update(editingId, formData);
        } else {
          await dockerApi.create(formData);
        }
        fetchDockerRegistries();
      }
      setShowModal(false);
      setFormData({ name: '', url: '', category: '' });
    } catch (err) {
      console.error('Failed to save repository');
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
      if (activeTab === 'helm') {
        await helmApi.sync(id);
        fetchHelmRepositories();
      }
    } catch (err) {
      console.error('Failed to sync repository');
    } finally {
      setSyncing(null);
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
          <p className="text-dark-400 mt-1">Manage Helm repositories and Docker registries</p>
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
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>{activeTab === 'helm' ? 'Category' : 'Type'}</th>
                <th>URL</th>
                <th>Status</th>
                {activeTab === 'helm' && <th>Last Synced</th>}
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {currentRepos.map((repo) => (
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
                  <td className="text-dark-300">
                    {'category' in repo ? repo.category : ('registry_type' in repo ? repo.registry_type : 'N/A')}
                  </td>
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
                  {activeTab === 'helm' && (
                    <td className="text-dark-400 text-sm">
                      {'last_synced' in repo
                        ? new Date(repo.last_synced).toLocaleDateString()
                        : 'Never'}
                    </td>
                  )}
                  <td>
                    <div className="flex items-center gap-2">
                      {activeTab === 'helm' && (
                        <button
                          onClick={() => handleSyncRepository(repo.id)}
                          disabled={syncing === repo.id}
                          className="text-blue-400 hover:text-blue-300 disabled:text-dark-500"
                        >
                          {syncing === repo.id ? 'Syncing...' : 'Sync'}
                        </button>
                      )}
                      <button
                        onClick={() => handleEditRepository(repo)}
                        className="text-gold-400 hover:text-gold-300"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDeleteRepository(repo.id, repo.is_builtin)}
                        disabled={repo.is_builtin}
                        className={`${
                          repo.is_builtin ? 'text-dark-500 cursor-not-allowed' : 'text-red-400 hover:text-red-300'
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
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="card w-full max-w-md">
            <h2 className="text-xl font-bold text-gold-400 mb-4">
              {editingId
                ? `Edit ${activeTab === 'helm' ? 'Helm Repository' : 'Docker Registry'}`
                : `Add ${activeTab === 'helm' ? 'Helm Repository' : 'Docker Registry'}`}
            </h2>
            <form onSubmit={handleSaveRepository} className="space-y-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="input"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">URL</label>
                <input
                  type="url"
                  value={formData.url}
                  onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                  className="input"
                  required
                />
              </div>
              {activeTab === 'helm' && (
                <div>
                  <label className="block text-sm text-dark-400 mb-1">Category</label>
                  <input
                    type="text"
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    className="input"
                    placeholder="e.g., monitoring, databases"
                  />
                </div>
              )}
              <div className="flex justify-end gap-3 mt-6">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" isLoading={activeTab === 'helm' ? helmApi.loading : dockerApi.loading}>
                  {editingId ? 'Update' : 'Add'} Repository
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
