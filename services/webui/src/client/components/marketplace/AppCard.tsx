import Button from '../Button';

interface AppCardProps {
  icon: string | React.ReactNode;
  name: string;
  version: string;
  description: string;
  category: string;
  onDeploy: () => void;
  isDeploying?: boolean;
}

export default function AppCard({
  icon,
  name,
  version,
  description,
  category,
  onDeploy,
  isDeploying = false,
}: AppCardProps) {
  return (
    <div className="bg-dark-900 border border-dark-800 rounded-lg overflow-hidden hover:border-gold-400 transition-all duration-300 hover:shadow-lg hover:shadow-gold-400/10 flex flex-col">
      {/* Header Section */}
      <div className="p-6 flex items-start gap-4 border-b border-dark-800">
        <div className="flex-shrink-0">
          {typeof icon === 'string' ? (
            <div className="w-12 h-12 flex items-center justify-center text-2xl">
              {icon}
            </div>
          ) : (
            <div className="w-12 h-12 flex items-center justify-center bg-dark-800 rounded-lg">
              {icon}
            </div>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-gray-100 truncate">{name}</h3>
          <p className="text-sm text-gray-400 mt-1">v{version}</p>
        </div>
      </div>

      {/* Content Section */}
      <div className="p-6 flex-1">
        <p className="text-sm text-gray-300 line-clamp-3 mb-4">{description}</p>

        <div className="flex items-center justify-between">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gold-400/10 text-gold-400 border border-gold-400/30">
            {category}
          </span>
        </div>
      </div>

      {/* Footer Section */}
      <div className="p-6 border-t border-dark-800">
        <Button
          variant="primary"
          size="md"
          onClick={onDeploy}
          isLoading={isDeploying}
          className="w-full justify-center"
        >
          Deploy
        </Button>
      </div>
    </div>
  );
}
