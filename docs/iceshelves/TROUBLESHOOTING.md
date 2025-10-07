# IceShelves Troubleshooting Guide

Common issues and solutions for IceShelves deployment platform.

## Table of Contents
- [Installation Issues](#installation-issues)
- [Connection Problems](#connection-problems)
- [Deployment Failures](#deployment-failures)
- [Agent Issues](#agent-issues)
- [Performance Problems](#performance-problems)
- [Database Issues](#database-issues)

## Installation Issues

### Docker Compose Won't Start

**Symptom:** `docker-compose up -d` fails

**Solutions:**
```bash
# Check Docker is running
sudo systemctl status docker

# Check for port conflicts
sudo netstat -tulpn | grep 8001

# Verify .env file exists
cat .env | grep POSTGRES

# Check Docker Compose syntax
docker-compose config

# View detailed errors
docker-compose up
```

### Database Migration Fails

**Symptom:** "Migration failed" error on startup

**Solutions:**
```bash
# Check database connectivity
docker-compose exec postgres pg_isready

# View migration logs
docker-compose logs iceshelves | grep migration

# Force clean migration
docker-compose down -v
docker-compose up -d postgres
# Wait 10 seconds
docker-compose up -d iceshelves
```

### Python Dependencies Missing

**Symptom:** `ImportError` or `ModuleNotFoundError`

**Solutions:**
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
python3 -c "import pylxd; print(pylxd.__version__)"
python3 -c "import yaml; print(yaml.__version__)"

# Check Python version
python3 --version  # Should be 3.12+
```

## Connection Problems

### Cannot Connect to LXD Cluster (Direct API)

**Symptom:** "Connection refused" or "Certificate error"

**Diagnosis:**
```bash
# Test LXD endpoint
curl -k https://lxd-host:8443

# Verify LXD is listening
lxc config get core.https_address

# Check firewall
sudo ufw status
```

**Solutions:**

**LXD Not Listening on Network:**
```bash
# On LXD host
lxc config set core.https_address "[::]:8443"
sudo systemctl restart snap.lxd.daemon
```

**Certificate Trust Issues:**
```bash
# On LXD host, add client certificate
lxc config trust add iceshelves-client.crt
```

**Firewall Blocking:**
```bash
# On LXD host
sudo ufw allow 8443/tcp
```

### SSH Tunnel Connection Fails

**Symptom:** "SSH connection failed" or "Permission denied"

**Solutions:**

**SSH Key Not Accepted:**
```bash
# Verify SSH key format
head -1 your-key.pem  # Should be: -----BEGIN ... PRIVATE KEY-----

# Test SSH connection manually
ssh -i your-key.pem ubuntu@lxd-host

# Check permissions
chmod 600 your-key.pem
```

**SSH Service Not Running:**
```bash
# On LXD host
sudo systemctl status sshd
sudo systemctl start sshd
```

**Port Not Open:**
```bash
# On LXD host
sudo ufw allow 22/tcp
```

### Agent Not Checking In

**Symptom:** Agent last_seen is old or null

**Diagnosis:**
```bash
# Check agent is running
sudo systemctl status iceshelves-agent

# View agent logs
sudo journalctl -u iceshelves-agent -n 50

# Test API endpoint manually
curl -X POST https://iceshelves.example.com/api/agent/poll/1 \
  -H "X-Agent-Key: your-key"
```

**Solutions:**

**Agent Not Running:**
```bash
sudo systemctl start iceshelves-agent
sudo systemctl enable iceshelves-agent
```

**Invalid Agent Key:**
```bash
# Regenerate key in IceShelves UI
# Update agent configuration
sudo vim /etc/iceshelves/agent.env
sudo systemctl restart iceshelves-agent
```

**Network Connectivity:**
```bash
# Test connectivity
ping iceshelves.example.com
curl -I https://iceshelves.example.com

# Check firewall
sudo ufw status
```

## Deployment Failures

### Deployment Stuck in "Pending"

**Symptom:** Deployment never progresses from pending status

**Causes & Solutions:**

**For Agent-based Deployments:**
- Agent not running → Start agent
- Agent not polling → Check agent logs
- Invalid agent key → Regenerate and update

**For Direct API:**
- Check cluster status in UI
- Test cluster connection
- View deployment logs for errors

### Cloud-init Errors

**Symptom:** Instance starts but configuration not applied

**Diagnosis:**
```bash
# SSH into instance
ssh ubuntu@instance-ip

# Check cloud-init status
sudo cloud-init status

# View logs
sudo cat /var/log/cloud-init.log
sudo cat /var/log/cloud-init-output.log
```

**Common Issues:**

**YAML Syntax Error:**
```yaml
# BAD - Missing colon
packages
  - vim

# GOOD
packages:
  - vim
```

**Invalid Package Names:**
```bash
# Check if package exists
apt-cache search package-name
```

**Script Errors:**
```bash
# Check runcmd output
sudo cat /var/log/cloud-init-output.log | grep -A 10 runcmd
```

### Instance Won't Start

**Symptom:** LXD instance created but won't start

**Diagnosis:**
```bash
# Check instance status
lxc list

# View instance logs
lxc info instance-name
lxc console instance-name --show-log
```

**Solutions:**

**Resource Limits:**
```bash
# Check available resources
lxc info

# Increase limits
lxc config set instance-name limits.cpu 2
lxc config set instance-name limits.memory 2GB
```

**Image Not Available:**
```bash
# List available images
lxc image list ubuntu:

# Download image
lxc image copy ubuntu:24.04 local: --alias ubuntu/24.04
```

### Deployment Timeout

**Symptom:** "Deployment timed out" error

**Causes:**
- Large image download
- Slow cloud-init execution
- Network issues

**Solutions:**
```bash
# Increase timeout (in .env)
DEPLOYMENT_TIMEOUT=1200  # 20 minutes

# Check network speed
speedtest-cli

# Pre-download images
lxc image copy ubuntu:24.04 local:
```

## Agent Issues

### Agent High CPU Usage

**Diagnosis:**
```bash
# Check CPU usage
top -p $(pgrep -f iceshelves-agent)

# Check poll interval
sudo systemctl show iceshelves-agent | grep POLL_INTERVAL
```

**Solution:**
```bash
# Increase poll interval
sudo systemctl edit iceshelves-agent
# Add: Environment=ICESHELVES_POLL_INTERVAL=600

sudo systemctl restart iceshelves-agent
```

### Agent Crashes

**Diagnosis:**
```bash
# Check logs for crash
sudo journalctl -u iceshelves-agent --since "1 hour ago" | grep -i error

# Check for Python errors
sudo journalctl -u iceshelves-agent | grep Traceback -A 20
```

**Solutions:**

**Missing Dependencies:**
```bash
sudo pip3 install --upgrade pylxd requests pyyaml
```

**LXD Access Issues:**
```bash
# Ensure agent runs as root
sudo systemctl edit iceshelves-agent
# Verify: User=root
```

### Agent Deploying Wrong Instances

**Symptom:** Agent deploying to wrong cluster

**Solution:**
```bash
# Verify cluster ID
sudo systemctl show iceshelves-agent | grep CLUSTER_ID

# Should match cluster ID in IceShelves
# Update if needed
sudo vim /etc/iceshelves/agent.env
sudo systemctl restart iceshelves-agent
```

## Performance Problems

### Slow Deployments

**Diagnosis:**
```bash
# Check deployment duration
curl http://localhost:8001/iceshelves/api/deployments | jq '.[] | {id, duration: (.completed_at - .started_at)}'
```

**Solutions:**

**Pre-cache Images:**
```bash
# On LXD host
lxc image copy ubuntu:24.04 local: --alias ubuntu/24.04
```

**Increase Resources:**
```bash
# More CPU for py4web
docker-compose up -d --scale iceshelves=2
```

**Database Optimization:**
```bash
# Add indexes
# Run VACUUM
docker-compose exec postgres psql -U postgres -d iceshelves -c "VACUUM ANALYZE;"
```

### Web UI Slow

**Diagnosis:**
```bash
# Check response time
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8001/iceshelves/

# curl-format.txt:
# time_total: %{time_total}
```

**Solutions:**

**Enable Redis Caching:**
```bash
# Verify Redis is running
docker-compose exec redis redis-cli ping

# Check cache configuration
grep CACHE .env
```

**Optimize Database Queries:**
```bash
# Check slow queries
docker-compose exec postgres psql -U postgres -d iceshelves \
  -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

## Database Issues

### Database Connection Failed

**Symptom:** "Could not connect to database"

**Solutions:**
```bash
# Check PostgreSQL is running
docker-compose exec postgres pg_isready

# Verify credentials
docker-compose exec postgres psql -U postgres -d iceshelves -c "SELECT 1;"

# Check connection string
echo $DATABASE_URL
```

### Database Disk Full

**Symptom:** "No space left on device"

**Solutions:**
```bash
# Check disk usage
df -h

# Clean old deployment logs
docker-compose exec postgres psql -U postgres -d iceshelves \
  -c "DELETE FROM deployment_logs WHERE timestamp < NOW() - INTERVAL '30 days';"

# Vacuum database
docker-compose exec postgres psql -U postgres -d iceshelves \
  -c "VACUUM FULL;"
```

### Database Migration Conflicts

**Symptom:** "Migration version mismatch"

**Solution:**
```bash
# Backup database first!
docker-compose exec postgres pg_dump -U postgres iceshelves > backup.sql

# Reset migrations
docker-compose down
docker volume rm project-template_postgres_data
docker-compose up -d
```

## Common Error Messages

### "License validation failed"

**Cause:** Invalid or expired license key

**Solution:**
```bash
# Check license key format
echo $LICENSE_KEY | grep -E '^PENG-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$'

# Test license server connectivity
curl https://license.penguintech.io/health

# Update license key
vim .env
docker-compose restart iceshelves
```

### "Egg not found"

**Cause:** Egg doesn't exist or is inactive

**Solution:**
```bash
# List all eggs
curl http://localhost:8001/iceshelves/api/eggs

# Check specific egg
curl http://localhost:8001/iceshelves/api/eggs/1

# Reactivate egg in database
docker-compose exec postgres psql -U postgres -d iceshelves \
  -c "UPDATE eggs SET is_active=true WHERE id=1;"
```

### "Instance name already exists"

**Cause:** Instance with same name exists

**Solution:**
```bash
# Check existing instances
lxc list

# Delete old instance
lxc delete old-instance --force

# Or use different name
```

## Debugging Tools

### Enable Debug Logging

**py4web Application:**
```bash
# Update .env
LOG_LEVEL=DEBUG

# Restart
docker-compose restart iceshelves

# View logs
docker-compose logs -f iceshelves
```

**Agent:**
```bash
# Edit service
sudo systemctl edit iceshelves-agent
# Add:
# Environment=ICESHELVES_LOG_LEVEL=DEBUG

sudo systemctl restart iceshelves-agent
sudo journalctl -u iceshelves-agent -f
```

### Test Deployment Manually

```bash
# Create test deployment
curl -X POST http://localhost:8001/iceshelves/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "egg_id": 1,
    "cluster_id": 1,
    "instance_name": "test-debug-instance"
  }'

# Watch logs
docker-compose logs -f iceshelves

# Check deployment status
curl http://localhost:8001/iceshelves/api/deployments/DEPLOYMENT_ID
```

### Database Query Tool

```bash
# Connect to database
docker-compose exec postgres psql -U postgres -d iceshelves

# Check eggs
SELECT id, name, is_active FROM eggs;

# Check deployments
SELECT id, instance_name, status FROM deployments ORDER BY created_on DESC LIMIT 10;

# Check clusters
SELECT id, name, connection_method, status FROM lxd_clusters;
```

## Getting Help

If issues persist:

1. **Check logs** - Most issues show in logs
2. **Test components individually** - Isolate the problem
3. **Review documentation** - Check relevant docs
4. **Search issues** - GitHub issues may have solutions
5. **Ask community** - Post in discussions
6. **Contact support** - support@penguintech.group

**When Requesting Support, Provide:**
- IceShelves version
- Deployment method (Docker, manual, etc.)
- Error messages and logs
- Steps to reproduce
- Environment details (OS, Python version, etc.)
