# Ubuntu with Docker

## Description
Ubuntu 24.04 LTS with Docker Engine and Docker Compose pre-installed and configured for production use.

## What's Included
- Ubuntu 24.04 LTS (Noble Numbat)
- Docker Engine (latest stable)
- Docker Compose Plugin
- Docker Buildx Plugin
- Optimized Docker daemon configuration
- Essential development tools

## Default Configuration
- **User**: ubuntu (with sudo and docker group access)
- **SSH**: Key-based authentication only
- **Docker**: Configured with json-file logging and overlay2 storage driver
- **Timezone**: UTC
- **Locale**: en_US.UTF-8

## Docker Configuration
The Docker daemon is configured with:
- **Log Driver**: json-file with rotation (10MB max size, 3 files)
- **Storage Driver**: overlay2
- **Live Restore**: Enabled (containers keep running during Docker daemon downtime)

## Usage

### Quick Deploy
1. Deploy using IceShelves web interface or API
2. SSH into the instance after deployment
3. Start deploying containers immediately

### Example Docker Commands
```bash
# Test Docker installation
docker run hello-world

# Run nginx container
docker run -d -p 80:80 nginx:latest

# Use Docker Compose
docker compose up -d
```

## Post-Deployment
After deployment:
1. SSH into the instance
2. Verify Docker: `docker --version`
3. Check Docker service: `systemctl status docker`
4. List running containers: `docker ps`
5. Deploy your containerized applications

## Use Cases
- Docker development environment
- Containerized application hosting
- CI/CD build agents
- Microservices deployment
- Container orchestration nodes

## System Requirements
- **Minimum Memory**: 2GB RAM
- **Minimum Disk**: 20GB
- **Minimum Cores**: 2

## Version
- Egg Version: 1.0.0
- Base Image: ubuntu/24.04
- Docker: Latest stable from Docker official repository
- Last Updated: 2025-10-07

## Security Notes
- Docker daemon runs as root (standard Docker behavior)
- User 'ubuntu' is in docker group (equivalent to root access)
- Consider implementing Docker security best practices for production
- Review and update Docker daemon configuration as needed
