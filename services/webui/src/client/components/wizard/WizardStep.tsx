import React, { ReactNode } from 'react';

interface WizardStepProps {
  title: string;
  description?: string;
  children: ReactNode;
}

const WizardStep: React.FC<WizardStepProps> = ({
  title,
  description,
  children,
}) => {
  return (
    <div className="w-full">
      <div className="mb-6">
        <h3 className="text-xl font-semibold text-gold-400 mb-2">
          {title}
        </h3>
        {description && (
          <p className="text-sm text-gray-400">
            {description}
          </p>
        )}
      </div>

      <div className="bg-dark-900 rounded-lg p-6 border border-gray-700">
        {children}
      </div>
    </div>
  );
};

export default WizardStep;
