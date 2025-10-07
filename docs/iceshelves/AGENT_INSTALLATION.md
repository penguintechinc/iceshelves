# IceShelves Agent Installation Guide

Complete guide for installing and configuring the IceShelves polling agent on LXD/KVM hypervisors.

## Overview

The IceShelves agent is a lightweight Python daemon that polls the IceShelves server for pending deployments and executes them on the local hypervisor. This enables deployments in air-gapped environments and through strict firewalls.

**Architecture:**
```
IceShelves Server <── Agent (polls every 1-5 min) ── LXD/KVM Hypervisor
```

## Prerequisites

### System Requirements
- Ubuntu 22.04 LTS or 24.04 LTS
- Python 3.10 or higher
- LXD installed and configured
- Network access to IceShelves server (outbound only)

### Required Permissions
- Root access (for systemd service)
- LXD group membership (for LXD operations)

## Installation Methods

### Method 1: Automated Installation (Recommended)

#### Step 1: Get Agent Key from IceShelves

1. Log into IceShelves web interface
2. Navigate to **Clusters** → **Add Cluster**
3. Select **Agent Poll** as connection method
4. Fill in cluster details
5. Click **Add** - an agent key will be generated
6. **Copy the agent key** - you'll need it for installation

#### Step 2: Install Agent using Makefile

On the hypervisor:

```bash
# Clone IceShelves repository
git clone https://github.com/PenguinCloud/iceshelves.git
cd iceshelves

# Install agent
sudo make iceshelves-agent \
  CLUSTER_ID=1 \
  AGENT_KEY=your-agent-key-here \
  ICESHELVES_SERVER=https://iceshelves.example.com
```

This will:
- Copy agent script to `/usr/local/bin/iceshelves-agent`
- Create systemd service
- Enable and start the service

#### Step 3: Verify Installation

```bash
# Check service status
sudo systemctl status iceshelves-agent

# View logs
sudo journalctl -u iceshelves-agent -f
```

### Method 2: Manual Installation

#### Step 1: Install Dependencies

```bash
# Install Python and pip
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv

# Install required Python packages
sudo pip3 install requests pylxd pyyaml
```

#### Step 2: Copy Agent Script

```bash
# Create directory
sudo mkdir -p /opt/iceshelves

# Copy agent script
sudo cp scripts/iceshelves-agent.py /opt/iceshelves/agent.py
sudo chmod +x /opt/iceshelves/agent.py

# Create symlink
sudo ln -s /opt/iceshelves/agent.py /usr/local/bin/iceshelves-agent
```

#### Step 3: Create Systemd Service

```bash
sudo tee /etc/systemd/system/iceshelves-agent.service > /dev/null <<EOF
[Unit]
Description=IceShelves Deployment Agent
After=network.target lxd.service
Wants=lxd.service

[Service]
Type=simple
User=root
Environment=ICESHELVES_SERVER=https://iceshelves.example.com
Environment=ICESHELVES_CLUSTER_ID=1
Environment=ICESHELVES_AGENT_KEY=your-agent-key-here
Environment=ICESHELVES_POLL_INTERVAL=300
ExecStart=/usr/local/bin/iceshelves-agent
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

#### Step 4: Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable iceshelves-agent

# Start service
sudo systemctl start iceshelves-agent

# Check status
sudo systemctl status iceshelves-agent
```

### Method 3: Docker Installation

Run agent as a Docker container:

```bash
docker run -d \
  --name iceshelves-agent \
  --restart always \
  --network host \
  -v /var/lib/lxd/unix.socket:/var/lib/lxd/unix.socket \
  -e ICESHELVES_SERVER=https://iceshelves.example.com \
  -e ICESHELVES_CLUSTER_ID=1 \
  -e ICESHELVES_AGENT_KEY=your-agent-key \
  -e ICESHELVES_POLL_INTERVAL=300 \
  ghcr.io/penguintechinc/iceshelves-agent:latest
```

## Configuration

### Environment Variables

- **ICESHELVES_SERVER** (required) - IceShelves server URL
- **ICESHELVES_CLUSTER_ID** (required) - Cluster ID from IceShelves
- **ICESHELVES_AGENT_KEY** (required) - Agent authentication key
- **ICESHELVES_POLL_INTERVAL** (optional) - Poll interval in seconds (default: 300)

### Poll Interval Recommendations

| Environment | Interval | Use Case |
|-------------|----------|----------|
| Development | 60s | Fast feedback for testing |
| Staging | 180s (3min) | Balance between responsiveness and load |
| Production | 300s (5min) | Standard production setting |
| Low-priority | 600s (10min) | Reduce server load |

### Advanced Configuration

Edit `/etc/systemd/system/iceshelves-agent.service`:

```ini
[Service]
# Enable debug logging
Environment=ICESHELVES_LOG_LEVEL=DEBUG

# Custom poll interval
Environment=ICESHELVES_POLL_INTERVAL=180

# Connection timeout
Environment=ICESHELVES_TIMEOUT=30
```

After changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart iceshelves-agent
```

## Security

### Agent Key Security

**Best Practices:**
- Store agent key securely (systemd environment file)
- Use unique key per cluster
- Rotate keys periodically
- Never commit keys to version control

**Create Secure Environment File:**

```bash
# Create environment file
sudo tee /etc/iceshelves/agent.env > /dev/null <<EOF
ICESHELVES_SERVER=https://iceshelves.example.com
ICESHELVES_CLUSTER_ID=1
ICESHELVES_AGENT_KEY=your-agent-key-here
ICESHELVES_POLL_INTERVAL=300
EOF

# Secure permissions
sudo chmod 600 /etc/iceshelves/agent.env
sudo chown root:root /etc/iceshelves/agent.env

# Update systemd service
sudo tee -a /etc/systemd/system/iceshelves-agent.service > /dev/null <<EOF
EnvironmentFile=/etc/iceshelves/agent.env
EOF

sudo systemctl daemon-reload
sudo systemctl restart iceshelves-agent
```

### Network Security

**Firewall Rules:**
```bash
# Allow outbound HTTPS to IceShelves server
sudo ufw allow out to iceshelves.example.com port 443

# Block all other outbound (if needed)
sudo ufw default deny outgoing
sudo ufw default deny incoming
sudo ufw allow ssh
```

**TLS Verification:**
Agent always verifies TLS certificates. For self-signed certificates:

```bash
# Add custom CA to system
sudo cp iceshelves-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

## Monitoring

### Check Agent Status

```bash
# Service status
sudo systemctl status iceshelves-agent

# Is agent running?
systemctl is-active iceshelves-agent
```

### View Logs

```bash
# Real-time logs
sudo journalctl -u iceshelves-agent -f

# Last 100 lines
sudo journalctl -u iceshelves-agent -n 100

# Logs since yesterday
sudo journalctl -u iceshelves-agent --since yesterday

# Grep for errors
sudo journalctl -u iceshelves-agent | grep ERROR
```

### Agent Health Check

```bash
# Check last seen time in IceShelves
curl -s http://iceshelves.example.com/api/clusters/1 | jq '.agent_last_seen'

# Should be within poll_interval * 2
```

### Metrics

Monitor these metrics:
- Last seen timestamp
- Deployment success rate
- Deployment duration
- Poll failures

## Troubleshooting

### Agent Won't Start

**Check service status:**
```bash
sudo systemctl status iceshelves-agent
sudo journalctl -u iceshelves-agent -n 50
```

**Common issues:**
- Invalid agent key
- Server unreachable
- Python dependencies missing
- LXD not running

### Agent Not Polling

**Verify configuration:**
```bash
# Check environment variables
sudo systemctl show iceshelves-agent | grep Environment
```

**Test connectivity:**
```bash
# Can agent reach server?
curl -I https://iceshelves.example.com

# Test API endpoint
curl -X POST https://iceshelves.example.com/api/agent/poll/1 \
  -H "X-Agent-Key: your-key"
```

### Deployments Not Executing

**Check LXD access:**
```bash
# Can agent access LXD?
sudo lxc list

# Check LXD status
sudo lxc cluster list  # If clustered
```

**View deployment logs:**
```bash
sudo journalctl -u iceshelves-agent | grep deployment
```

### High CPU/Memory Usage

**Check poll interval:**
```bash
# Increase interval if too aggressive
sudo systemctl edit iceshelves-agent
# Add: Environment=ICESHELVES_POLL_INTERVAL=600
```

**Monitor resource usage:**
```bash
# CPU and memory
top -p $(pgrep -f iceshelves-agent)

# Detailed stats
pidstat -p $(pgrep -f iceshelves-agent) 1
```

## Maintenance

### Update Agent

```bash
# Pull latest changes
cd /path/to/iceshelves
git pull

# Restart agent
sudo systemctl restart iceshelves-agent
```

### Rotate Agent Key

1. Generate new key in IceShelves UI
2. Update environment:
```bash
sudo vim /etc/iceshelves/agent.env
# Update ICESHELVES_AGENT_KEY
sudo systemctl restart iceshelves-agent
```

### Backup Configuration

```bash
# Backup systemd service and env file
sudo cp /etc/systemd/system/iceshelves-agent.service /backup/
sudo cp /etc/iceshelves/agent.env /backup/
```

## Uninstallation

```bash
# Stop and disable service
sudo systemctl stop iceshelves-agent
sudo systemctl disable iceshelves-agent

# Remove files
sudo rm /etc/systemd/system/iceshelves-agent.service
sudo rm /usr/local/bin/iceshelves-agent
sudo rm -rf /opt/iceshelves
sudo rm -rf /etc/iceshelves

# Reload systemd
sudo systemctl daemon-reload
```

## Best Practices

1. **Use systemd** for process management
2. **Secure agent keys** with proper file permissions
3. **Monitor agent health** regularly
4. **Set appropriate poll interval** for your needs
5. **Keep agent updated** to latest version
6. **Log rotation** to prevent disk fill
7. **Test in development** before production
8. **Document configuration** for team
9. **Backup configuration** files
10. **Monitor deployments** for failures

## Support

For issues with agent installation:
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review agent logs
- Verify network connectivity
- Check IceShelves server logs
- Contact support@penguintech.group
