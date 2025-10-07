# Ubuntu Base 24.04 LTS

## Description
Minimal Ubuntu 24.04 LTS system with essential packages and secure configuration.

## What's Included
- Ubuntu 24.04 LTS (Noble Numbat)
- Essential development tools (vim, git, build-essential)
- Network utilities (curl, wget, net-tools)
- System monitoring (htop)
- Secure SSH configuration (password auth disabled)
- Automatic security updates

## Default Configuration
- **User**: ubuntu (with sudo access)
- **SSH**: Key-based authentication only
- **Timezone**: UTC
- **Locale**: en_US.UTF-8

## Usage

### Deploy via Web Interface
1. Navigate to **Deploy** page
2. Select **ubuntu-base** egg
3. Choose target cluster
4. Specify instance name
5. Click **Deploy**

### Deploy via API
```bash
curl -X POST https://iceshelves.example.com/deploy \
  -d "egg_id=1" \
  -d "cluster_id=1" \
  -d "instance_name=my-ubuntu-instance"
```

## Customization
This egg can be customized by:
- Modifying `cloud-init.yaml` to add more packages or configurations
- Creating a derived egg from this template
- Using deployment config overrides

## Post-Deployment
After deployment, you can:
1. SSH into the instance using your configured key
2. Run `cloud-init status` to check cloud-init completion
3. Install additional software as needed

## Version
- Egg Version: 1.0.0
- Base Image: ubuntu/24.04
- Last Updated: 2025-10-07
