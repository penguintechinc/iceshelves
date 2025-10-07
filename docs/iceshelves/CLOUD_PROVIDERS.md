# IceShelves Cloud Provider Integration

Complete guide for deploying eggs to AWS EC2 and Google Cloud Platform (GCP) Compute Engine.

## Table of Contents
- [Overview](#overview)
- [AWS EC2 Deployment](#aws-ec2-deployment)
- [GCP Compute Engine Deployment](#gcp-compute-engine-deployment)
- [Deployment Comparison](#deployment-comparison)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

IceShelves supports deploying eggs (OS-level packages) to multiple cloud providers in addition to LXD containers and KVM virtual machines. All deployments use cloud-init for consistent configuration across platforms.

**Supported Cloud Providers:**
- **Amazon Web Services (AWS) EC2** - Virtual machines on AWS
- **Google Cloud Platform (GCP) Compute Engine** - Virtual machines on GCP
- **LXD** - Local or remote container hosts
- **KVM** - Local or remote virtual machines

**Key Features:**
- Unified cloud-init configuration across all platforms
- Secrets management integration (AWS Secrets Manager, GCP Secret Manager, Infisical)
- Clientless deployment via cloud provider APIs
- Same egg can deploy to multiple platforms (multi-cloud)

## AWS EC2 Deployment

### Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS Credentials** (one of):
   - IAM role attached to IceShelves server (recommended)
   - Access key ID and secret access key
   - Stored in secrets manager

3. **VPC and Networking**:
   - VPC with subnets
   - Security groups configured
   - Internet gateway (for public instances)

4. **EC2 Key Pair** for SSH access

### Adding AWS as Deployment Target

#### Via Web UI

1. Navigate to **Clusters** → **Add Cluster**
2. Fill in the form:
   - **Name**: `aws-us-east-1` (or your preferred name)
   - **Description**: AWS EC2 deployment target
   - **Provider Type**: `aws`
   - **Secrets Manager**: Choose secrets manager type
   - **Cloud Configuration**: Click to expand and configure

3. **Cloud Configuration JSON**:

```json
{
  "region": "us-east-1",
  "ami": "ami-0e2c8caa4b6378d8c",
  "instance_type": "t3.micro",
  "security_groups": ["sg-0123456789abcdef0"],
  "subnet_id": "subnet-0123456789abcdef0",
  "key_name": "my-ec2-keypair",
  "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
}
```

**Important**: Store credentials in secrets manager instead of cloud_config for production.

#### Via API

```bash
curl -X POST http://localhost:8001/iceshelves/api/targets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "aws-us-east-1",
    "description": "AWS EC2 us-east-1 region",
    "provider_type": "aws",
    "secrets_manager_type": "aws",
    "secrets_config": {
      "region": "us-east-1",
      "secret_prefix": "iceshelves/aws-creds/"
    },
    "cloud_config": {
      "region": "us-east-1",
      "ami": "ami-0e2c8caa4b6378d8c",
      "instance_type": "t3.micro",
      "security_groups": ["sg-xxxxxxxxx"],
      "subnet_id": "subnet-xxxxxxxxx",
      "key_name": "my-keypair"
    }
  }'
```

### Deploying to AWS

#### Via Web UI

1. Navigate to **Deploy**
2. Select an AWS-compatible egg (e.g., `aws-ubuntu-base`)
3. Choose AWS deployment target
4. Enter instance name
5. Click **Deploy**

#### Via API

```bash
curl -X POST http://localhost:8001/iceshelves/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "egg_id": 5,
    "target_id": 2,
    "instance_name": "my-aws-instance-01"
  }'
```

### AWS-Specific Configuration

#### AMI Selection

Choose appropriate Ubuntu 24.04 AMI for your region:

| Region | AMI ID (Ubuntu 24.04 LTS) |
|--------|---------------------------|
| us-east-1 | ami-0e2c8caa4b6378d8c |
| us-west-2 | ami-0aff18ec83b712f05 |
| eu-west-1 | ami-0d71ea30463e0ff8d |

Or use AWS CLI to find latest:

```bash
aws ec2 describe-images \
  --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-noble-24.04-amd64-server-*" \
  --query 'Images[*].[ImageId,CreationDate,Name]' \
  --output table \
  --region us-east-1
```

#### Instance Types

**Cost-Optimized:**
- `t3.micro` - $0.0104/hr (~$7.50/mo) - 1 vCPU, 1 GB RAM
- `t3.small` - $0.0208/hr (~$15/mo) - 2 vCPU, 2 GB RAM
- `t3.medium` - $0.0416/hr (~$30/mo) - 2 vCPU, 4 GB RAM

**Compute-Optimized:**
- `c6i.large` - 2 vCPU, 4 GB RAM
- `c6i.xlarge` - 4 vCPU, 8 GB RAM

**Memory-Optimized:**
- `r6i.large` - 2 vCPU, 16 GB RAM
- `r6i.xlarge` - 4 vCPU, 32 GB RAM

#### Security Groups

Create security group for your instances:

```bash
# Create security group
aws ec2 create-security-group \
  --group-name iceshelves-instances \
  --description "Security group for IceShelves deployed instances"

# Allow SSH from your IP
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxxx \
  --protocol tcp \
  --port 22 \
  --cidr YOUR_IP/32

# Allow HTTP/HTTPS (if needed)
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxxx \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxxx \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0
```

#### IAM Roles

Use IAM roles instead of access keys:

```bash
# Create IAM role for IceShelves server
aws iam create-role \
  --role-name IceShelvesEC2Manager \
  --assume-role-policy-document file://trust-policy.json

# Attach EC2 full access policy
aws iam attach-role-policy \
  --role-name IceShelvesEC2Manager \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2FullAccess
```

## GCP Compute Engine Deployment

### Prerequisites

1. **GCP Account** with billing enabled
2. **GCP Project** created
3. **Service Account** with Compute Engine permissions
4. **VPC Network** configured
5. **Firewall Rules** for SSH and application ports

### Adding GCP as Deployment Target

#### Via Web UI

1. Navigate to **Clusters** → **Add Cluster**
2. Fill in the form:
   - **Name**: `gcp-us-central1`
   - **Description**: GCP Compute Engine deployment target
   - **Provider Type**: `gcp`
   - **Secrets Manager**: Choose secrets manager type
   - **Cloud Configuration**: Click to expand

3. **Cloud Configuration JSON**:

```json
{
  "project_id": "my-gcp-project",
  "zone": "us-central1-a",
  "machine_type": "e2-micro",
  "image_project": "ubuntu-os-cloud",
  "image_family": "ubuntu-2404-lts",
  "network": "default"
}
```

#### Via API

```bash
curl -X POST http://localhost:8001/iceshelves/api/targets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gcp-us-central1",
    "description": "GCP Compute Engine us-central1 zone",
    "provider_type": "gcp",
    "secrets_manager_type": "gcp",
    "secrets_config": {
      "project_id": "my-gcp-project",
      "secret_prefix": "iceshelves-"
    },
    "cloud_config": {
      "project_id": "my-gcp-project",
      "zone": "us-central1-a",
      "machine_type": "e2-micro",
      "image_project": "ubuntu-os-cloud",
      "image_family": "ubuntu-2404-lts",
      "network": "default"
    }
  }'
```

### Deploying to GCP

#### Via Web UI

1. Navigate to **Deploy**
2. Select a GCP-compatible egg (e.g., `gcp-ubuntu-base`)
3. Choose GCP deployment target
4. Enter instance name
5. Click **Deploy**

#### Via API

```bash
curl -X POST http://localhost:8001/iceshelves/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "egg_id": 6,
    "target_id": 3,
    "instance_name": "my-gcp-instance-01"
  }'
```

### GCP-Specific Configuration

#### Machine Types

**Cost-Optimized (e2 series):**
- `e2-micro` - $0.0084/hr (~$6/mo, free tier eligible) - 2 vCPU, 1 GB RAM
- `e2-small` - $0.0168/hr (~$12/mo) - 2 vCPU, 2 GB RAM
- `e2-medium` - $0.0336/hr (~$24/mo) - 2 vCPU, 4 GB RAM

**General Purpose (n2 series):**
- `n2-standard-2` - 2 vCPU, 8 GB RAM
- `n2-standard-4` - 4 vCPU, 16 GB RAM

**Compute-Optimized (c2 series):**
- `c2-standard-4` - 4 vCPU, 16 GB RAM
- `c2-standard-8` - 8 vCPU, 32 GB RAM

#### Free Tier

GCP offers always-free tier:
- 1 **e2-micro** instance per month (US regions only)
- 30 GB standard persistent disk
- 1 GB network egress per month

#### Service Accounts

Create service account for API access:

```bash
# Create service account
gcloud iam service-accounts create iceshelves-manager \
  --display-name="IceShelves Compute Manager"

# Grant Compute Engine permissions
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:iceshelves-manager@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/compute.instanceAdmin.v1"

# Create and download key
gcloud iam service-accounts keys create key.json \
  --iam-account=iceshelves-manager@PROJECT_ID.iam.gserviceaccount.com
```

Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
```

#### Firewall Rules

Create firewall rules for instances:

```bash
# Allow SSH
gcloud compute firewall-rules create allow-ssh \
  --allow tcp:22 \
  --source-ranges 0.0.0.0/0 \
  --target-tags ssh-server

# Allow HTTP/HTTPS
gcloud compute firewall-rules create allow-web \
  --allow tcp:80,tcp:443 \
  --source-ranges 0.0.0.0/0 \
  --target-tags http-server

# List firewall rules
gcloud compute firewall-rules list
```

Tag instances during deployment by adding to cloud_config:

```json
{
  "tags": ["ssh-server", "http-server"]
}
```

## Deployment Comparison

| Feature | LXD | KVM | AWS EC2 | GCP Compute |
|---------|-----|-----|---------|-------------|
| **Infrastructure** | Containers | Virtual Machines | Cloud VMs | Cloud VMs |
| **Cost** | Free (self-hosted) | Free (self-hosted) | Pay-per-use | Pay-per-use |
| **Startup Time** | < 1 second | 10-30 seconds | 30-60 seconds | 30-60 seconds |
| **Isolation** | Process-level | Full VM | Full VM | Full VM |
| **Cloud-init** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Networking** | Bridge/NAT | Bridge/NAT | VPC | VPC |
| **Storage** | ZFS/Btrfs pools | qcow2/raw | EBS volumes | Persistent disks |
| **Connection** | Direct/SSH/Agent | Direct | API (boto3) | API (gcloud) |
| **Best For** | Dev/Test, Microservices | Full OS testing | Production cloud | Production cloud |

## Best Practices

### Multi-Cloud Deployment

Design eggs to work across multiple providers:

```yaml
#cloud-config
# Universal configuration that works on LXD, KVM, AWS, and GCP

hostname: {{ hostname | default('universal-instance') }}
timezone: {{ timezone | default('UTC') }}

package_update: true
package_upgrade: true

packages:
  - vim
  - curl
  - git
  # Cloud provider CLIs installed conditionally via runcmd

users:
  - name: ubuntu
    groups: sudo
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']

# Detect cloud provider and configure accordingly
runcmd:
  - |
    if [ -f /sys/hypervisor/uuid ] && grep -q ec2 /sys/hypervisor/uuid; then
      echo "Running on AWS EC2"
      apt-get install -y awscli
    elif [ -f /sys/class/dmi/id/product_name ] && grep -q Google /sys/class/dmi/id/product_name; then
      echo "Running on GCP"
      apt-get install -y google-cloud-sdk
    else
      echo "Running on LXD/KVM"
    fi
```

### Cost Optimization

**AWS:**
- Use Reserved Instances for long-running workloads (up to 72% savings)
- Use Spot Instances for fault-tolerant workloads (up to 90% savings)
- Enable auto-scaling to match demand
- Use S3 for cold storage instead of EBS snapshots

**GCP:**
- Use Committed Use Discounts for predictable workloads (up to 57% savings)
- Use Preemptible VMs for batch processing (up to 80% savings)
- Leverage sustained use discounts (automatic)
- Use Cloud Storage Nearline/Coldline for archival

### Security

**All Providers:**
- Use secrets manager for credentials (never hardcode)
- Enable firewall rules with least privilege
- Use private subnets where possible
- Enable cloud provider security features (Security Hub, Security Command Center)
- Regular security updates via cloud-init
- Implement monitoring and alerting

**AWS:**
- Use IAM roles instead of access keys
- Enable VPC Flow Logs
- Use AWS Systems Manager Session Manager instead of SSH
- Enable CloudTrail for audit logging

**GCP:**
- Use service accounts with minimal permissions
- Enable VPC Flow Logs
- Use OS Login for centralized SSH key management
- Enable Cloud Audit Logs

### Monitoring

**AWS:**
- CloudWatch for metrics and logs
- CloudWatch Alarms for notifications
- AWS X-Ray for distributed tracing

**GCP:**
- Cloud Monitoring (formerly Stackdriver)
- Cloud Logging
- Cloud Trace for distributed tracing

## Troubleshooting

### AWS Deployment Failures

**Invalid AMI ID:**
- Verify AMI exists in the specified region
- Check AMI permissions (public vs private)
- Use `describe-images` to find correct AMI

**Security Group Errors:**
- Ensure security group exists in the same VPC as subnet
- Verify security group ID format: `sg-xxxxxxxxx`

**Subnet Errors:**
- Confirm subnet exists and has available IP addresses
- Verify subnet is in the specified availability zone

**Instance Limit Exceeded:**
- Check EC2 service quotas: `aws service-quotas list-service-quotas --service-code ec2`
- Request limit increase if needed

### GCP Deployment Failures

**Quota Exceeded:**
- Check quotas: `gcloud compute project-info describe --project=PROJECT_ID`
- Request quota increase via GCP Console

**Permission Denied:**
- Verify service account has `compute.instanceAdmin.v1` role
- Check `GOOGLE_APPLICATION_CREDENTIALS` is set correctly

**Image Not Found:**
- Verify image family exists: `gcloud compute images list --project=ubuntu-os-cloud --filter="family:ubuntu-2404-lts"`
- Check image project is spelled correctly

**Network Errors:**
- Confirm VPC network exists
- Verify firewall rules allow required traffic
- Check subnet has available IP addresses

### Cloud-Init Not Running

**Check Logs:**

AWS:
```bash
# View user-data
sudo cat /var/lib/cloud/instance/user-data.txt

# Check cloud-init logs
sudo cat /var/log/cloud-init.log
sudo cat /var/log/cloud-init-output.log
```

GCP:
```bash
# View startup script
sudo journalctl -u google-startup-scripts.service

# Check cloud-init logs
sudo cat /var/log/cloud-init.log
```

**Common Issues:**
- Invalid YAML syntax in cloud-init
- Missing `#cloud-config` header
- Package installation failures (check package names)
- Network connectivity issues during package downloads

## Advanced Topics

### Terraform Integration

Use IceShelves eggs with Terraform:

```hcl
resource "aws_instance" "iceshelves_deployed" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"

  user_data = templatefile("${path.module}/eggs/ubuntu-base/cloud-init.yaml", {
    hostname = "terraform-deployed"
    packages = ["nginx", "docker.io"]
  })

  tags = {
    Name        = "IceShelves-Deployed"
    ManagedBy   = "Terraform"
  }
}
```

### CI/CD Integration

Deploy via GitHub Actions:

```yaml
name: Deploy to Cloud

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
              "egg_id": 5,
              "target_id": 2,
              "instance_name": "app-${{ github.sha }}"
            }'
```

## Support

For cloud provider integration issues:
- [AWS EC2 Documentation](https://docs.aws.amazon.com/ec2/)
- [GCP Compute Documentation](https://cloud.google.com/compute/docs)
- [IceShelves Troubleshooting](./TROUBLESHOOTING.md)
- [IceShelves API Reference](./API.md)

**Support Channels:**
- GitHub Issues: Report bugs and feature requests
- Documentation: Check comprehensive guides
- Email: support@penguintech.group
