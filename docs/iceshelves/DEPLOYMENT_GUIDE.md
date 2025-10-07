# IceShelves Deployment Guide

Complete guide for deploying eggs to LXD clusters and KVM hypervisors.

## Table of Contents
- [Deployment Methods](#deployment-methods)
- [Web UI Deployment](#web-ui-deployment)
- [API Deployment](#api-deployment)
- [Advanced Deployment](#advanced-deployment)
- [Best Practices](#best-practices)

## Deployment Methods

IceShelves supports three deployment workflows:

1. **Web UI** - Interactive point-and-click deployment
2. **REST API** - Automation and CI/CD integration
3. **CLI** - Command-line deployment (via API)

## Web UI Deployment

### Step 1: Navigate to Deploy Page

```
http://localhost:8001/iceshelves/deploy
```

### Step 2: Select an Egg

Browse available eggs or use search:
- Filter by category (base, webserver, database, etc.)
- Search by name or description
- View egg details before deploying

### Step 3: Choose Target Cluster

Select destination cluster:
- View cluster status (active/inactive)
- Check connection method
- View available resources (if cluster supports)

### Step 4: Configure Deployment

**Required Fields:**
- **Instance Name** - Unique name for the instance (e.g., `web-server-01`)

**Optional Fields:**
- **Target Member** - Specific cluster node (for clusters only)
- **Config Overrides** - Custom cloud-init values

**Example Config Override:**
```json
{
  "hostname": "custom-hostname",
  "packages": ["nginx", "vim", "curl"]
}
```

### Step 5: Deploy

Click **Deploy** button:
- Deployment is queued immediately
- Redirected to deployment details page
- Real-time logs displayed

### Step 6: Monitor Progress

Deployment details page shows:
- Current status
- Start/completion time
- Instance information
- Detailed logs

**Status Values:**
- `pending` - Waiting to start
- `in_progress` - Currently deploying
- `completed` - Successfully deployed
- `failed` - Deployment failed (check logs)

## API Deployment

### Basic Deployment

```bash
curl -X POST http://localhost:8001/iceshelves/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "egg_id": 1,
    "cluster_id": 2,
    "instance_name": "my-instance-01"
  }'
```

**Response:**
```json
{
  "success": true,
  "deployment_id": 42,
  "instance_name": "my-instance-01",
  "status": "pending",
  "message": "Deployment initiated"
}
```

### Deployment with Overrides

```bash
curl -X POST http://localhost:8001/iceshelves/api/deploy \
  -H "Content-Type": application/json" \
  -d '{
    "egg_id": 1,
    "cluster_id": 2,
    "instance_name": "custom-web-01",
    "config_overrides": {
      "hostname": "custom-web-01",
      "packages": ["nginx", "certbot", "python3-certbot-nginx"],
      "timezone": "America/New_York"
    }
  }'
```

### Cluster-Specific Deployment

Deploy to specific cluster member:

```bash
curl -X POST http://localhost:8001/iceshelves/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "egg_id": 1,
    "cluster_id": 2,
    "instance_name": "node2-instance",
    "target_member": "node-2"
  }'
```

### Monitor Deployment Status

```bash
# Get deployment details
curl http://localhost:8001/iceshelves/api/deployments/42

# Get deployment logs
curl http://localhost:8001/iceshelves/api/deployments/42/logs
```

## Advanced Deployment

### Batch Deployment

Deploy multiple instances:

```bash
#!/bin/bash

EGG_ID=1
CLUSTER_ID=2

for i in {1..5}; do
  curl -X POST http://localhost:8001/iceshelves/api/deploy \
    -H "Content-Type: application/json" \
    -d "{
      \"egg_id\": $EGG_ID,
      \"cluster_id\": $CLUSTER_ID,
      \"instance_name\": \"batch-instance-$(printf %02d $i)\"
    }"

  echo "Deployed instance $i"
  sleep 2
done
```

### Deployment with Validation

Pre-validate before deploying:

```bash
#!/bin/bash

# Check egg exists
EGG_EXISTS=$(curl -s http://localhost:8001/iceshelves/api/eggs/1 | jq '.id')

if [ "$EGG_EXISTS" = "null" ]; then
  echo "Error: Egg not found"
  exit 1
fi

# Check cluster is healthy
CLUSTER_STATUS=$(curl -s http://localhost:8001/iceshelves/api/clusters/2 | jq -r '.status')

if [ "$CLUSTER_STATUS" != "active" ]; then
  echo "Error: Cluster not active"
  exit 1
fi

# Deploy
curl -X POST http://localhost:8001/iceshelves/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "egg_id": 1,
    "cluster_id": 2,
    "instance_name": "validated-instance"
  }'
```

### CI/CD Integration

**GitHub Actions Example:**

```yaml
name: Deploy to LXD

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to IceShelves
        run: |
          curl -X POST ${{ secrets.ICESHELVES_URL }}/api/deploy \
            -H "Content-Type: application/json" \
            -d '{
              "egg_id": 1,
              "cluster_id": 2,
              "instance_name": "app-${{ github.sha }}"
            }'
```

**GitLab CI Example:**

```yaml
deploy:
  stage: deploy
  script:
    - |
      curl -X POST ${ICESHELVES_URL}/api/deploy \
        -H "Content-Type: application/json" \
        -d "{
          \"egg_id\": 1,
          \"cluster_id\": 2,
          \"instance_name\": \"app-${CI_COMMIT_SHORT_SHA}\"
        }"
  only:
    - main
```

### Python Deployment Script

```python
#!/usr/bin/env python3
import requests
import time
import sys

class IceShelvesDeployer:
    def __init__(self, base_url):
        self.base_url = base_url

    def deploy(self, egg_id, cluster_id, instance_name, wait=True):
        """Deploy an egg and optionally wait for completion."""

        # Initiate deployment
        response = requests.post(
            f'{self.base_url}/api/deploy',
            json={
                'egg_id': egg_id,
                'cluster_id': cluster_id,
                'instance_name': instance_name
            }
        )

        if response.status_code != 200:
            print(f"Deployment failed: {response.text}")
            return False

        deployment_id = response.json()['deployment_id']
        print(f"Deployment initiated: {deployment_id}")

        if not wait:
            return deployment_id

        # Wait for completion
        while True:
            status = self.get_deployment_status(deployment_id)

            print(f"Status: {status['status']}")

            if status['status'] == 'completed':
                print("Deployment completed successfully!")
                return deployment_id
            elif status['status'] == 'failed':
                print(f"Deployment failed: {status.get('error_message')}")
                return False

            time.sleep(5)

    def get_deployment_status(self, deployment_id):
        """Get deployment status."""
        response = requests.get(
            f'{self.base_url}/api/deployments/{deployment_id}'
        )
        return response.json()

# Usage
deployer = IceShelvesDeployer('http://localhost:8001/iceshelves')
deployer.deploy(
    egg_id=1,
    cluster_id=2,
    instance_name='python-deployed-instance',
    wait=True
)
```

## Best Practices

### Naming Conventions

**Good Instance Names:**
- `web-prod-01`, `web-prod-02` - Environment and sequence
- `db-mysql-primary` - Purpose and role
- `app-api-20251007-01` - Date-based versioning

**Avoid:**
- `test`, `temp`, `asdf` - Too generic
- Special characters except `-`
- Spaces in names

### Resource Planning

**Before deploying, consider:**
- CPU cores required (check egg metadata)
- Memory requirements (minimum in egg spec)
- Disk space needs
- Network bandwidth

**Cluster Selection:**
- Deploy to cluster with available resources
- Use target_member for specific node placement
- Balance load across cluster members

### Configuration Management

**Use Config Overrides for:**
- Hostname customization
- Package additions
- Timezone/locale settings
- User-specific SSH keys

**Don't Override:**
- Core system configuration
- Security-critical settings
- LXD profile settings (use egg customization instead)

### Monitoring Deployments

**Always:**
- Monitor deployment logs in real-time
- Check instance status after deployment
- Verify cloud-init completed successfully
- Test connectivity to deployed instance

**Verification Commands:**
```bash
# Check deployment status
curl http://localhost:8001/iceshelves/api/deployments/{id}

# SSH into instance (if configured)
ssh ubuntu@<instance-ip>

# Check cloud-init status
sudo cloud-init status
```

### Rollback Strategy

If deployment fails:

1. **Check Logs** - Review deployment logs for errors
2. **Fix Issue** - Correct configuration or egg
3. **Retry** - Deploy again with fixes
4. **Cleanup** - Delete failed instance if needed

**Delete Failed Instance:**
```bash
# Via LXD directly
lxc delete failed-instance --force

# Via API (future feature)
curl -X DELETE http://localhost:8001/iceshelves/api/deployments/{id}/cleanup
```

### Production Deployment Checklist

- [ ] Egg tested in development
- [ ] Target cluster has sufficient resources
- [ ] Instance naming follows convention
- [ ] Config overrides validated
- [ ] Monitoring configured
- [ ] Backup plan in place
- [ ] Rollback procedure documented
- [ ] Team notified of deployment

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common deployment issues and solutions.
