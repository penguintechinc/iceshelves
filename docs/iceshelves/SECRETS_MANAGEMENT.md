# IceShelves Secrets Management

Complete guide for managing sensitive credentials using AWS Secrets Manager, GCP Secret Manager, Infisical, or database storage.

## Table of Contents
- [Overview](#overview)
- [Database Storage (Default)](#database-storage-default)
- [AWS Secrets Manager](#aws-secrets-manager)
- [GCP Secret Manager](#gcp-secret-manager)
- [Infisical](#infisical)
- [Migration Between Secrets Managers](#migration-between-secrets-managers)
- [Best Practices](#best-practices)

## Overview

IceShelves supports multiple secrets management backends for storing sensitive credentials like SSH keys, certificates, and API keys. This allows you to choose the solution that best fits your security requirements and infrastructure.

**Supported Secrets Managers:**
- **Database** - Default, stores secrets directly in PostgreSQL (not recommended for production)
- **AWS Secrets Manager** - AWS-native secrets management service
- **GCP Secret Manager** - Google Cloud Platform secrets management
- **Infisical** - Open-source secrets management platform

**What Can Be Stored:**
- SSH private keys (for SSH-based LXD connections)
- TLS client certificates and keys (for LXD API connections)
- Trust passwords (for LXD initial setup)
- Agent keys (for polling agents)
- Cloud provider credentials (AWS access keys, GCP service account keys)

## Database Storage (Default)

### Overview

By default, IceShelves stores secrets directly in the PostgreSQL database. This is the simplest method but has security limitations.

**Pros:**
- No additional infrastructure required
- Simple to set up and use
- Works out of the box

**Cons:**
- Secrets stored in plain text in database
- Database backups contain sensitive data
- No audit logging of secret access
- Not compliant with many security standards

**When to Use:**
- Development and testing
- Single-user deployments
- Non-production environments

### Configuration

Database storage is the default. No configuration needed:

```python
# Target configuration
{
    "secrets_manager_type": "database",
    "secrets_config": {}
}
```

### Accessing Secrets

Secrets are automatically retrieved from database fields:

```python
from secrets import get_secrets_manager

# Get secrets manager
secrets_mgr = get_secrets_manager(target_config, db, target_id)

# Retrieve secret
ssh_key = secrets_mgr.get_secret('ssh_key')
```

## AWS Secrets Manager

### Overview

AWS Secrets Manager is a fully managed service for storing, retrieving, and rotating secrets.

**Pros:**
- Enterprise-grade security
- Automatic secret rotation
- Fine-grained IAM access control
- Audit logging via CloudTrail
- Encryption at rest using AWS KMS

**Cons:**
- AWS-only (requires AWS account)
- Cost: $0.40/secret/month + $0.05 per 10,000 API calls

**When to Use:**
- Production deployments on AWS
- Multi-user teams
- Compliance requirements (SOC2, HIPAA, etc.)

### Prerequisites

1. **AWS Account** with permissions to:
   - Create secrets (`secretsmanager:CreateSecret`)
   - Retrieve secrets (`secretsmanager:GetSecretValue`)
   - List secrets (`secretsmanager:ListSecrets`)

2. **AWS Credentials** configured:
   - IAM role attached to IceShelves server (recommended)
   - Or access key/secret key in environment variables

### Setup

#### 1. Create IAM Policy

```bash
# Create policy for IceShelves
cat > iceshelves-secrets-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:GetSecretValue",
        "secretsmanager:PutSecretValue",
        "secretsmanager:DeleteSecret",
        "secretsmanager:ListSecrets"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:iceshelves/*"
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name IceShelvesSecretsAccess \
  --policy-document file://iceshelves-secrets-policy.json
```

#### 2. Attach Policy to IAM Role

```bash
# Attach to existing role
aws iam attach-role-policy \
  --role-name IceShelvesServerRole \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/IceShelvesSecretsAccess
```

#### 3. Configure Deployment Target

```json
{
  "name": "secure-lxd-cluster",
  "provider_type": "lxd",
  "secrets_manager_type": "aws",
  "secrets_config": {
    "region": "us-east-1",
    "secret_prefix": "iceshelves/cluster-name/"
  }
}
```

### Usage

#### Store SSH Key in AWS Secrets Manager

```bash
# Store SSH private key
aws secretsmanager create-secret \
  --name iceshelves/my-cluster/ssh_key \
  --secret-string file://~/.ssh/id_rsa \
  --region us-east-1
```

#### Retrieve Secret

Secrets are automatically retrieved when connecting:

```python
from secrets import AWSSecretsManager

# Initialize
secrets_mgr = AWSSecretsManager({
    "region": "us-east-1",
    "secret_prefix": "iceshelves/my-cluster/"
})

# Get secret
ssh_key = secrets_mgr.get_secret('ssh_key')
```

### Secret Rotation

Enable automatic rotation for enhanced security:

```bash
# Enable rotation
aws secretsmanager rotate-secret \
  --secret-id iceshelves/my-cluster/ssh_key \
  --rotation-lambda-arn arn:aws:lambda:region:account:function:rotation-function \
  --rotation-rules AutomaticallyAfterDays=30
```

## GCP Secret Manager

### Overview

GCP Secret Manager is Google Cloud's managed service for storing and accessing secrets.

**Pros:**
- Enterprise-grade security
- Integration with Google Cloud IAM
- Automatic replication across regions
- Audit logging via Cloud Logging
- Versioning of secrets

**Cons:**
- GCP-only (requires Google Cloud project)
- Cost: $0.06 per 10,000 access operations + storage costs

**When to Use:**
- Production deployments on GCP
- Multi-cloud with GCP presence
- Compliance requirements

### Prerequisites

1. **GCP Project** with Secret Manager API enabled:
   ```bash
   gcloud services enable secretmanager.googleapis.com
   ```

2. **Service Account** with permissions:
   - `secretmanager.secrets.create`
   - `secretmanager.secrets.get`
   - `secretmanager.versions.access`

### Setup

#### 1. Create Service Account

```bash
# Create service account
gcloud iam service-accounts create iceshelves-secrets \
  --display-name="IceShelves Secrets Manager"

# Grant permissions
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:iceshelves-secrets@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.admin"

# Create and download key
gcloud iam service-accounts keys create key.json \
  --iam-account=iceshelves-secrets@PROJECT_ID.iam.gserviceaccount.com
```

#### 2. Configure Environment

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
export GCP_PROJECT_ID="your-project-id"
```

#### 3. Configure Deployment Target

```json
{
  "name": "secure-lxd-cluster",
  "provider_type": "lxd",
  "secrets_manager_type": "gcp",
  "secrets_config": {
    "project_id": "my-gcp-project",
    "secret_prefix": "iceshelves-cluster-name-"
  }
}
```

### Usage

#### Store SSH Key in GCP Secret Manager

```bash
# Create secret
echo -n "$(cat ~/.ssh/id_rsa)" | \
  gcloud secrets create iceshelves-my-cluster-ssh-key \
  --data-file=- \
  --replication-policy="automatic"
```

#### Retrieve Secret

```python
from secrets import GCPSecretsManager

# Initialize
secrets_mgr = GCPSecretsManager({
    "project_id": "my-gcp-project",
    "secret_prefix": "iceshelves-my-cluster-"
})

# Get secret
ssh_key = secrets_mgr.get_secret('ssh_key')  # Accesses: iceshelves-my-cluster-ssh-key
```

### Secret Versioning

GCP automatically versions secrets:

```bash
# Add new version
echo -n "new-secret-value" | \
  gcloud secrets versions add iceshelves-my-cluster-ssh-key \
  --data-file=-

# List versions
gcloud secrets versions list iceshelves-my-cluster-ssh-key

# Access specific version
gcloud secrets versions access 2 --secret=iceshelves-my-cluster-ssh-key
```

## Infisical

### Overview

Infisical is an open-source, end-to-end encrypted secrets management platform. Can be self-hosted or used as a service.

**Pros:**
- Open source (self-hostable)
- End-to-end encryption
- Multi-environment support
- Secret versioning
- Team collaboration features
- Lower cost than cloud providers

**Cons:**
- Requires self-hosting or Infisical Cloud account
- Less mature than AWS/GCP solutions
- Community support only (unless enterprise)

**When to Use:**
- Self-hosted secrets management
- Multi-cloud deployments
- Open-source preference
- Cost optimization

### Prerequisites

1. **Infisical Instance** (cloud or self-hosted)
2. **Infisical Project** created
3. **Service Token** or **Universal Auth** credentials

### Setup

#### 1. Install Infisical (Self-Hosted)

```bash
# Using Docker Compose
docker-compose up -d infisical
```

Or use Infisical Cloud: https://app.infisical.com

#### 2. Create Project and Service Token

Via Infisical UI:
1. Create project: "iceshelves-secrets"
2. Create environment: "production"
3. Generate service token with read/write permissions

#### 3. Configure Deployment Target

```json
{
  "name": "secure-lxd-cluster",
  "provider_type": "lxd",
  "secrets_manager_type": "infisical",
  "secrets_config": {
    "client_id": "universal-auth-client-id",
    "client_secret": "universal-auth-client-secret",
    "project_id": "project-id-from-infisical",
    "environment": "prod",
    "secret_path": "/iceshelves/cluster-name"
  }
}
```

### Usage

#### Store SSH Key in Infisical

Via Infisical UI:
1. Navigate to project → environment
2. Click "Add Secret"
3. Key: `ssh_key`
4. Value: `<paste SSH private key>`
5. Path: `/iceshelves/cluster-name`

Or via API:

```bash
# Using Infisical CLI
infisical secrets set ssh_key --value="$(cat ~/.ssh/id_rsa)" \
  --path="/iceshelves/cluster-name" \
  --env=prod
```

#### Retrieve Secret

```python
from secrets import InfisicalSecretsManager

# Initialize
secrets_mgr = InfisicalSecretsManager({
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "project_id": "your-project-id",
    "environment": "prod",
    "secret_path": "/iceshelves/cluster-name"
})

# Get secret
ssh_key = secrets_mgr.get_secret('ssh_key')
```

### Infisical Features

**Secret Versioning:**
- Automatic versioning of secret changes
- Rollback to previous versions
- Audit trail of changes

**Access Control:**
- Role-based access control (RBAC)
- Environment-based permissions
- Secret-level permissions

**Integrations:**
- GitHub Actions
- GitLab CI
- Jenkins
- Kubernetes via Infisical Operator

## Migration Between Secrets Managers

### From Database to AWS Secrets Manager

```python
#!/usr/bin/env python3
import boto3
from models import db

# Initialize AWS Secrets Manager
client = boto3.client('secretsmanager', region_name='us-east-1')

# Get all targets using database secrets
targets = db(db.deployment_targets.secrets_manager_type == 'database').select()

for target in targets:
    prefix = f"iceshelves/{target.name}/"

    # Migrate SSH key
    if target.ssh_key:
        client.create_secret(
            Name=f"{prefix}ssh_key",
            SecretString=target.ssh_key
        )

    # Migrate client cert
    if target.client_cert:
        client.create_secret(
            Name=f"{prefix}client_cert",
            SecretString=target.client_cert
        )

    # Update target configuration
    target.update_record(
        secrets_manager_type='aws',
        secrets_config={
            'region': 'us-east-1',
            'secret_prefix': prefix
        },
        # Clear database fields
        ssh_key=None,
        client_cert=None,
        client_key=None
    )

db.commit()
print("Migration completed!")
```

### From AWS to GCP

```python
#!/usr/bin/env python3
import boto3
from google.cloud import secretmanager

# Initialize clients
aws_client = boto3.client('secretsmanager', region_name='us-east-1')
gcp_client = secretmanager.SecretManagerServiceClient()
project_id = "your-gcp-project"

# List AWS secrets with prefix
paginator = aws_client.get_paginator('list_secrets')
for page in paginator.paginate():
    for secret in page['SecretList']:
        if secret['Name'].startswith('iceshelves/'):
            # Get secret value from AWS
            response = aws_client.get_secret_value(SecretId=secret['Name'])
            secret_value = response['SecretString']

            # Create in GCP
            gcp_secret_name = secret['Name'].replace('/', '-')
            parent = f"projects/{project_id}"

            # Create secret
            gcp_secret = gcp_client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": gcp_secret_name,
                    "secret": {"replication": {"automatic": {}}}
                }
            )

            # Add secret version
            gcp_client.add_secret_version(
                request={
                    "parent": gcp_secret.name,
                    "payload": {"data": secret_value.encode('UTF-8')}
                }
            )

print("Migration from AWS to GCP completed!")
```

## Best Practices

### Security

1. **Never Store Secrets in Code**
   - Use secrets manager for all sensitive data
   - Never commit secrets to version control
   - Use `.env.example` with dummy values

2. **Principle of Least Privilege**
   - Grant minimum necessary permissions
   - Use separate service accounts per environment
   - Regularly audit access logs

3. **Secret Rotation**
   - Rotate secrets regularly (30-90 days)
   - Automate rotation where possible
   - Test rotation procedures

4. **Encryption**
   - All secrets managers encrypt at rest
   - Use TLS for all API communications
   - Enable encryption in transit

### Operations

1. **Environment Separation**
   - Use separate secrets for dev/staging/prod
   - Different prefixes or projects per environment
   - Never share production secrets with development

2. **Backup and Recovery**
   - AWS Secrets Manager: Automatic backups
   - GCP Secret Manager: Automatic versioning
   - Infisical: Regular database backups
   - Document recovery procedures

3. **Monitoring**
   - Enable audit logging
   - Monitor secret access patterns
   - Alert on unauthorized access attempts
   - Track secret age and rotation status

4. **Documentation**
   - Document which secrets exist
   - Record secret purposes
   - Maintain recovery procedures
   - Keep runbooks updated

### Cost Optimization

**AWS Secrets Manager:**
- Delete unused secrets (incur costs even when not accessed)
- Use secret caching to reduce API calls
- Consider KMS key reuse

**GCP Secret Manager:**
- Delete old secret versions
- Use automatic replication only when needed
- Cache secrets in application

**Infisical:**
- Self-host to eliminate per-secret costs
- Use Infisical Cloud free tier for small deployments

## Troubleshooting

### AWS Secrets Manager

**Access Denied:**
```
ClientError: An error occurred (AccessDeniedException) when calling the GetSecretValue operation
```

Solutions:
- Verify IAM role has `secretsmanager:GetSecretValue` permission
- Check resource ARN in policy matches secret name
- Confirm AWS region is correct

**Secret Not Found:**
- Verify secret name matches exactly (case-sensitive)
- Check secret prefix configuration
- Ensure secret exists in the specified region

### GCP Secret Manager

**Permission Denied:**
```
google.api_core.exceptions.PermissionDenied: 403 Permission denied on resource
```

Solutions:
- Verify service account has `secretmanager.versions.access` role
- Check `GOOGLE_APPLICATION_CREDENTIALS` environment variable
- Confirm project ID is correct

**Secret Not Found:**
- GCP uses hyphens in secret names (not slashes or underscores)
- Verify secret exists: `gcloud secrets list`
- Check secret name transformation (underscores → hyphens)

### Infisical

**Authentication Failed:**
```
InfisicalError: Invalid credentials
```

Solutions:
- Verify client ID and client secret
- Check service token hasn't expired
- Confirm project ID and environment are correct

**Connection Timeout:**
- Check Infisical instance is accessible
- Verify firewall rules
- Confirm correct URL (cloud vs self-hosted)

## Support

For secrets management issues:
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [GCP Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [Infisical Documentation](https://infisical.com/docs)
- [IceShelves Troubleshooting](./TROUBLESHOOTING.md)

**Security Concerns:**
- Email: security@penguintech.group
- DO NOT include actual secrets in support requests
