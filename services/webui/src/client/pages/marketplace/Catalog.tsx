import { useState, useEffect } from 'react';
import { useMarketplaceApps } from '../../hooks/useMarketplace';
import Card from '../../components/Card';

interface MarketplaceApp {
  id: string;
  name: string;
  version: string;
  description: string;
  category: string;
  icon?: string;
}

interface CatalogResponse {
  items: MarketplaceApp[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

interface CategoryOption {
  id: string;
  name: string;
  count: number;
}

export default function Catalog() {
  const { list, search, data, loading, error, setData } = useMarketplaceApps();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const itemsPerPage = 12;

  // Fetch categories on mount
  useEffect(() => {
    const fetchCategories = async () => {
      try {
        // Mock categories - replace with actual API call
        const mockCategories: CategoryOption[] = [
          { id: 'databases', name: 'Databases', count: 12 },
          { id: 'monitoring', name: 'Monitoring', count: 8 },
          { id: 'networking', name: 'Networking', count: 15 },
          { id: 'storage', name: 'Storage', count: 6 },
          { id: 'security', name: 'Security', count: 10 },
          { id: 'ci-cd', name: 'CI/CD', count: 9 },
          { id: 'messaging', name: 'Messaging', count: 7 },
          { id: 'other', name: 'Other', count: 5 },
        ];
        setCategories(mockCategories);
      } catch (err) {
        console.error('Failed to fetch categories:', err);
      }
    };

    fetchCategories();
  }, []);

  // Fetch apps when page or category changes
  useEffect(() => {
    const fetchApps = async () => {
      try {
        if (searchQuery.trim()) {
          setIsSearching(true);
          await search(searchQuery, currentPage, itemsPerPage);
          setIsSearching(false);
        } else {
          await list(currentPage, itemsPerPage, selectedCategory || undefined);
        }
      } catch (err) {
        console.error('Failed to fetch apps:', err);
      }
    };

    fetchApps();
  }, [currentPage, selectedCategory, searchQuery]);

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setCurrentPage(1);
  };

  const handleCategoryChange = (categoryId: string | null) => {
    setSelectedCategory(categoryId === selectedCategory ? null : categoryId);
    setCurrentPage(1);
  };

  const handleDeploy = (appId: string) => {
    console.log(`Deploying app: ${appId}`);
    // TODO: Navigate to deployment wizard
  };

  const catalogData = data as CatalogResponse | null;
  const apps = catalogData?.items || [];
  const totalPages = catalogData?.total_pages || 1;

  return (
    <div className="flex gap-6">
      {/* Sidebar - Category Filter */}
      <aside className="w-64 flex-shrink-0">
        <Card title="Categories">
          <div className="space-y-2">
            <button
              onClick={() => handleCategoryChange(null)}
              className={`w-full text-left px-4 py-2 rounded-lg transition-colors ${
                selectedCategory === null
                  ? 'bg-gold-500/20 text-gold-400 border border-gold-400/50'
                  : 'text-dark-300 hover:bg-dark-700'
              }`}
            >
              <span>All Categories</span>
            </button>
            {categories.map((category) => (
              <button
                key={category.id}
                onClick={() => handleCategoryChange(category.id)}
                className={`w-full text-left px-4 py-2 rounded-lg transition-colors flex justify-between items-center ${
                  selectedCategory === category.id
                    ? 'bg-gold-500/20 text-gold-400 border border-gold-400/50'
                    : 'text-dark-300 hover:bg-dark-700'
                }`}
              >
                <span>{category.name}</span>
                <span className="text-xs text-dark-400">{category.count}</span>
              </button>
            ))}
          </div>
        </Card>
      </aside>

      {/* Main Content */}
      <div className="flex-1">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gold-400">App Catalog</h1>
          <p className="text-dark-400 mt-1">
            Discover and deploy applications to your clusters
          </p>
        </div>

        {/* Search Bar */}
        <div className="mb-6">
          <input
            type="text"
            placeholder="Search apps by name or description..."
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            className="input w-full"
          />
        </div>

        {/* Results Info */}
        {catalogData && (
          <div className="mb-4 text-sm text-dark-400">
            Showing {apps.length} of {catalogData.total} apps
            {selectedCategory && ` in ${categories.find(c => c.id === selectedCategory)?.name}`}
          </div>
        )}

        {/* Error State */}
        {error && (
          <Card className="border-red-500/50 bg-red-900/20 mb-6">
            <p className="text-red-400">Error: {error}</p>
          </Card>
        )}

        {/* Loading State */}
        {(loading || isSearching) ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 9 }).map((_, i) => (
              <div
                key={i}
                className="card animate-pulse"
              >
                <div className="h-12 bg-dark-700 rounded mb-4"></div>
                <div className="h-4 bg-dark-700 rounded mb-3"></div>
                <div className="h-4 bg-dark-700 rounded mb-4 w-3/4"></div>
                <div className="h-10 bg-dark-700 rounded"></div>
              </div>
            ))}
          </div>
        ) : apps.length > 0 ? (
          <>
            {/* App Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
              {apps.map((app) => (
                <Card key={app.id}>
                  {/* Icon */}
                  {app.icon && (
                    <div className="mb-4 flex justify-center">
                      <img
                        src={app.icon}
                        alt={app.name}
                        className="w-16 h-16 rounded-lg object-cover"
                      />
                    </div>
                  )}

                  {/* App Header */}
                  <div className="mb-3">
                    <h3 className="text-lg font-semibold text-gold-400 truncate">
                      {app.name}
                    </h3>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-sm text-dark-400">v{app.version}</span>
                      <span className="inline-block px-2 py-1 rounded text-xs bg-dark-700 text-dark-300">
                        {app.category}
                      </span>
                    </div>
                  </div>

                  {/* Description */}
                  <p className="text-sm text-dark-300 mb-4 line-clamp-2">
                    {app.description}
                  </p>

                  {/* Deploy Button */}
                  <button
                    onClick={() => handleDeploy(app.id)}
                    className="btn-primary w-full"
                  >
                    Deploy
                  </button>
                </Card>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex justify-center items-center gap-2">
                <button
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                  className={`px-4 py-2 rounded-lg transition-colors ${
                    currentPage === 1
                      ? 'bg-dark-700 text-dark-400 cursor-not-allowed'
                      : 'bg-dark-700 text-gold-400 hover:bg-dark-600'
                  }`}
                >
                  Previous
                </button>

                <div className="flex items-center gap-2">
                  {Array.from({ length: Math.min(5, totalPages) }).map((_, i) => {
                    const pageNum = i + 1;
                    return (
                      <button
                        key={pageNum}
                        onClick={() => setCurrentPage(pageNum)}
                        className={`w-10 h-10 rounded-lg transition-colors ${
                          currentPage === pageNum
                            ? 'bg-gold-500 text-dark-900 font-semibold'
                            : 'bg-dark-700 text-gold-400 hover:bg-dark-600'
                        }`}
                      >
                        {pageNum}
                      </button>
                    );
                  })}
                  {totalPages > 5 && (
                    <>
                      <span className="text-dark-400">...</span>
                      <button
                        onClick={() => setCurrentPage(totalPages)}
                        className={`w-10 h-10 rounded-lg transition-colors ${
                          currentPage === totalPages
                            ? 'bg-gold-500 text-dark-900 font-semibold'
                            : 'bg-dark-700 text-gold-400 hover:bg-dark-600'
                        }`}
                      >
                        {totalPages}
                      </button>
                    </>
                  )}
                </div>

                <button
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={currentPage === totalPages}
                  className={`px-4 py-2 rounded-lg transition-colors ${
                    currentPage === totalPages
                      ? 'bg-dark-700 text-dark-400 cursor-not-allowed'
                      : 'bg-dark-700 text-gold-400 hover:bg-dark-600'
                  }`}
                >
                  Next
                </button>
              </div>
            )}
          </>
        ) : (
          <Card>
            <div className="text-center py-12">
              <p className="text-dark-400 mb-4">No apps found</p>
              {searchQuery && (
                <button
                  onClick={() => handleSearch('')}
                  className="btn-secondary"
                >
                  Clear search
                </button>
              )}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
