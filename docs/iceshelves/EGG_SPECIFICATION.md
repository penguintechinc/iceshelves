# Egg Specification

## Overview
An "egg" is a deployment package containing cloud-init scripts, LXD profiles, and configuration for deploying instances to LXD or KVM.

## Egg Directory Structure
```
eggs/
└── egg-name/
    ├── cloud-init.yaml      # Cloud-init configuration (required)
    ├── lxd-profile.yaml     # LXD profile (optional)
    ├── kvm-config.xml       # KVM libvirt config (optional)
    ├── metadata.json        # Egg metadata (required)
    └── README.md            # Documentation (recommended)
```

## metadata.json Format
```json
{
  "name": "egg-name",
  "version": "1.0.0",
  "description": "Description of what this egg provides",
  "category": "base|webserver|database|kubernetes|docker|custom",
  "egg_type": "lxd-container|kvm-vm|hybrid",
  "base_image": "ubuntu/24.04",
  "author": "Your Name",
  "created": "2025-10-07T00:00:00Z",
  "tags": ["ubuntu", "tag1", "tag2"],
  "requirements": {
    "min_memory_mb": 512,
    "min_disk_gb": 5,
    "min_cores": 1
  },
  "features": [
    "Feature 1",
    "Feature 2"
  ]
}
```

## cloud-init.yaml Format
Standard cloud-init YAML configuration. See [Cloud-init Examples](CLOUD_INIT_EXAMPLES.md).

## Creating a New Egg

### Method 1: From Template (Web UI)
1. Navigate to **Eggs** → **Create New Egg**
2. Select a template
3. Fill in required variables
4. Click **Create**

### Method 2: Manual Creation
```bash
cd apps/iceshelves/libraries/eggs/
mkdir my-new-egg
cd my-new-egg

# Create cloud-init.yaml
cat > cloud-init.yaml <<EOF
#cloud-config
hostname: my-instance
packages:
  - vim
  - curl
EOF

# Create metadata.json
cat > metadata.json <<EOF
{
  "name": "my-new-egg",
  "version": "1.0.0",
  "description": "My custom egg",
  "category": "custom",
  "egg_type": "lxd-container",
  "base_image": "ubuntu/24.04"
}
EOF

# Create README.md
echo "# My New Egg" > README.md
```

### Method 3: API
```bash
curl -X POST http://iceshelves:8000/api/eggs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-egg",
    "template_id": 1,
    "variables": {
      "hostname": "my-host",
      "packages": ["nginx", "vim"]
    }
  }'
```

## Egg Types

### lxd-container
- Deploys as LXD system container
- Fast deployment
- Shared kernel with host
- Best for: Most Linux workloads

### kvm-vm
- Deploys as KVM virtual machine
- Full kernel isolation
- Can run non-Linux OS
- Best for: Windows, non-Linux OS, kernel isolation requirements

### hybrid
- Supports both LXD and KVM deployment
- User chooses at deployment time

## Best Practices

1. **Always include README.md** - Document your egg thoroughly
2. **Use semantic versioning** - Version your eggs properly
3. **Test cloud-init** - Validate YAML before deployment
4. **Include metadata** - Proper metadata helps discoverability
5. **Set requirements** - Specify minimum resources needed
6. **Use tags** - Tag eggs for easy searching
7. **Document post-deployment** - Include setup instructions
8. **Keep it simple** - One purpose per egg (UNIX philosophy)

## Example Eggs
See the pre-built eggs in `apps/iceshelves/libraries/eggs/`:
- **ubuntu-base** - Minimal Ubuntu system
- **ubuntu-docker** - Docker host
- **ubuntu-nginx** - Web server
- **ubuntu-k8s-node** - Kubernetes node
