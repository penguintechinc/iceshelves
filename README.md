[![CI](https://github.com/PenguinCloud/project-template/actions/workflows/ci.yml/badge.svg)](https://github.com/PenguinCloud/project-template/actions/workflows/ci.yml)
[![Docker Build](https://github.com/PenguinCloud/project-template/actions/workflows/docker-build.yml/badge.svg)](https://github.com/PenguinCloud/project-template/actions/workflows/docker-build.yml)
[![codecov](https://codecov.io/gh/PenguinCloud/project-template/branch/main/graph/badge.svg)](https://codecov.io/gh/PenguinCloud/project-template)
[![Go Report Card](https://goreportcard.com/badge/github.com/PenguinCloud/project-template)](https://goreportcard.com/report/github.com/PenguinCloud/project-template)
[![version](https://img.shields.io/badge/version-5.1.1-blue.svg)](https://semver.org)
[![License](https://img.shields.io/badge/License-Limited%20AGPL3-blue.svg)](LICENSE.md)

```
 ____            _           _     _____                    _       _
|  _ \ _ __ ___ (_) ___  ___| |_  |_   _|__ _ __ ___  _ __ | | __ _| |_ ___
| |_) | '__/ _ \| |/ _ \/ __| __|   | |/ _ \ '_ ` _ \| '_ \| |/ _` | __/ _ \
|  __/| | | (_) | |  __/ (__| |_    | |  __/ | | | | | |_) | | (_| | ||  __/
|_|   |_|  \___/| |\___|\___|\__|   |_|\___|_| |_| |_| .__/|_|\__,_|\__\___|
               _/ |                                  |_|
              |__/
```

# 🐧 IceShelves - LXD/KVM Egg Deployment Platform

```
  ___          ____  _          _
 |_ _|___ ___ / ___|| |__   ___| |_   _____  ___
  | |/ __/ _ \ \___ \| '_ \ / _ \ \ \ / / _ \/ __|
  | | (_|  __/  ___) | | | |  __/ |\ V /  __/\__ \
 |___\___\___| |____/|_| |_|\___|_| \_/ \___||___/

     LXD/KVM Deployment Made Simple
```

**Deploy cloud-init packages ("eggs") to LXD clusters and KVM hypervisors with ease**

IceShelves is a comprehensive py4web-based platform for managing and deploying standardized system configurations to LXD containers and KVM virtual machines. Built with security, flexibility, and automation at its core, it provides multiple connection methods and a modern web interface for infrastructure deployment.
## ✨ Key Features

### 🥚 Egg Management
- **Pre-built Eggs**: Ubuntu base, Docker, Nginx, Kubernetes nodes
- **Custom Eggs**: Create your own deployment packages
- **Template System**: Generate new eggs from templates
- **Cloud-init Integration**: Full cloud-init YAML support
- **Version Control**: Semantic versioning for eggs

### 🔌 Flexible Connection Methods
- **Direct API**: Clientless connection to LXD API (immediate deployment)
- **SSH Tunnel**: Clientless SSH-based connection (firewall-friendly)
- **Polling Agent**: Client-based polling for air-gapped environments

### 🏢 LXD Cluster Support
- **Multi-host Clusters**: Deploy to LXD cluster members
- **Single Hosts**: Support for standalone LXD hosts
- **Target Selection**: Choose specific cluster nodes for deployment
- **Health Monitoring**: Track cluster status and connectivity

### 🖥️ KVM/Libvirt Support
- **Virtual Machines**: Deploy KVM VMs for non-Linux workloads
- **Blackbox Applications**: Run Windows or proprietary systems
- **Full Isolation**: Complete kernel isolation when needed

### 📊 Modern Web Interface
- **Dashboard**: Real-time deployment statistics
- **Egg Library**: Browse and search available eggs
- **Deployment Wizard**: Step-by-step deployment interface
- **Live Logs**: Real-time deployment progress monitoring

### 🔐 Enterprise Ready
- **PenguinTech License Integration**: Feature gating and licensing
- **Multi-tenant Support**: Isolated deployments
- **Audit Logging**: Complete deployment history
- **Prometheus Metrics**: Built-in observability

## 🚀 Quick Start

### Using Docker Compose (Recommended)
```bash
# Clone repository
git clone https://github.com/PenguinCloud/iceshelves.git
cd iceshelves

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start services
docker-compose up -d iceshelves

# Access IceShelves
open http://localhost:8001/iceshelves
```

### Manual Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Configure database
export ICESHELVES_DATABASE_URL="postgresql://user:pass@localhost/iceshelves"

# Run py4web
py4web run apps --host 0.0.0.0 --port 8000

# Access IceShelves
open http://localhost:8000/iceshelves
```

## 📚 Core Components

### Technology Stack
- **Framework**: py4web (Python 3.12)
- **Database**: PostgreSQL with PyDAL ORM
- **Cache**: Redis/Valkey
- **LXD Integration**: pylxd library
- **KVM Integration**: libvirt-python
- **Cloud-init**: PyYAML for configuration management

### Connection Architectures

#### 1. Direct API (Clientless)
```
IceShelves → LXD API (HTTPS) → LXD Host
```
- Immediate deployment
- Requires network connectivity
- Best for: Data centers, cloud environments

#### 2. SSH Tunnel (Clientless)
```
IceShelves → SSH Tunnel → LXD Unix Socket
```
- Works through firewalls
- SSH key authentication
- Best for: Restricted networks

#### 3. Polling Agent (Client-based)
```
IceShelves ← Agent (polls every 1-5 min) ← LXD Host
```
- Air-gapped support
- Service account authentication
- Best for: Isolated environments, DMZs

## 📖 Documentation

- **IceShelves Guide**: [docs/iceshelves/README.md](docs/iceshelves/README.md)
- **Egg Specification**: [docs/iceshelves/EGG_SPECIFICATION.md](docs/iceshelves/EGG_SPECIFICATION.md)
- **API Reference**: [docs/iceshelves/API.md](docs/iceshelves/API.md)
- **Agent Installation**: [docs/iceshelves/AGENT_INSTALLATION.md](docs/iceshelves/AGENT_INSTALLATION.md)
- **Cloud-init Examples**: [docs/iceshelves/CLOUD_INIT_EXAMPLES.md](docs/iceshelves/CLOUD_INIT_EXAMPLES.md)

### Pre-built Eggs
- **ubuntu-base**: Minimal Ubuntu 24.04 LTS
- **ubuntu-docker**: Docker Engine pre-installed
- **ubuntu-nginx**: Nginx web server with Certbot
- **ubuntu-k8s-node**: Kubernetes worker node ready to join cluster

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Maintainers
- **Primary**: creatorsemailhere@penguintech.group
- **General**: info@penguintech.group
- **Company**: [www.penguintech.io](https://www.penguintech.io)

### Community Contributors
- *Your name could be here! Submit a PR to get started.*

## 📞 Support & Resources

- **Documentation**: [./docs/](docs/)
- **Premium Support**: https://support.penguintech.group
- **Community Issues**: [GitHub Issues](../../issues)
- **License Server Status**: https://status.penguintech.io

## 📄 License

This project is licensed under the Limited AGPL3 with preamble for fair use - see [LICENSE.md](docs/LICENSE.md) for details.

**License Highlights:**
- **Personal & Internal Use**: Free under AGPL-3.0
- **Commercial Use**: Requires commercial license
- **SaaS Deployment**: Requires commercial license if providing as a service

### Contributor Employer Exception (GPL-2.0 Grant)

Companies employing official contributors receive GPL-2.0 access to community features:

- **Perpetual for Contributed Versions**: GPL-2.0 rights to versions where the employee contributed remain valid permanently, even after the employee leaves the company
- **Attribution Required**: Employee must be credited in CONTRIBUTORS, AUTHORS, commit history, or release notes
- **Future Versions**: New versions released after employment ends require standard licensing
- **Community Only**: Enterprise features still require a commercial license

This exception rewards contributors by providing lasting fair use rights to their employers.
