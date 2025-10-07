# AWS Ubuntu Base Egg

Minimal Ubuntu 24.04 LTS configuration for AWS EC2 instances.

## Overview

This egg provides a clean, secure Ubuntu 24.04 LTS base for AWS EC2 deployments with essential tools pre-installed and automatic security updates configured.

## What's Included

- **Operating System**: Ubuntu 24.04 LTS (Noble Numbat)
- **AWS CLI**: Pre-installed and ready to use
- **Essential Tools**: vim, curl, wget, git, htop, python3-pip
- **Security**:
  - SSH key-based authentication only (password auth disabled)
  - Root login disabled
  - Automatic security updates enabled
- **User**: Default ubuntu user with sudo privileges

## AWS Requirements

### Instance Type
- **Minimum**: t3.micro (1 vCPU, 1GB RAM)
- **Recommended**: t3.small (2 vCPU, 2GB RAM)

### AMI
This egg works with official Canonical Ubuntu 24.04 LTS AMIs:
- Filter: `ubuntu/images/hvm-ssd/ubuntu-noble-24.04-amd64-server-*`
- Owner: `099720109477` (Canonical)

### Security Groups
- Requires at least the `default` security group
- Recommended: Create a custom security group with:
  - SSH (22) from your IP/VPC
  - Any application-specific ports

### Networking
- Works in default VPC or custom VPC
- Public IP recommended for external SSH access
- Private subnet supported for internal-only instances

## Deployment Configuration

When deploying this egg to AWS, configure your deployment target with:

```json
{
  "provider_type": "aws",
  "cloud_config": {
    "region": "us-east-1",
    "ami": "ami-0e2c8caa4b6378d8c",
    "instance_type": "t3.micro",
    "security_groups": ["sg-xxxxxxxxx"],
    "subnet_id": "subnet-xxxxxxxxx",
    "key_name": "my-ec2-keypair"
  }
}
```

## Post-Deployment

### Accessing Your Instance

SSH into your instance using the key pair you specified:

```bash
ssh -i /path/to/your-keypair.pem ubuntu@<instance-public-ip>
```

### Verify Deployment

Check the deployment log:

```bash
cat /var/log/iceshelves-deployment.log
```

### AWS CLI Configuration

The AWS CLI is pre-installed. Configure it with your credentials:

```bash
aws configure
```

Or attach an IAM role to the instance for automatic credential management.

## Customization

### Cloud-Init Overrides

You can override cloud-init configuration during deployment:

```json
{
  "hostname": "my-custom-hostname",
  "packages": ["nginx", "docker.io"],
  "timezone": "America/New_York"
}
```

### Add Custom Scripts

Use the `runcmd` section to run custom commands:

```yaml
runcmd:
  - apt-get install -y nodejs npm
  - npm install -g pm2
  - systemctl enable pm2
```

## Cost Considerations

- **t3.micro**: ~$0.0104/hour (~$7.50/month)
- **t3.small**: ~$0.0208/hour (~$15/month)

Pricing varies by region. Include additional costs for:
- EBS storage (root volume)
- Data transfer
- Elastic IP (if using static IP)

## Security Best Practices

1. **Use IAM Roles**: Attach IAM roles instead of embedding credentials
2. **Security Groups**: Restrict SSH access to known IPs
3. **Key Management**: Use AWS Systems Manager Session Manager as SSH alternative
4. **Monitoring**: Enable CloudWatch monitoring and alarms
5. **Backups**: Regular AMI snapshots for disaster recovery

## Troubleshooting

### Cloud-Init Not Running

Check cloud-init status:

```bash
sudo cloud-init status
```

View logs:

```bash
sudo cat /var/log/cloud-init.log
sudo cat /var/log/cloud-init-output.log
```

### Cannot SSH

1. Verify security group allows SSH (port 22) from your IP
2. Ensure instance has public IP (if accessing from internet)
3. Verify correct key pair being used
4. Check instance system log via AWS Console

### AWS CLI Not Working

Verify IAM role or configure credentials:

```bash
aws sts get-caller-identity
```

## Support

For issues with this egg, check:
- [IceShelves Troubleshooting Guide](../../docs/iceshelves/TROUBLESHOOTING.md)
- [AWS EC2 Documentation](https://docs.aws.amazon.com/ec2/)
- [Ubuntu Cloud Images](https://cloud-images.ubuntu.com/)

## Version History

- **1.0.0**: Initial release with Ubuntu 24.04 LTS support
