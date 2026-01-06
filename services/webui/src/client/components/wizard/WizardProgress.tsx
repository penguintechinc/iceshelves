import React from 'react';

interface WizardStep {
  id: string;
  title: string;
  description?: string;
}

interface WizardProgressProps {
  steps: WizardStep[];
  currentStep: number;
}

const WizardProgress: React.FC<WizardProgressProps> = ({
  steps,
  currentStep,
}) => {
  return (
    <div className="bg-dark-900 px-8 py-6 border-b border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-semibold text-gold-400">
          Step {currentStep + 1} of {steps.length}
        </span>
        <span className="text-sm text-gray-400">
          {Math.round(((currentStep + 1) / steps.length) * 100)}%
        </span>
      </div>

      <div className="flex items-center gap-2">
        {steps.map((step, index) => (
          <React.Fragment key={step.id}>
            <div
              className={`flex-1 h-2 rounded-full transition-colors ${
                index <= currentStep
                  ? 'bg-gold-400'
                  : 'bg-gray-700'
              }`}
            />
            {index < steps.length - 1 && (
              <div className="mx-1" />
            )}
          </React.Fragment>
        ))}
      </div>

      <div className="flex justify-between mt-4">
        {steps.map((step, index) => (
          <div
            key={step.id}
            className={`text-xs font-medium transition-colors ${
              index <= currentStep
                ? 'text-gold-400'
                : 'text-gray-500'
            }`}
          >
            {step.title}
          </div>
        ))}
      </div>
    </div>
  );
};

export default WizardProgress;
