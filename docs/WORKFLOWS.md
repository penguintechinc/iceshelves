# IceShelves CI/CD Workflows

This document describes all GitHub Actions workflows for the IceShelves cloud deployment management system (Go + Python).

## Workflow Overview

IceShelves provides cloud deployment management for LXD, KVM, AWS, and GCP environments. CI/CD automation ensures code quality, security, and reliable deployments across the management platform and deployment agents.

## Core Workflows

### 1. **Continuous Integration (ci.yml)**

**Purpose**: Complete CI pipeline for Go and Python code
**Triggers**:
- Push to main, develop, feature/* branches
- Pull requests to main, develop branches
- Daily schedule: 2 AM UTC

**Environment**:
- Go: 1.23.5 (with matrix testing 1.23.5, 1.24.0)
- Python: 3.12 (for py4web applications)
- Node.js: 18

**Path Detection** - Skips unnecessary jobs:
```yaml
changes:
  go:
    - 'go.mod'
    - 'go.sum'
    - '**/*.go'
    - 'apps/api/**'
    - 'services/**'
  python:
    - 'requirements.txt'
    - '**/*.py'
    - 'apps/iceshelves/**'
  node:
    - 'package.json'
    - 'package-lock.json'
    - 'web/**'
    - '**/*.js'
  docs:
    - 'docs/**'
    - '**/*.md'
```

**Go Testing & Linting** (`go-test`):
- Multiple Go versions (1.23.5, 1.24.0)
- go test with coverage reporting
- golangci-lint with comprehensive checks
- gosec for security vulnerability detection
- go mod tidy validation

**Go Security** (`go-security`):
- gosec static security analysis
- SARIF report generation
- GitHub Security tab integration

**Python Testing** (`python-test`):
- Python 3.12 environment
- py4web application testing
- pytest unit test execution
- Coverage reporting
- Deployment agent testing

**Python Linting** (`python-lint`):
- flake8 linting (PEP 8 compliance)
- black code formatting
- isort import sorting
- mypy type checking
- Deployment script validation

**Python Security** (`python-security`):
- bandit security scanning
- Safety dependency vulnerability checking
- SARIF report generation
- Secrets scanning

**Node.js Testing** (if web UI present):
- Node.js 18 environment
- npm dependency installation
- Jest unit tests
- Code coverage

**Node.js Security**:
- ESLint and Prettier checks
- npm audit dependency scanning

### 2. **Docker Build (docker-build.yml)**

**Purpose**: Build and scan Docker images
**Triggers**: Push to main with .version changes

**Features**:
- Multi-stage builds (golang:1.23-slim, python:3.12-slim base)
- Debian-slim runtime images
- Trivy vulnerability scanning
- Parallel build optimization
- Registry push to ghcr.io

**Services Built**:
- IceShelves Manager (py4web application)
- API service (Go)
- Deployment agent (Python)

**Version Detection**:
- Monitors .version path
- Extracts epoch64 timestamp
- Tags images with semantic version + epoch64
- Skips if version is 0.0.0

### 3. **Version Release (version-release.yml)**

**Purpose**: Automated release creation on version file updates
**Triggers**: Push to main with .version path changes

**Features**:
- .version file path monitoring
- Epoch64 timestamp detection
- Semantic version extraction (vMajor.Minor.Patch)
- Pre-release creation
- Release notes generation
- Duplicate release prevention

**Version Format**: `vMajor.Minor.Patch.epoch64`
**Example**: `1.0.0.1737727200`

**Process**:
1. Checkout repository
2. Read .version file content
3. Extract semantic version (first 3 version segments)
4. Parse epoch64 timestamp (4th segment, Unix timestamp)
5. Validate version > 0.0.0 (skip release if default)
6. Check if release tag already exists (prevent duplicates)
7. Generate release notes with:
   - Semantic version
   - Full version with timestamp
   - Commit SHA
   - Branch reference
8. Create pre-release on GitHub
9. Log release status

### 4. **Deployment (deploy.yml)**

**Purpose**: Deploy to target environments
**Triggers**: Manual workflow dispatch

**Features**:
- Environment selection (dev, staging, production)
- Deployment validation
- Health check verification
- Database migration automation
- Agent deployment coordination
- Rollback capability

**Deployment Process**:
1. Select target environment
2. Validate build artifacts
3. Execute pre-deployment checks
4. Deploy Manager application
5. Deploy API service
6. Deploy agent configurations
7. Run health checks
8. Log deployment status

### 5. **Release (release.yml)**

**Purpose**: Create semantic version releases
**Triggers**: Manual workflow dispatch

**Features**:
- Manual version input
- Release note generation
- Tag creation
- Asset uploading

### 6. **Push (push.yml)**

**Purpose**: Push Docker images to registry
**Triggers**: After successful Docker builds

**Features**:
- Registry authentication
- Multi-tag image push
- Push status reporting

### 7. **GitStream (gitstream.yml)**

**Purpose**: Automated code review and policy enforcement
**Triggers**: Pull request events

**Policies**:
- Code review requirements
- Change validation
- Merge criteria

### 8. **Cron (cron.yml)**

**Purpose**: Scheduled maintenance tasks
**Triggers**: Daily schedule

**Tasks**:
- Dependency updates
- Security scans
- Cache cleanup
- Log archival

## Security Scanning

IceShelves implements multi-layered security scanning:

### Go Security (gosec)
- Detects security vulnerabilities in Go code
- Checks for unsafe patterns
- Integration: SARIF to GitHub Security tab
- Command: `gosec ./...`

### Python Security (bandit)
- Identifies Python security issues
- Checks for hardcoded secrets
- Validates against OWASP top issues
- Command: `bandit -r apps/ scripts/`

### Dependency Scanning
- **Go**: go mod audit (implicit via golangci-lint)
- **Python**: Safety for vulnerability detection
- **Node.js**: npm audit for dependency vulnerabilities

### Container Scanning (Trivy)
- Scans Docker images for CVEs
- Filesystem vulnerability scanning
- SARIF output to GitHub Security
- SBOM generation

## Version Management

### .version File Format
- **Format**: `vMajor.Minor.Patch.epoch64`
- **Example**: `1.0.0.1737727200`
- **epoch64**: Unix timestamp of build (seconds since Jan 1, 1970)

### Update Process
```bash
# Increment epoch64 (development builds)
./scripts/version/update-version.sh

# Increment patch version (bug fixes)
./scripts/version/update-version.sh patch

# Increment minor version (new features)
./scripts/version/update-version.sh minor

# Increment major version (breaking changes)
./scripts/version/update-version.sh major

# Set specific version
./scripts/version/update-version.sh 1 2 3
```

### Deployment Process
1. Update .version file
2. Commit and push to main
3. GitHub Actions automatically:
   - Builds Docker images
   - Runs security scans
   - Creates GitHub release
   - Pushes to registry

## Services Architecture

### Manager Application (py4web)
- Web UI for deployment management
- REST API for automation
- Database backend (PostgreSQL)
- Redis caching

### API Service (Go)
- gRPC service definitions
- REST API endpoints
- Agent coordination
- Event handling

### Deployment Agent (Python)
- Polling agent for air-gapped environments
- Runs on LXD/KVM hosts
- Communicates with Manager
- Handles local deployments

### Cloud Integrations
- AWS EC2 orchestration
- GCP Compute Engine support
- LXD container management
- KVM virtual machine management

## Path-Based Filtering Benefits

Workflows intelligently skip jobs for unrelated changes:
- Pure Go changes: Skip Python/Node jobs
- Pure Python changes: Skip Go/Node jobs
- Documentation changes: Skip code testing
- Reduces CI time and cloud costs

## Environment Variables

**Workflow Configuration**:
- `GO_VERSION`: 1.23.5
- `PYTHON_VERSION`: 3.12
- `NODE_VERSION`: 18
- `REGISTRY`: ghcr.io

**Build Environment** (when deployed):
- `RELEASE_MODE`: false (development), true (production)
- `LICENSE_KEY`: PenguinTech License key
- `DATABASE_URL`: PostgreSQL connection string

## Troubleshooting

### Workflow Issues

**Test Failures**:
1. Check Python 3.12 compatibility (not 3.13)
2. Verify Go version in go.mod
3. Review dependency compatibility
4. Check for flaky tests

**Build Failures**:
1. Validate multi-stage Dockerfile
2. Check base image availability
3. Verify build dependencies
4. Review build logs for specific errors

**Security Scan Failures**:
1. Review vulnerability reports
2. Update vulnerable dependencies
3. Check for false positives
4. Use security exception comments if needed

### Debug Commands

```bash
# View workflow execution
gh run view <run-id> --log

# List recent workflow runs
gh run list --limit 20

# Rerun failed workflow
gh run rerun <run-id>

# Cancel running workflow
gh run cancel <run-id>

# View specific job output
gh run view <run-id> --log --job <job-name>
```

## Best Practices

1. **Keep .version file updated** - Changes automatically trigger releases
2. **Test locally first** - Run tests before pushing
3. **Use feature branches** - All development on feature/* branches
4. **Review security reports** - Monitor GitHub Security tab
5. **Document deployment changes** - Update RELEASE_NOTES.md
6. **Monitor agent health** - Check deployed agents regularly
7. **Keep dependencies updated** - Use Dependabot for automation

## Branch Strategy

- **main**: Production-ready code
  - All PRs require approval
  - Automated security checks required
  - Version changes trigger releases

- **develop**: Development branch
  - Integration point for features
  - CI pipeline runs but allows merge failures

- **feature/***: Feature branches
  - Branched from develop
  - PR to develop for review
  - CI pipeline validates

## Related Documentation

- See [docs/STANDARDS.md](STANDARDS.md) for code quality standards
- See [docs/DEPLOYMENT.md](DEPLOYMENT.md) for deployment procedures
- See [CLAUDE.md](../CLAUDE.md) for development context
- See [docs/ARCHITECTURE.md](ARCHITECTURE.md) for system architecture
- See [README.md](../README.md) for project overview
