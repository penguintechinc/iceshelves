# IceShelves Documentation

## Overview
IceShelves is a comprehensive LXD/KVM egg deployment platform built with py4web. It allows you to manage and deploy "eggs" (cloud-init deployment packages) to LXD clusters and KVM virtual machines.

## Key Features
- **Egg Management**: Create, manage, and deploy pre-configured system images
- **Multiple Connection Methods**: Direct API, SSH tunnel, or polling agent
- **LXD Cluster Support**: Deploy to single hosts or LXD clusters
- **KVM Support**: Deploy to KVM/libvirt hypervisors
- **Cloud-init Integration**: Full cloud-init configuration support
- **Web Interface**: Modern, responsive web UI
- **REST API**: Complete API for automation
- **Template System**: Create new eggs from templates

## Documentation Index

- [Architecture](ARCHITECTURE.md) - System design and components
- [API Documentation](API.md) - REST API reference
- [Deployment Guide](DEPLOYMENT_GUIDE.md) - How to deploy eggs
- [Egg Specification](EGG_SPECIFICATION.md) - Egg format and structure
- [Cloud-init Examples](CLOUD_INIT_EXAMPLES.md) - Cloud-init configuration examples
- [Agent Installation](AGENT_INSTALLATION.md) - Installing the polling agent
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions

## Quick Start

### 1. Access IceShelves
Navigate to `http://your-server:8000/iceshelves`

### 2. Add a Cluster
1. Go to **Clusters** → **Add Cluster**
2. Choose connection method:
   - **Direct API**: For direct LXD API access
   - **SSH**: For SSH tunnel connections
   - **Agent Poll**: For agent-based deployments
3. Fill in connection details
4. Test connection

### 3. Browse Eggs
Visit **Eggs** to see available deployment packages:
- ubuntu-base - Minimal Ubuntu 24.04 LTS
- ubuntu-docker - Ubuntu with Docker pre-installed
- ubuntu-nginx - Ubuntu with Nginx web server
- ubuntu-k8s-node - Kubernetes worker node

### 4. Deploy an Egg
1. Click **Deploy** or select an egg and click **Deploy**
2. Choose target cluster
3. Specify instance name
4. Click **Deploy**
5. Monitor deployment progress

## Connection Methods

### Direct API (Clientless)
- Connects directly to LXD API endpoint
- Requires network connectivity to LXD host
- Immediate deployment
- Best for: Direct network access environments

### SSH (Clientless)
- Creates SSH tunnel to LXD unix socket
- Works through firewalls
- Requires SSH access to hypervisor
- Best for: Restricted network environments

### Agent Poll (Client-based)
- Lightweight agent installed on hypervisor
- Agent polls for deployments every 1-5 minutes
- Works in air-gapped environments
- Best for: Isolated networks, strict firewall policies

## Support
- **Documentation**: [./docs/iceshelves](.)
- **Issues**: GitHub Issues
- **Support**: support@penguintech.group
