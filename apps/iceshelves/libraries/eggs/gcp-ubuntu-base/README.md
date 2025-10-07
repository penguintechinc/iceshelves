# GCP Ubuntu Base Egg

Minimal Ubuntu 24.04 LTS configuration for Google Cloud Platform Compute Engine instances.

## Overview

This egg provides a clean, secure Ubuntu 24.04 LTS base for GCP Compute Engine deployments with Google Cloud SDK pre-installed, automatic security updates, and GCP metadata service integration.

## What's Included

- **Operating System**: Ubuntu 24.04 LTS (Noble Numbat)
- **Google Cloud SDK**: Pre-installed and auto-configured
- **Essential Tools**: vim, curl, wget, git, htop, python3-pip
- **GCP Integration**:
  - Automatic project/zone configuration
  - Metadata service environment variables
  - Service account support
- **Security**:
  - SSH key-based authentication only (password auth disabled)
  - Root login disabled
  - Automatic security updates enabled
- **User**: Default ubuntu user with sudo privileges

## GCP Requirements

### Machine Type
- **Minimum**: e2-micro (2 vCPU, 1GB RAM, burstable)
- **Recommended**: e2-small (2 vCPU, 2GB RAM)

### Image
This egg works with official Ubuntu 24.04 LTS images from `ubuntu-os-cloud`:
- Image Family: `ubuntu-2404-lts`
- Project: `ubuntu-os-cloud`

### Network
- Works with default VPC network
- Custom VPC networks supported
- External IP optional (can deploy in private subnet)

### IAM & Service Accounts
- Default compute service account used if not specified
- Custom service accounts supported
- Requires appropriate IAM permissions for metadata access

## Deployment Configuration

When deploying this egg to GCP, configure your deployment target with:

```json
{
  "provider_type": "gcp",
  "cloud_config": {
    "project_id": "my-gcp-project",
    "zone": "us-central1-a",
    "machine_type": "e2-micro",
    "image_project": "ubuntu-os-cloud",
    "image_family": "ubuntu-2404-lts",
    "network": "default",
    "service_account": "default"
  }
}
```

## Post-Deployment

### Accessing Your Instance

#### Using gcloud CLI

```bash
gcloud compute ssh ubuntu@<instance-name> --zone=<zone>
```

#### Using SSH directly

```bash
ssh -i ~/.ssh/google_compute_engine ubuntu@<instance-external-ip>
```

### Verify Deployment

Check the deployment log:

```bash
cat /var/log/iceshelves-deployment.log
```

View cloud-init status:

```bash
sudo cloud-init status
```

### GCP Environment Variables

The deployment automatically sets up environment variables:

```bash
echo $GCP_PROJECT_ID
echo $GCP_ZONE
echo $GCP_INSTANCE_NAME
```

### Google Cloud SDK

The gcloud CLI is pre-installed and configured:

```bash
gcloud config list
gcloud auth list
```

Authentication is automatic via service account or you can configure:

```bash
gcloud auth login
```

## Metadata Service

Access GCP metadata:

```bash
# Get project ID
curl -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/project/project-id

# Get instance name
curl -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/name

# Get zone
curl -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/zone
```

## Customization

### Cloud-Init Overrides

Override cloud-init configuration during deployment:

```json
{
  "hostname": "my-custom-hostname",
  "packages": ["nginx", "docker.io"],
  "timezone": "America/Los_Angeles"
}
```

### Add Custom Startup Scripts

Use the `runcmd` section for additional setup:

```yaml
runcmd:
  - apt-get install -y nodejs npm
  - npm install -g pm2
  - systemctl enable pm2
```

### Network Configuration

Configure firewall rules:

```bash
# Create firewall rule
gcloud compute firewall-rules create allow-http \
  --allow tcp:80 \
  --source-ranges 0.0.0.0/0 \
  --target-tags http-server
```

Tag your instance:

```bash
gcloud compute instances add-tags <instance-name> \
  --tags http-server \
  --zone <zone>
```

## Cost Considerations

- **e2-micro**: ~$0.0084/hour (~$6/month) - Free tier eligible
- **e2-small**: ~$0.0168/hour (~$12/month)

**Free Tier**: Google Cloud offers always-free e2-micro instances in US regions (1 per account).

Additional costs:
- Boot disk (10GB standard persistent disk ~$0.40/month)
- Network egress (first 1GB/month free)
- Static external IP (if not in use: ~$7/month)

## Security Best Practices

1. **Service Accounts**: Use least-privilege service accounts
2. **Firewall Rules**: Restrict ingress to known IP ranges
3. **OS Login**: Enable OS Login for centralized SSH key management
4. **VPC**: Use custom VPC with private subnets where possible
5. **Monitoring**: Enable Cloud Monitoring and Logging
6. **Backups**: Regular instance snapshots or custom images

### Enable OS Login

```bash
# Enable OS Login on project
gcloud compute project-info add-metadata \
  --metadata enable-oslogin=TRUE

# Enable on instance
gcloud compute instances add-metadata <instance-name> \
  --zone <zone> \
  --metadata enable-oslogin=TRUE
```

## Troubleshooting

### Cloud-Init Not Running

Check cloud-init status:

```bash
sudo cloud-init status
```

View startup script logs:

```bash
sudo journalctl -u google-startup-scripts.service
```

View cloud-init logs:

```bash
sudo cat /var/log/cloud-init.log
sudo cat /var/log/cloud-init-output.log
```

### Cannot SSH

1. Verify firewall allows SSH (default: port 22 allowed in default network)
2. Ensure instance has external IP (if accessing from internet)
3. Check IAM permissions for SSH access
4. View serial console output via GCP Console

### gcloud CLI Issues

Verify authentication:

```bash
gcloud auth list
gcloud config list
```

Re-authenticate if needed:

```bash
gcloud auth login
```

## Integration with GCP Services

### Cloud Storage

```bash
# List buckets
gsutil ls

# Copy files
gsutil cp file.txt gs://my-bucket/
```

### Cloud SQL

Connect to Cloud SQL instance:

```bash
gcloud sql connect my-instance --user=root
```

### Container Registry

```bash
# Configure Docker
gcloud auth configure-docker

# Push image
docker push gcr.io/my-project/my-image:tag
```

## Support

For issues with this egg, check:
- [IceShelves Troubleshooting Guide](../../docs/iceshelves/TROUBLESHOOTING.md)
- [GCP Compute Engine Documentation](https://cloud.google.com/compute/docs)
- [Ubuntu Cloud Images](https://cloud-images.ubuntu.com/)

## Version History

- **1.0.0**: Initial release with Ubuntu 24.04 LTS support
