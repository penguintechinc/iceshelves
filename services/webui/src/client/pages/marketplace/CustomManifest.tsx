import { useState } from 'react';
import Card from '../../components/Card';

interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  resources: CategorizedResources;
}

interface CategorizedResources {
  configMaps: string[];
  deployments: string[];
  services: string[];
  persistentVolumes: string[];
  ingresses: string[];
  statefulSets: string[];
  daemonSets: string[];
  jobs: string[];
  cronJobs: string[];
  secrets: string[];
  other: { type: string; name: string }[];
}

export default function CustomManifest() {
  const [yamlContent, setYamlContent] = useState('');
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [uploadMethod, setUploadMethod] = useState<'paste' | 'file'>('paste');

  const parseYaml = (yaml: string): object[] => {
    const documents = yaml.split(/^---$/m).filter(doc => doc.trim());
    const resources: object[] = [];

    documents.forEach(doc => {
      try {
        const lines = doc.trim().split('\n');
        const resource: Record<string, unknown> = {};
        let currentKey: string | null = null;
        let indentStack: { key: string; indent: number }[] = [];

        lines.forEach(line => {
          if (!line.trim() || line.trim().startsWith('#')) return;

          const indent = line.search(/\S/);
          const content = line.trim();

          if (content.includes(':')) {
            const [key, ...valueParts] = content.split(':');
            const value = valueParts.join(':').trim();
            currentKey = key.trim();

            while (indentStack.length > 0 && indentStack[indentStack.length - 1].indent >= indent) {
              indentStack.pop();
            }

            if (indentStack.length === 0) {
              resource[currentKey] = value || null;
            }
          }
        });

        if (Object.keys(resource).length > 0) {
          resources.push(resource);
        }
      } catch {
        // Silently handle parsing errors
      }
    });

    return resources;
  };

  const categorizeResources = (resources: object[]): CategorizedResources => {
    const categorized: CategorizedResources = {
      configMaps: [],
      deployments: [],
      services: [],
      persistentVolumes: [],
      ingresses: [],
      statefulSets: [],
      daemonSets: [],
      jobs: [],
      cronJobs: [],
      secrets: [],
      other: [],
    };

    resources.forEach((resource: object) => {
      const res = resource as Record<string, unknown>;
      const kind = (res.kind || 'Unknown') as string;
      const metadata = res.metadata as Record<string, unknown> | undefined;
      const name = (metadata?.name as string) || 'unnamed';

      switch (kind) {
        case 'ConfigMap':
          categorized.configMaps.push(name);
          break;
        case 'Deployment':
          categorized.deployments.push(name);
          break;
        case 'Service':
          categorized.services.push(name);
          break;
        case 'PersistentVolume':
          categorized.persistentVolumes.push(name);
          break;
        case 'Ingress':
          categorized.ingresses.push(name);
          break;
        case 'StatefulSet':
          categorized.statefulSets.push(name);
          break;
        case 'DaemonSet':
          categorized.daemonSets.push(name);
          break;
        case 'Job':
          categorized.jobs.push(name);
          break;
        case 'CronJob':
          categorized.cronJobs.push(name);
          break;
        case 'Secret':
          categorized.secrets.push(name);
          break;
        default:
          categorized.other.push({ type: kind, name });
      }
    });

    return categorized;
  };

  const validateManifest = (yaml: string): ValidationResult => {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Trim and check empty
    if (!yaml.trim()) {
      errors.push('YAML content is empty');
      return {
        valid: false,
        errors,
        warnings,
        resources: {
          configMaps: [],
          deployments: [],
          services: [],
          persistentVolumes: [],
          ingresses: [],
          statefulSets: [],
          daemonSets: [],
          jobs: [],
          cronJobs: [],
          secrets: [],
          other: [],
        },
      };
    }

    // Check for invalid characters
    if (/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(yaml)) {
      errors.push('YAML contains invalid control characters');
    }

    // Parse resources
    let resources: object[] = [];
    try {
      resources = parseYaml(yaml);
    } catch {
      errors.push('Failed to parse YAML. Please check syntax');
    }

    if (resources.length === 0 && errors.length === 0) {
      errors.push('No valid Kubernetes resources found in manifest');
    }

    // Validate each resource
    resources.forEach((resource: object, index: number) => {
      const res = resource as Record<string, unknown>;
      const kind = res.kind as string | undefined;
      const apiVersion = res.apiVersion as string | undefined;
      const metadata = res.metadata as Record<string, unknown> | undefined;
      const name = metadata?.name as string | undefined;

      // Check required fields
      if (!kind) {
        errors.push(`Resource ${index + 1}: Missing 'kind' field`);
      }
      if (!apiVersion) {
        warnings.push(`Resource ${index + 1}: Missing 'apiVersion' field`);
      }
      if (!name) {
        errors.push(`Resource ${index + 1} (${kind || 'Unknown'}): Missing metadata.name`);
      }

      // Check namespace
      const namespace = metadata?.namespace as string | undefined;
      if (!namespace) {
        warnings.push(`Resource ${index + 1} (${kind} ${name}): No namespace specified, will use 'default'`);
      }

      // Validate specific kinds
      if (kind === 'Deployment') {
        const spec = res.spec as Record<string, unknown> | undefined;
        if (!spec?.replicas) {
          warnings.push(`Deployment '${name}': replicas not explicitly set`);
        }
      }
    });

    const categorizedResources = categorizeResources(resources);

    return {
      valid: errors.length === 0,
      errors,
      warnings,
      resources: categorizedResources,
    };
  };

  const handleValidate = async () => {
    setIsValidating(true);
    // Simulate async validation
    await new Promise(resolve => setTimeout(resolve, 300));
    const result = validateManifest(yamlContent);
    setValidationResult(result);
    setIsValidating(false);
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target?.result as string;
        setYamlContent(content);
        setUploadMethod('paste');
      };
      reader.readAsText(file);
    }
  };

  const handleContinue = () => {
    if (validationResult?.valid) {
      console.log('Proceeding to deploy with manifest:', yamlContent);
      // TODO: Navigate to deployment confirmation
    }
  };

  const resourceCount =
    (validationResult?.resources.configMaps.length || 0) +
    (validationResult?.resources.deployments.length || 0) +
    (validationResult?.resources.services.length || 0) +
    (validationResult?.resources.persistentVolumes.length || 0) +
    (validationResult?.resources.ingresses.length || 0) +
    (validationResult?.resources.statefulSets.length || 0) +
    (validationResult?.resources.daemonSets.length || 0) +
    (validationResult?.resources.jobs.length || 0) +
    (validationResult?.resources.cronJobs.length || 0) +
    (validationResult?.resources.secrets.length || 0) +
    (validationResult?.resources.other.length || 0);

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gold-400">Custom Manifest</h1>
        <p className="text-dark-400 mt-2">
          Upload or paste your custom Kubernetes manifests for validation and deployment
        </p>
      </div>

      {/* Upload Options */}
      <div className="grid grid-cols-2 gap-4 mb-8">
        <button
          onClick={() => setUploadMethod('file')}
          className={`p-6 rounded-lg border-2 transition-all ${
            uploadMethod === 'file'
              ? 'border-gold-400 bg-gold-400/10'
              : 'border-dark-600 bg-dark-800 hover:border-dark-500'
          }`}
        >
          <div className="text-center">
            <div className="text-2xl mb-2">📁</div>
            <p className="font-semibold text-gold-400">Upload File</p>
            <p className="text-sm text-dark-400 mt-1">Select a YAML file from your computer</p>
          </div>
        </button>

        <button
          onClick={() => setUploadMethod('paste')}
          className={`p-6 rounded-lg border-2 transition-all ${
            uploadMethod === 'paste'
              ? 'border-gold-400 bg-gold-400/10'
              : 'border-dark-600 bg-dark-800 hover:border-dark-500'
          }`}
        >
          <div className="text-center">
            <div className="text-2xl mb-2">📝</div>
            <p className="font-semibold text-gold-400">Paste YAML</p>
            <p className="text-sm text-dark-400 mt-1">Paste your manifest directly here</p>
          </div>
        </button>
      </div>

      {/* File Upload or Text Area */}
      {uploadMethod === 'file' ? (
        <Card className="mb-8">
          <div className="border-2 border-dashed border-dark-600 rounded-lg p-8 text-center hover:border-gold-400/50 transition-colors">
            <label className="cursor-pointer block">
              <div className="text-4xl mb-3">📤</div>
              <p className="text-gold-400 font-semibold mb-2">Click to upload or drag and drop</p>
              <p className="text-sm text-dark-400">YAML files (*.yaml, *.yml)</p>
              <input
                type="file"
                accept=".yaml,.yml"
                onChange={handleFileUpload}
                className="hidden"
              />
            </label>
          </div>
        </Card>
      ) : (
        <Card className="mb-8">
          <label className="block mb-3">
            <p className="text-sm font-semibold text-gold-400 mb-2">Kubernetes Manifest</p>
            <textarea
              value={yamlContent}
              onChange={(e) => setYamlContent(e.target.value)}
              placeholder="apiVersion: apps/v1&#10;kind: Deployment&#10;metadata:&#10;  name: example&#10;spec:&#10;  replicas: 3&#10;  selector:&#10;    matchLabels:&#10;      app: example&#10;  template:&#10;    metadata:&#10;      labels:&#10;        app: example&#10;    spec:&#10;      containers:&#10;      - name: example&#10;        image: nginx:latest"
              className="w-full h-80 p-4 bg-dark-950 text-dark-100 font-mono text-sm border border-dark-600 rounded-lg resize-none focus:border-gold-400 focus:outline-none"
            />
          </label>
          <p className="text-xs text-dark-500 mt-2">
            Separate multiple resources with '---' on its own line
          </p>
        </Card>
      )}

      {/* Validate Button */}
      <div className="mb-8">
        <button
          onClick={handleValidate}
          disabled={!yamlContent.trim() || isValidating}
          className={`px-6 py-3 rounded-lg font-semibold transition-all ${
            !yamlContent.trim() || isValidating
              ? 'bg-dark-700 text-dark-500 cursor-not-allowed'
              : 'bg-gold-500 text-dark-950 hover:bg-gold-400 active:scale-95'
          }`}
        >
          {isValidating ? 'Validating...' : 'Validate Manifest'}
        </button>
      </div>

      {/* Validation Results */}
      {validationResult && (
        <div className="space-y-6">
          {/* Status Card */}
          <Card className={`border-2 ${validationResult.valid ? 'border-green-600/50 bg-green-900/20' : 'border-red-600/50 bg-red-900/20'}`}>
            <div className="flex items-start gap-4">
              <div className="text-3xl">{validationResult.valid ? '✓' : '✗'}</div>
              <div className="flex-1">
                <p className={`text-lg font-semibold ${validationResult.valid ? 'text-green-400' : 'text-red-400'}`}>
                  {validationResult.valid ? 'Manifest is Valid' : 'Manifest has Errors'}
                </p>
                <p className="text-sm text-dark-300 mt-1">
                  {validationResult.valid
                    ? `Found ${resourceCount} resource${resourceCount !== 1 ? 's' : ''} ready for deployment`
                    : `Found ${validationResult.errors.length} error${validationResult.errors.length !== 1 ? 's' : ''} that need to be fixed`}
                </p>
              </div>
            </div>
          </Card>

          {/* Errors */}
          {validationResult.errors.length > 0 && (
            <Card className="border-red-600/50 bg-red-900/20">
              <div className="mb-3">
                <h3 className="font-semibold text-red-400 text-lg">Errors ({validationResult.errors.length})</h3>
              </div>
              <ul className="space-y-2">
                {validationResult.errors.map((error, idx) => (
                  <li key={idx} className="flex gap-3 text-sm">
                    <span className="text-red-400 font-bold flex-shrink-0">•</span>
                    <span className="text-red-300">{error}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Warnings */}
          {validationResult.warnings.length > 0 && (
            <Card className="border-yellow-600/50 bg-yellow-900/20">
              <div className="mb-3">
                <h3 className="font-semibold text-yellow-400 text-lg">Warnings ({validationResult.warnings.length})</h3>
              </div>
              <ul className="space-y-2">
                {validationResult.warnings.map((warning, idx) => (
                  <li key={idx} className="flex gap-3 text-sm">
                    <span className="text-yellow-400 font-bold flex-shrink-0">⚠</span>
                    <span className="text-yellow-300">{warning}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Categorized Resources */}
          {resourceCount > 0 && (
            <Card className="border-gold-400/30">
              <h3 className="font-semibold text-gold-400 text-lg mb-6">Resources Found</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {validationResult.resources.deployments.length > 0 && (
                  <ResourceCategory
                    title="Deployments"
                    items={validationResult.resources.deployments}
                  />
                )}
                {validationResult.resources.services.length > 0 && (
                  <ResourceCategory
                    title="Services"
                    items={validationResult.resources.services}
                  />
                )}
                {validationResult.resources.statefulSets.length > 0 && (
                  <ResourceCategory
                    title="StatefulSets"
                    items={validationResult.resources.statefulSets}
                  />
                )}
                {validationResult.resources.daemonSets.length > 0 && (
                  <ResourceCategory
                    title="DaemonSets"
                    items={validationResult.resources.daemonSets}
                  />
                )}
                {validationResult.resources.configMaps.length > 0 && (
                  <ResourceCategory
                    title="ConfigMaps"
                    items={validationResult.resources.configMaps}
                  />
                )}
                {validationResult.resources.secrets.length > 0 && (
                  <ResourceCategory
                    title="Secrets"
                    items={validationResult.resources.secrets}
                  />
                )}
                {validationResult.resources.persistentVolumes.length > 0 && (
                  <ResourceCategory
                    title="PersistentVolumes"
                    items={validationResult.resources.persistentVolumes}
                  />
                )}
                {validationResult.resources.ingresses.length > 0 && (
                  <ResourceCategory
                    title="Ingresses"
                    items={validationResult.resources.ingresses}
                  />
                )}
                {validationResult.resources.jobs.length > 0 && (
                  <ResourceCategory
                    title="Jobs"
                    items={validationResult.resources.jobs}
                  />
                )}
                {validationResult.resources.cronJobs.length > 0 && (
                  <ResourceCategory
                    title="CronJobs"
                    items={validationResult.resources.cronJobs}
                  />
                )}
                {validationResult.resources.other.length > 0 && (
                  <ResourceCategory
                    title="Other"
                    items={validationResult.resources.other.map(r => `${r.type}: ${r.name}`)}
                  />
                )}
              </div>
            </Card>
          )}

          {/* Continue Button */}
          {validationResult.valid && (
            <div className="flex gap-4">
              <button
                onClick={handleContinue}
                className="flex-1 px-6 py-3 bg-gold-500 text-dark-950 font-semibold rounded-lg hover:bg-gold-400 active:scale-95 transition-all"
              >
                Continue to Deploy
              </button>
              <button
                onClick={() => {
                  setValidationResult(null);
                  setYamlContent('');
                }}
                className="px-6 py-3 bg-dark-700 text-dark-300 font-semibold rounded-lg hover:bg-dark-600 transition-all"
              >
                Reset
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface ResourceCategoryProps {
  title: string;
  items: string[];
}

function ResourceCategory({ title, items }: ResourceCategoryProps) {
  return (
    <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
      <p className="text-sm font-semibold text-gold-400 mb-3">{title}</p>
      <ul className="space-y-1.5">
        {items.map((item, idx) => (
          <li key={idx} className="text-xs text-dark-300 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-gold-500"></span>
            <span className="truncate">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
