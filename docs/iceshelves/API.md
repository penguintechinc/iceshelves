# IceShelves API Documentation

## Overview

IceShelves provides a RESTful API for automation and integration. All API endpoints return JSON responses and support standard HTTP methods.

**Base URL:** `http://your-server:8001/iceshelves`

## Authentication

### Web UI
Session-based authentication with CSRF protection.

### Agent API
Bearer token authentication using agent key:
```http
Authorization: Bearer {agent_key}
```

## Response Format

### Success Response
```json
{
  "success": true,
  "data": { ... }
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error message",
  "code": 400
}
```

## Core Endpoints

### Health & Status

#### GET /healthz
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-07T12:00:00Z",
  "version": "1.0.0",
  "app": "iceshelves",
  "database": "connected",
  "dependencies": {
    "pylxd": true,
    "libvirt": true
  }
}
```

#### GET /metrics
Prometheus metrics endpoint (plain text format).

## Egg Management

### GET /api/eggs
List all eggs.

**Query Parameters:**
- `category` (optional) - Filter by category
- `search` (optional) - Search in name/description
- `page` (optional) - Page number (default: 1)
- `per_page` (optional) - Items per page (default: 20)

**Response:**
```json
{
  "eggs": [
    {
      "id": 1,
      "name": "ubuntu-base",
      "display_name": "Ubuntu Base",
      "description": "Minimal Ubuntu 24.04 LTS",
      "version": "1.0.0",
      "category": "base",
      "egg_type": "lxd-container",
      "is_active": true,
      "created_on": "2025-10-07T12:00:00Z"
    }
  ],
  "total": 10,
  "page": 1,
  "total_pages": 1
}
```

### GET /api/eggs/{egg_id}
Get egg details.

**Response:**
```json
{
  "id": 1,
  "name": "ubuntu-base",
  "display_name": "Ubuntu Base",
  "description": "Minimal Ubuntu 24.04 LTS",
  "version": "1.0.0",
  "category": "base",
  "egg_type": "lxd-container",
  "base_image": "ubuntu/24.04",
  "cloud_init_path": "cloud-init.yaml",
  "metadata_json": {},
  "tags": ["ubuntu", "base", "lts"],
  "files": {
    "cloud_init": "#cloud-config\n...",
    "readme": "# Ubuntu Base\n..."
  }
}
```

### POST /api/eggs
Create new egg.

**Request Body:**
```json
{
  "name": "my-egg",
  "display_name": "My Custom Egg",
  "description": "Custom configuration",
  "category": "custom",
  "egg_type": "lxd-container",
  "template_id": 1,
  "variables": {
    "hostname": "my-host",
    "packages": ["vim", "curl"]
  }
}
```

**Response:**
```json
{
  "success": true,
  "egg_id": 10,
  "message": "Egg created successfully"
}
```

## Cluster Management

### GET /api/clusters
List all clusters.

**Response:**
```json
{
  "clusters": [
    {
      "id": 1,
      "name": "production-lxd",
      "description": "Production LXD cluster",
      "connection_method": "direct-api",
      "endpoint_url": "https://lxd-prod:8443",
      "status": "active",
      "is_active": true,
      "last_check": "2025-10-07T12:00:00Z"
    }
  ]
}
```

### GET /api/clusters/{cluster_id}
Get cluster details.

**Response:**
```json
{
  "id": 1,
  "name": "production-lxd",
  "connection_method": "direct-api",
  "endpoint_url": "https://lxd-prod:8443",
  "auth_type": "certificate",
  "is_cluster": true,
  "status": "active",
  "metadata": {
    "members": ["node-1", "node-2", "node-3"],
    "resources": {
      "cpu_cores": 96,
      "memory_gb": 512
    }
  },
  "health": {
    "status": "active",
    "message": "Connected successfully to LXD 5.21",
    "checked_at": "2025-10-07T12:00:00Z"
  }
}
```

### POST /api/clusters
Add new cluster.

**Request Body (Direct API):**
```json
{
  "name": "my-cluster",
  "description": "My LXD cluster",
  "connection_method": "direct-api",
  "endpoint_url": "https://lxd-host:8443",
  "auth_type": "certificate",
  "client_cert": "-----BEGIN CERTIFICATE-----\n...",
  "client_key": "-----BEGIN PRIVATE KEY-----\n...",
  "verify_ssl": true,
  "is_cluster": true
}
```

**Request Body (SSH):**
```json
{
  "name": "my-cluster",
  "connection_method": "ssh",
  "ssh_host": "lxd-host.example.com",
  "ssh_port": 22,
  "ssh_user": "ubuntu",
  "ssh_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n..."
}
```

**Request Body (Agent Poll):**
```json
{
  "name": "my-cluster",
  "connection_method": "agent-poll",
  "agent_poll_interval": 300
}
```

**Response:**
```json
{
  "success": true,
  "cluster_id": 5,
  "agent_key": "generated-agent-key-12345",
  "message": "Cluster added successfully"
}
```

### POST /api/clusters/{cluster_id}/test
Test cluster connection.

**Response:**
```json
{
  "status": "active",
  "details": {
    "message": "Connected successfully to LXD 5.21",
    "server_version": "5.21",
    "api_version": "1.0"
  }
}
```

### DELETE /api/clusters/{cluster_id}
Delete cluster (if no active deployments).

## Deployment

### POST /api/deploy
Deploy an egg.

**Request Body:**
```json
{
  "egg_id": 1,
  "cluster_id": 2,
  "instance_name": "my-instance-01",
  "target_member": "node-2",
  "config_overrides": {
    "hostname": "custom-hostname"
  }
}
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

### GET /api/deployments
List deployments.

**Query Parameters:**
- `status` (optional) - Filter by status
- `cluster_id` (optional) - Filter by cluster
- `egg_id` (optional) - Filter by egg
- `page` (optional) - Page number

**Response:**
```json
{
  "deployments": [
    {
      "id": 42,
      "egg_id": 1,
      "cluster_id": 2,
      "instance_name": "my-instance-01",
      "status": "completed",
      "deployment_type": "lxd",
      "started_at": "2025-10-07T12:00:00Z",
      "completed_at": "2025-10-07T12:02:30Z",
      "deployed_by": "admin"
    }
  ],
  "total": 100,
  "page": 1
}
```

### GET /api/deployments/{deployment_id}
Get deployment details.

**Response:**
```json
{
  "id": 42,
  "egg": {
    "id": 1,
    "name": "ubuntu-base"
  },
  "cluster": {
    "id": 2,
    "name": "production-lxd"
  },
  "instance_name": "my-instance-01",
  "status": "completed",
  "deployment_type": "lxd",
  "started_at": "2025-10-07T12:00:00Z",
  "completed_at": "2025-10-07T12:02:30Z",
  "instance_info": {
    "name": "my-instance-01",
    "status": "Running",
    "architecture": "x86_64",
    "ipv4": ["10.0.0.5"]
  },
  "logs": [
    {
      "timestamp": "2025-10-07T12:00:00Z",
      "level": "INFO",
      "message": "Deployment initiated"
    },
    {
      "timestamp": "2025-10-07T12:02:30Z",
      "level": "INFO",
      "message": "Deployment completed successfully"
    }
  ]
}
```

### GET /api/deployments/{deployment_id}/logs
Get deployment logs.

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2025-10-07T12:00:00Z",
      "level": "INFO",
      "message": "Deployment initiated for instance my-instance-01"
    },
    {
      "timestamp": "2025-10-07T12:00:15Z",
      "level": "INFO",
      "message": "Connected to cluster production-lxd"
    },
    {
      "timestamp": "2025-10-07T12:01:00Z",
      "level": "INFO",
      "message": "Creating instance my-instance-01"
    },
    {
      "timestamp": "2025-10-07T12:02:30Z",
      "level": "INFO",
      "message": "Instance started successfully"
    }
  ]
}
```

## Agent API

### POST /api/agent/poll/{cluster_id}
Agent polling endpoint (requires agent authentication).

**Headers:**
```
X-Agent-Key: {agent_key}
```

**Response:**
```json
{
  "deployments": [
    {
      "deployment_id": 42,
      "egg_name": "ubuntu-base",
      "instance_name": "my-instance-01",
      "deployment_type": "lxd",
      "cloud_init": "#cloud-config\n...",
      "lxd_profile": "...",
      "config_overrides": {},
      "target_member": null
    }
  ]
}
```

### POST /api/agent/status/{deployment_id}
Update deployment status (requires agent authentication).

**Headers:**
```
X-Agent-Key: {agent_key}
```

**Request Body:**
```json
{
  "status": "completed",
  "message": "Instance deployed successfully",
  "instance_info": {
    "name": "my-instance-01",
    "status": "Running",
    "architecture": "x86_64",
    "ipv4": ["10.0.0.5"]
  },
  "details": {
    "agent_hostname": "lxd-host-01",
    "timestamp": "2025-10-07T12:02:30Z"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Status updated"
}
```

## Templates

### GET /api/templates
List egg templates.

**Response:**
```json
{
  "templates": [
    {
      "id": 1,
      "name": "basic-ubuntu",
      "display_name": "Basic Ubuntu Template",
      "description": "Basic Ubuntu with customizable packages",
      "category": "base",
      "template_type": "lxd-container",
      "required_variables": ["hostname", "packages"]
    }
  ]
}
```

## Status Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error
- `503` - Service Unavailable

## Rate Limiting

Currently no rate limiting implemented. Enterprise version will include:
- Per-user rate limits
- Per-cluster deployment limits
- API key quotas

## Pagination

List endpoints support pagination:

**Query Parameters:**
- `page` - Page number (default: 1)
- `per_page` - Items per page (default: 20, max: 100)

**Response:**
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

## Webhooks (Coming Soon)

Subscribe to deployment events:
- `deployment.started`
- `deployment.completed`
- `deployment.failed`
- `cluster.status_changed`

## SDK Examples

### Python
```python
import requests

class IceShelvesClient:
    def __init__(self, base_url, api_key=None):
        self.base_url = base_url
        self.session = requests.Session()
        if api_key:
            self.session.headers['Authorization'] = f'Bearer {api_key}'

    def deploy(self, egg_id, cluster_id, instance_name):
        response = self.session.post(
            f'{self.base_url}/api/deploy',
            json={
                'egg_id': egg_id,
                'cluster_id': cluster_id,
                'instance_name': instance_name
            }
        )
        return response.json()

# Usage
client = IceShelvesClient('http://localhost:8001/iceshelves')
result = client.deploy(egg_id=1, cluster_id=2, instance_name='my-instance')
print(result)
```

### cURL
```bash
# Deploy an egg
curl -X POST http://localhost:8001/iceshelves/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "egg_id": 1,
    "cluster_id": 2,
    "instance_name": "my-instance"
  }'

# List deployments
curl http://localhost:8001/iceshelves/api/deployments?status=completed

# Get deployment status
curl http://localhost:8001/iceshelves/api/deployments/42
```
