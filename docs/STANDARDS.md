# IceShelves Code Quality and Development Standards

This document defines code quality, security, and development standards for the IceShelves project.

## Table of Contents
1. [Code Quality Standards](#code-quality-standards)
2. [Security Standards](#security-standards)
3. [Testing Standards](#testing-standards)
4. [Documentation Standards](#documentation-standards)
5. [Git Workflow](#git-workflow)
6. [Deployment Standards](#deployment-standards)

## Code Quality Standards

### Language-Specific Requirements

#### Go (1.23.5+)
- **Formatter**: golangci-lint with strict settings
- **Style Guide**: Go Code Review Comments
- **Package Structure**:
  - `cmd/` - Application entry points
  - `internal/` - Private packages
  - `pkg/` - Public packages
- **Requirements**:
  - All code must compile without warnings
  - No unused imports or variables
  - Interface{} usage minimized
  - Error handling required on all I/O operations
  - Comments on exported functions mandatory

**Linting Setup**:
```bash
# Install golangci-lint
curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b $(go env GOPATH)/bin

# Run linting
golangci-lint run ./...

# Auto-fix issues where possible
golangci-lint run --fix ./...
```

**Included Linters**:
- goimports - Import sorting and formatting
- govet - Vet issues detection
- staticcheck - Static analysis
- gosec - Security issues
- gocyclo - Cyclomatic complexity
- misspell - Spelling errors
- unconvert - Unnecessary type conversions
- ineffassign - Ineffective assignments

#### Python (3.12 for py4web, 3.13 for other services)
- **Formatter**: black (line length: 88)
- **Import Sorter**: isort with black profile
- **Linter**: flake8
- **Type Checker**: mypy with strict mode
- **Security**: bandit for vulnerability scanning
- **Requirements**:
  - All code must pass black formatting
  - All code must pass isort import sorting
  - All code must pass flake8 linting
  - Type hints required on function signatures
  - Docstrings on all public functions (PEP 257)

**Linting Setup**:
```bash
# Install linting tools
pip install black isort flake8 mypy bandit

# Format code
black apps/ scripts/

# Sort imports
isort --profile black apps/ scripts/

# Lint
flake8 apps/ scripts/ --max-line-length=88

# Type check
mypy apps/ scripts/ --ignore-missing-imports

# Security check
bandit -r apps/ scripts/
```

**Code Style**:
```python
# Example: Well-formatted Python code
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class Deployment:
    """Represents a cloud deployment."""

    name: str
    cloud_provider: str
    region: str
    instance_count: int = 1
    tags: Optional[List[str]] = None

    def validate(self) -> bool:
        """Validate deployment configuration."""
        if not self.name or not self.region:
            return False
        return True
```

#### Node.js/TypeScript
- **Formatter**: Prettier with 2-space indentation
- **Linter**: ESLint with React rules
- **Type Checking**: TypeScript strict mode
- **Requirements**:
  - All code must pass Prettier formatting
  - All code must pass ESLint
  - TypeScript strict mode enabled
  - No any types without justification
  - Prop types on all React components

**Setup**:
```bash
# Install tools
npm install --save-dev prettier eslint typescript

# Format
prettier --write "src/**/*.{js,ts,tsx}"

# Lint
eslint src/ --fix

# Type check
tsc --noEmit
```

### Code Organization

**Directory Structure**:
```
iceshelves/
├── apps/
│   ├── api/              # Go API service
│   │   ├── cmd/          # Main entry point
│   │   ├── internal/     # Private packages
│   │   └── pkg/          # Public packages
│   └── iceshelves/       # py4web application
│       ├── controllers/  # Request handlers
│       ├── models/       # Data models
│       ├── static/       # Static assets
│       └── views/        # View templates
├── scripts/              # Utility scripts
│   ├── version/          # Version management
│   └── deploy/           # Deployment scripts
├── services/             # Microservices
├── shared/               # Shared utilities
│   ├── licensing/        # License integration
│   ├── database/         # Database utilities
│   └── monitoring/       # Metrics and logging
└── tests/                # Test suites
    ├── unit/             # Unit tests
    └── integration/      # Integration tests
```

### Naming Conventions

**Go**:
- Constants: `CONSTANT_CASE` (exported), `camelCase` (unexported)
- Functions: `CamelCase` (exported), `camelCase` (unexported)
- Interfaces: `ReaderWriter` (end with -er, -or suffixes)
- Packages: lowercase, no underscores

**Python**:
- Constants: `CONSTANT_CASE`
- Functions/methods: `snake_case`
- Classes: `PascalCase`
- Private: prefix with `_`
- Protected: prefix with `__`

**JavaScript/TypeScript**:
- Constants: `CONSTANT_CASE`
- Functions: `camelCase`
- Classes: `PascalCase`
- React components: `PascalCase`
- Props interfaces: `ComponentNameProps`

### DRY Principle

**Rule of Two**: If identical or near-identical code appears in 2+ places, refactor to shared utility.

**Shared Location Options**:
- Go: `shared/` package
- Python: `shared/` module or package
- JavaScript: `src/lib/` utilities

**Examples**:
```go
// Shared Go utility
package shared

func ValidateDeploymentName(name string) error {
    if name == "" {
        return errors.New("deployment name required")
    }
    return nil
}
```

```python
# Shared Python utility
from shared.validation import validate_deployment_name

def create_deployment(name: str) -> Deployment:
    validate_deployment_name(name)
    # ...
```

## Security Standards

### Authentication & Authorization

1. **JWT Tokens**:
   - Algorithm: HS256 or RS256
   - Expiration: 1 hour default
   - Refresh tokens: 7 days
   - Secure cookies: HttpOnly, Secure flags

2. **API Keys**:
   - Format: Minimum 32 random bytes
   - Storage: Hashed in database
   - Rotation: Every 90 days
   - Audit logging: All usage tracked

3. **Multi-Factor Authentication**:
   - TOTP (Time-based One-Time Password)
   - Backup codes for recovery
   - Account recovery procedures

### Input Validation

- **All inputs validated** server-side
- **Whitelist approach**: Define what's allowed, reject everything else
- **Framework validators**: Use py4web/Flask validators
- **Sanitization**: HTML escape output, SQL parameterize queries
- **Length limits**: Enforce maximum field lengths

**Example Validation**:
```python
from pydal.validators import IS_NOT_EMPTY, IS_EMAIL, IS_URL

db.define_table('deployment',
    Field('name', 'string', requires=IS_NOT_EMPTY()),
    Field('region', 'string', requires=IN(['us-east-1', 'us-west-2'])),
    Field('email', 'string', requires=IS_EMAIL()),
)
```

### Secrets Management

1. **Environment Variables** - Never hardcode secrets
   - Use .env files (git-ignored)
   - Load via environment variable service
   - Validate on startup that all required secrets present

2. **No Secrets in Code**:
   - Pre-commit hooks block secret commits
   - GitHub secret scanning enabled
   - Manual code review for credential detection

3. **Secrets Rotation**:
   - API keys: 90-day rotation
   - Database passwords: 180-day rotation
   - JWT signing keys: Annual rotation

### Dependency Security

1. **Vulnerability Scanning**:
   - Go: golangci-lint with gosec
   - Python: Safety + bandit
   - Node.js: npm audit
   - Containers: Trivy scanning

2. **Dependency Updates**:
   - Monitor Dependabot alerts
   - Security patches applied immediately
   - Regular dependency audits (monthly)
   - Test updates in develop branch first

3. **Approved Dependencies Only**:
   - Unmaintained packages: Remove
   - Heavily dependent: Prefer maintained alternatives
   - Custom forks: Document reason and plan

### Network Security

1. **TLS/HTTPS**:
   - Enforce TLS 1.2 minimum, prefer 1.3
   - All external API calls over HTTPS
   - Certificate pinning for critical connections

2. **API Security**:
   - CORS properly configured
   - Rate limiting on all endpoints
   - Request size limits enforced
   - Timeout on long operations

3. **Database Security**:
   - Connection pooling with credentials
   - TLS for remote connections
   - No privilege escalation
   - Row-level security where applicable

## Testing Standards

### Unit Tests

**Coverage Target**: 80%+ of code

**Requirements**:
- Fast execution (< 5 seconds)
- No external dependencies (mock/stub)
- Isolated and repeatable
- Clear test names describing behavior
- Arrange-Act-Assert pattern

**Example Test**:
```python
# tests/unit/test_deployment.py
import pytest
from apps.models import Deployment

class TestDeploymentValidation:
    """Test deployment validation logic."""

    def test_valid_deployment_creation(self):
        """Test creating valid deployment."""
        deployment = Deployment(
            name="prod-cluster",
            region="us-east-1",
            instance_count=3
        )
        assert deployment.validate()

    def test_invalid_deployment_missing_name(self):
        """Test validation fails with missing name."""
        deployment = Deployment(name="", region="us-east-1")
        assert not deployment.validate()

    def test_invalid_region(self):
        """Test validation fails with invalid region."""
        deployment = Deployment(
            name="test",
            region="invalid-region"
        )
        assert not deployment.validate()
```

### Integration Tests

- Test service interactions
- Mock external services
- Database fixtures
- Temporary test databases
- Run in CI pipeline

### End-to-End Tests

- Test complete workflows
- Real environment simulation
- Agent deployment testing
- Rollback scenarios

## Documentation Standards

### Code Comments

1. **Exported Functions/Types**: Comment on declaration
2. **Complex Logic**: Explain why, not what
3. **Assumptions**: Document assumptions clearly
4. **Gotchas**: Document non-obvious behavior

**Example**:
```go
// DeployToAWS deploys the application to AWS EC2.
//
// Region must be a valid AWS region code. The function
// will wait for instance health checks to pass (max 5 min)
// before returning. If deployment fails, instances are
// automatically terminated.
func DeployToAWS(ctx context.Context, config *AWSConfig) error {
    // ...
}
```

### README Standards

- Project description
- Quick start guide
- Architecture overview
- Configuration options
- Troubleshooting section
- Contributing guidelines
- License information

### API Documentation

- Endpoint descriptions
- Request/response schemas
- Error codes and meanings
- Authentication requirements
- Rate limit information
- Example requests/responses

## Git Workflow

### Branch Naming

- `main` - Production-ready code
- `develop` - Development integration branch
- `feature/description` - Feature development
- `bugfix/description` - Bug fixes
- `hotfix/description` - Production hotfixes

### Commit Messages

**Format**:
```
<type>: <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (no logic changes)
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Test additions/modifications
- `chore`: Build, dependencies, tooling

**Example**:
```
feat: Add AWS region validation

- Validate region code against AWS API
- Return descriptive error for invalid regions
- Add unit tests for validation logic

Closes #123
```

### Pull Request Requirements

1. **Code Review**: Minimum 2 approvals
2. **CI Passing**: All tests and linting pass
3. **Security Checks**: No vulnerabilities
4. **No Conflicts**: Branch up-to-date with main
5. **Documentation**: Updated if needed

## Deployment Standards

### Pre-Deployment Checklist

- [ ] All tests passing
- [ ] Security scans passing
- [ ] Code review approved
- [ ] Version number updated
- [ ] RELEASE_NOTES.md updated
- [ ] Database migrations tested
- [ ] Rollback procedure documented

### Deployment Process

1. Create release branch from main
2. Update version in .version
3. Update RELEASE_NOTES.md
4. Create pull request
5. Wait for CI/security checks
6. Merge to main
7. GitHub Actions automatically:
   - Build Docker images
   - Run security scans
   - Create GitHub release
   - Push to registry
8. Verify deployment in target environment

### Rollback Procedure

```bash
# Identify previous stable version
git log --oneline | head -10

# Checkout previous version
git checkout v<previous-version>

# Build and deploy previous version
./scripts/deploy.sh <environment>

# Verify service health
./scripts/health-check.sh <environment>
```

## Performance Standards

### Go Services

- **Startup Time**: < 5 seconds
- **Memory Usage**: < 100MB baseline
- **API Latency**: < 100ms p99
- **Database Queries**: < 50ms p99

### Python Applications

- **Startup Time**: < 10 seconds
- **Memory Usage**: < 200MB baseline
- **API Latency**: < 150ms p99
- **Database Queries**: < 100ms p99

### Monitoring

- Prometheus metrics exposed on /metrics
- Structured logging with correlation IDs
- Error rate alerting (> 1%)
- Latency alerting (p99 > threshold)

## Accessibility Standards

- Web UI: WCAG 2.1 Level AA compliance
- Color contrast: 4.5:1 minimum
- Keyboard navigation: Full support
- Screen reader: Semantic HTML

## Related Standards

- [IceCharts Standards](../IceCharts/docs/STANDARDS.md) - Multi-language standards
- [Elder Standards](../Elder/docs/STANDARDS.md) - Python-focused standards
- [PenguinTech Standards](https://www.penguintech.io/standards) - Company-wide standards
