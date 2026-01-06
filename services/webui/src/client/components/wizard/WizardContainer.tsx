import React, { ReactNode } from 'react';
import WizardProgress from './WizardProgress';
import Button from '../Button';

interface WizardStep {
  id: string;
  title: string;
  description?: string;
}

interface WizardContainerProps {
  steps: WizardStep[];
  currentStep: number;
  onStepChange: (step: number) => void;
  onComplete: () => void;
  onCancel: () => void;
  children: ReactNode;
}

const WizardContainer: React.FC<WizardContainerProps> = ({
  steps,
  currentStep,
  onStepChange,
  onComplete,
  onCancel,
  children,
}) => {
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === steps.length - 1;

  const handlePrevious = () => {
    if (currentStep > 0) {
      onStepChange(currentStep - 1);
    }
  };

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      onStepChange(currentStep + 1);
    }
  };

  const handleComplete = () => {
    onComplete();
  };

  return (
    <div className="w-full bg-dark-950 rounded-lg shadow-lg">
      <WizardProgress steps={steps} currentStep={currentStep} />

      <div className="p-8">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gold-400 mb-2">
            {steps[currentStep]?.title}
          </h2>
          {steps[currentStep]?.description && (
            <p className="text-gray-300">
              {steps[currentStep]?.description}
            </p>
          )}
        </div>

        <div className="mb-8 min-h-64">
          {children}
        </div>

        <div className="flex justify-between gap-4 pt-4 border-t border-gray-700">
          <div className="flex gap-4">
            <Button
              onClick={onCancel}
              variant="secondary"
              className="px-6"
            >
              Cancel
            </Button>
            <Button
              onClick={handlePrevious}
              disabled={isFirstStep}
              variant="secondary"
              className="px-6"
            >
              Previous
            </Button>
          </div>

          <div className="flex gap-4">
            {isLastStep ? (
              <Button
                onClick={handleComplete}
                variant="primary"
                className="px-8 bg-gold-400 hover:bg-gold-500 text-dark-950"
              >
                Complete
              </Button>
            ) : (
              <Button
                onClick={handleNext}
                variant="primary"
                className="px-8 bg-gold-400 hover:bg-gold-500 text-dark-950"
              >
                Next
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default WizardContainer;
