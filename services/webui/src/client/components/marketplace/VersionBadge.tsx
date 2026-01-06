interface VersionBadgeProps {
  currentVersion: string;
  latestVersion?: string;
}

export default function VersionBadge({
  currentVersion,
  latestVersion,
}: VersionBadgeProps) {
  const hasUpdate = latestVersion && latestVersion !== currentVersion;

  return (
    <div className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-dark-900 border border-dark-800 rounded-md text-sm">
      <span className="text-gray-300">v{currentVersion}</span>
      {hasUpdate && (
        <span className="flex items-center text-gold-400 font-semibold">
          <svg
            className="w-4 h-4 animate-bounce"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
              clipRule="evenodd"
            />
          </svg>
        </span>
      )}
    </div>
  );
}
