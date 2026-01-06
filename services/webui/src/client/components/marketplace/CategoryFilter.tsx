interface Category {
  id: string;
  name: string;
  count: number;
}

interface CategoryFilterProps {
  categories: Category[];
  selectedId?: string;
  onSelect: (categoryId: string | undefined) => void;
}

export default function CategoryFilter({
  categories,
  selectedId,
  onSelect,
}: CategoryFilterProps) {
  return (
    <aside className="w-64 bg-dark-900 border border-dark-800 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gold-400 mb-6">Categories</h3>

      <div className="space-y-2">
        <button
          onClick={() => onSelect(undefined)}
          className={`w-full flex items-center justify-between px-4 py-2.5 rounded-lg transition-colors text-left ${
            !selectedId
              ? 'bg-dark-800 text-gold-400 border border-gold-400'
              : 'text-gray-300 hover:bg-dark-800'
          }`}
        >
          <span className="font-medium">All Apps</span>
        </button>

        {categories.map((category) => (
          <button
            key={category.id}
            onClick={() => onSelect(category.id)}
            className={`w-full flex items-center justify-between px-4 py-2.5 rounded-lg transition-colors text-left ${
              selectedId === category.id
                ? 'bg-dark-800 text-gold-400 border border-gold-400'
                : 'text-gray-300 hover:bg-dark-800'
            }`}
          >
            <span className="font-medium">{category.name}</span>
            <span
              className={`inline-flex items-center justify-center min-w-6 px-2 py-1 rounded text-xs font-semibold ${
                selectedId === category.id
                  ? 'bg-gold-400 text-dark-950'
                  : 'bg-dark-700 text-gray-300'
              }`}
            >
              {category.count}
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}
