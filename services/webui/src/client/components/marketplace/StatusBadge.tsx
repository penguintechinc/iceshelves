interface StatusBadgeProps {
  status: 'running' | 'failed' | 'deploying' | 'pending' | 'degraded';
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const statusConfig = {
    running: {
      bgColor: 'bg-green-600',
      textColor: 'text-white',
      label: 'Running',
    },
    failed: {
      bgColor: 'bg-red-600',
      textColor: 'text-white',
      label: 'Failed',
    },
    deploying: {
      bgColor: 'bg-blue-600',
      textColor: 'text-white',
      label: 'Deploying',
    },
    pending: {
      bgColor: 'bg-yellow-600',
      textColor: 'text-white',
      label: 'Pending',
    },
    degraded: {
      bgColor: 'bg-orange-600',
      textColor: 'text-white',
      label: 'Degraded',
    },
  };

  const config = statusConfig[status];

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.bgColor} ${config.textColor}`}
    >
      {config.label}
    </span>
  );
}
