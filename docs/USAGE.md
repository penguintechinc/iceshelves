# IceShelves Usage Guide

## Quick Start

### Pull
```bash
# Pull IceShelves image
docker pull ghcr.io/penguintechinc/iceshelves:latest
```

### Run

#### Standalone Container
```bash
docker run -d \
  -p 8001:8000 \
  -e DATABASE_URL="postgresql://user:pass@host/db" \
  -e LICENSE_KEY="PENG-XXXX-XXXX-XXXX-XXXX-ABCD" \
  -e PRODUCT_NAME="iceshelves" \
  --name iceshelves \
  ghcr.io/penguintechinc/iceshelves:latest
```

#### With Local Development
```bash
# Start dependencies
docker-compose up -d postgres redis

# Run IceShelves
make iceshelves-dev
```

### Docker-Compose

**docker-compose.yml**
```yaml
version: '3.8'

services:
  iceshelves:
    image: ghcr.io/penguintechinc/iceshelves:latest
    ports:
      - "8001:8000"
    environment:
      - ICESHELVES_DATABASE_URL=postgresql://postgres:password@postgres:5432/iceshelves
      - LICENSE_KEY=${LICENSE_KEY}
      - PRODUCT_NAME=iceshelves
    volumes:
      - iceshelves_eggs:/app/apps/iceshelves/libraries/eggs
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: iceshelves
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass password

volumes:
  iceshelves_eggs:
  postgres_data:
```

**Start Services**
```bash
docker-compose up -d
```

**Access**
- Web Interface: http://localhost:8001/iceshelves
- Health Check: http://localhost:8001/iceshelves/healthz
- Metrics: http://localhost:8001/iceshelves/metrics

### Helm

**Install Chart** (Coming Soon)
```bash
helm repo add penguintech https://charts.penguintech.io
helm install iceshelves penguintech/iceshelves \
  --set license.key="PENG-XXXX-XXXX-XXXX-XXXX-ABCD" \
  --set postgresql.enabled=true
```

### Terraform

**Example Configuration** (Coming Soon)
```hcl
module "iceshelves" {
  source  = "penguintech/iceshelves/kubernetes"
  version = "1.0.0"

  license_key = var.license_key
  database_url = var.database_url
}
```

## Storage / Persistence

### Required Volumes for Persistence

#### Egg Library
- **Path**: `/app/apps/iceshelves/libraries/eggs`
- **Purpose**: Store egg definitions and cloud-init configurations
- **Type**: Persistent volume
- **Size**: 1-10GB (depending on number of eggs)

#### Database
- **Path**: PostgreSQL data directory
- **Purpose**: Store deployments, clusters, and metadata
- **Type**: Persistent volume
- **Size**: 10GB+ recommended

### Optional Volumes for Advanced Usage

#### Logs
- **Path**: `/var/log/iceshelves`
- **Purpose**: Application logs (if LOG_TO_FILE=true)
- **Type**: Optional persistent volume

## Options

### Environment Variables

#### Core Configuration
- `ICESHELVES_DATABASE_URL` - PostgreSQL connection string (required)
- `LICENSE_KEY` - PenguinTech license key
- `PRODUCT_NAME` - Product identifier (default: iceshelves)
- `VERSION` - Application version

#### Database
- `ICESHELVES_DB_POOL_SIZE` - Connection pool size (default: 10)
- `ICESHELVES_DB_MIGRATE` - Auto-run migrations (default: True)

#### LXD Configuration
- `LXD_DEFAULT_PROTOCOL` - Default protocol (default: lxd)
- `LXD_VERIFY_CERT` - Verify SSL certificates (default: True)
- `LXD_CONNECTION_TIMEOUT` - Connection timeout in seconds (default: 30)

#### KVM/Libvirt
- `LIBVIRT_DEFAULT_URI` - Libvirt URI (default: qemu:///system)
- `ENABLE_KVM_SUPPORT` - Enable KVM features (default: True)

#### Deployment
- `MAX_CONCURRENT_DEPLOYMENTS` - Max parallel deployments (default: 5)
- `DEPLOYMENT_TIMEOUT` - Deployment timeout in seconds (default: 600)
- `DEPLOYMENT_LOG_RETENTION_DAYS` - Log retention (default: 30)

#### Logging
- `LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
- `LOG_TO_FILE` - Write logs to file (default: False)
- `LOG_FILE_PATH` - Log file path

#### Features
- `ENABLE_METRICS` - Enable Prometheus metrics (default: True)
- `ENABLE_CLUSTER_DEPLOYMENT` - Enable cluster features (default: True)

### Arguments

#### py4web Run Arguments
```bash
py4web run apps \
  --host 0.0.0.0 \
  --port 8000 \
  --watch off \
  --workers 4
```

#### Agent Arguments
```bash
iceshelves-agent \
  --server https://iceshelves.example.com \
  --cluster-id 1 \
  --agent-key YOUR_KEY \
  --poll-interval 300 \
  --debug
```

## Common Use Cases

### 1. Deploy an Egg
```bash
# Via Web UI
open http://localhost:8001/iceshelves/deploy

# Via API
curl -X POST http://localhost:8001/iceshelves/deploy \
  -d "egg_id=1" \
  -d "cluster_id=1" \
  -d "instance_name=my-instance"
```

### 2. Add an LXD Cluster
```bash
# Direct API method
curl -X POST http://localhost:8001/iceshelves/clusters/add \
  -d "name=my-cluster" \
  -d "connection_method=direct-api" \
  -d "endpoint_url=https://lxd-host:8443" \
  -d "client_cert=..." \
  -d "client_key=..."
```

### 3. Install Agent on Hypervisor
```bash
# On hypervisor
make iceshelves-agent \
  CLUSTER_ID=1 \
  AGENT_KEY=your-agent-key \
  ICESHELVES_SERVER=https://iceshelves.example.com
```

### 4. Create Custom Egg
```bash
# Create egg directory
mkdir -p apps/iceshelves/libraries/eggs/my-custom-egg

# Create cloud-init.yaml
cat > apps/iceshelves/libraries/eggs/my-custom-egg/cloud-init.yaml <<EOF
#cloud-config
hostname: my-custom
packages:
  - nginx
EOF

# Create metadata.json
cat > apps/iceshelves/libraries/eggs/my-custom-egg/metadata.json <<EOF
{
  "name": "my-custom-egg",
  "version": "1.0.0",
  "description": "My custom configuration",
  "category": "custom",
  "egg_type": "lxd-container"
}
EOF

# Add to database via web UI
```

## Monitoring

### Health Checks
```bash
# Application health
curl http://localhost:8001/iceshelves/healthz

# Database connectivity
curl http://localhost:8001/iceshelves/healthz | jq '.database'
```

### Metrics
```bash
# Prometheus metrics
curl http://localhost:8001/iceshelves/metrics

# Grafana dashboard
open http://localhost:3001
```

### Logs
```bash
# Docker logs
docker-compose logs -f iceshelves

# Application logs
make iceshelves-logs

# Agent logs
sudo journalctl -u iceshelves-agent -f
```

## Troubleshooting

See [docs/iceshelves/TROUBLESHOOTING.md](iceshelves/TROUBLESHOOTING.md) for common issues and solutions.
