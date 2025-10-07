# IceShelves Architecture

## System Overview

IceShelves is a py4web-based platform for deploying standardized system configurations ("eggs") to LXD containers and KVM virtual machines. It supports three connection architectures to accommodate various network topologies and security requirements.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     IceShelves Server                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  py4web App  │  │  PostgreSQL  │  │    Redis     │     │
│  │              │──│   Database   │  │    Cache     │     │
│  │  - Web UI    │  │              │  │              │     │
│  │  - REST API  │  │  - Eggs      │  │  - Sessions  │     │
│  │  - Workers   │  │  - Clusters  │  │  - Queue     │     │
│  └──────┬───────┘  │  - Deploy    │  └──────────────┘     │
│         │          └──────────────┘                        │
└─────────┼───────────────────────────────────────────────────┘
          │
          │ Connection Methods (3 options)
          │
    ┌─────┴──────┬────────────────┬─────────────────┐
    │            │                │                 │
    ▼            ▼                ▼                 ▼
┌───────┐  ┌───────────┐  ┌──────────────┐  ┌──────────┐
│Direct │  │    SSH    │  │ Agent (Poll) │  │   KVM    │
│  API  │  │  Tunnel   │  │              │  │          │
└───┬───┘  └─────┬─────┘  └──────┬───────┘  └────┬─────┘
    │            │                │               │
    ▼            ▼                ▼               ▼
┌────────────────────────────────────────────────────────┐
│              LXD Clusters / KVM Hypervisors            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │Container │  │Container │  │    VM    │            │
│  └──────────┘  └──────────┘  └──────────┘            │
└────────────────────────────────────────────────────────┘
```

## Connection Architectures

### 1. Direct API (Clientless)

**Flow:**
```
IceShelves ──HTTPS──> LXD API (8443) ──> LXD Host ──> Container/VM
```

**Characteristics:**
- Immediate deployment (no polling delay)
- Requires network connectivity to LXD host
- Uses TLS certificate authentication
- Best for: Data centers, cloud environments

**Implementation:**
- Uses `pylxd` library for LXD API communication
- Certificate-based mutual TLS authentication
- Connection pooling for performance
- Automatic retry on transient failures

### 2. SSH Tunnel (Clientless)

**Flow:**
```
IceShelves ──SSH Tunnel──> LXD Unix Socket ──> Container/VM
```

**Characteristics:**
- Works through firewalls/NAT
- SSH key-based authentication
- Port forwarding to unix socket
- Best for: Restricted networks, bastion hosts

**Implementation:**
- SSH tunnel to LXD unix socket
- Uses paramiko or system SSH
- Falls back to LXD HTTPS over tunnel
- Automatic tunnel management

### 3. Polling Agent (Client-based)

**Flow:**
```
IceShelves <──Poll (1-5 min)── Agent ──> LXD Host ──> Container/VM
               (REST API)
```

**Characteristics:**
- Air-gapped environments supported
- No inbound connections required
- Service account authentication
- Best for: DMZs, isolated networks, strict security policies

**Implementation:**
- Agent: Python daemon (systemd service)
- Polls `/api/agent/poll/{cluster_id}` endpoint
- Bearer token (agent_key) authentication
- Stateless deployments (all data in API response)

## Component Architecture

### py4web Application Layer

```
apps/iceshelves/
├── controllers.py      # Routes, API endpoints
├── models.py          # Database schema (PyDAL)
├── common.py          # Business logic, utilities
├── settings.py        # Configuration
├── templates/         # HTML templates
└── libraries/eggs/    # Egg storage
```

### Database Schema

**Core Tables:**
- `eggs` - Deployment package definitions
- `lxd_clusters` - Connection configurations (all 3 methods)
- `deployments` - Deployment tracking and history
- `deployment_logs` - Structured deployment logs
- `egg_templates` - Skeleton templates for new eggs

**Relationships:**
```
eggs (1) ──< (N) deployments
lxd_clusters (1) ──< (N) deployments
deployments (1) ──< (N) deployment_logs
egg_templates (1) ──< (N) eggs (created_from)
```

### Egg Structure

```
eggs/{egg-name}/
├── cloud-init.yaml     # Cloud-init configuration
├── lxd-profile.yaml    # LXD profile (optional)
├── kvm-config.xml      # KVM config (optional)
├── metadata.json       # Egg metadata
└── README.md          # Documentation
```

## Data Flow

### Deployment Flow (Direct API)

1. **User Initiates Deployment**
   - Via Web UI or API
   - Selects: Egg, Cluster, Instance name

2. **Validation**
   - Validate egg exists and is active
   - Validate cluster is reachable
   - Check for name conflicts

3. **Preparation**
   - Load cloud-init from egg
   - Apply any config overrides
   - Create deployment record (status: pending)

4. **Execution**
   - Connect to LXD via pylxd
   - Create instance with cloud-init
   - Start instance
   - Update status (in_progress → completed)

5. **Logging**
   - Log all steps to deployment_logs
   - Update deployment metadata
   - Emit Prometheus metrics

### Agent Polling Flow

1. **Agent Polls Server**
   - Every 1-5 minutes (configurable)
   - `POST /api/agent/poll/{cluster_id}`
   - Bearer token authentication

2. **Server Returns Pending Deployments**
   - Query deployments with status=pending
   - For matching cluster_id
   - Include all egg files in response

3. **Agent Deploys Locally**
   - Creates LXD instance on local host
   - Applies cloud-init from response
   - No need to connect back to IceShelves

4. **Agent Reports Status**
   - `POST /api/agent/status/{deployment_id}`
   - Updates: status, instance_info, errors
   - Server updates database

## Security Architecture

### Authentication

**Web UI:**
- Session-based authentication
- CSRF protection
- Secure cookie flags

**API:**
- Bearer token for agent authentication
- Per-cluster agent keys
- API key rotation support

**LXD Connections:**
- TLS certificate mutual authentication
- SSH key-based for SSH method
- Certificate verification configurable

### Authorization

**Role-based Access:**
- Admin: Full access
- Operator: Deploy, view
- Viewer: Read-only

**Cluster Isolation:**
- Each cluster has unique credentials
- Agent keys are cluster-specific
- No cross-cluster access

### Data Protection

**Secrets Storage:**
- TLS certificates encrypted at rest
- SSH keys encrypted
- Agent keys hashed

**Network Security:**
- TLS 1.2 minimum (prefer TLS 1.3)
- Certificate pinning for LXD connections
- No plaintext credentials in logs

## Scalability

### Horizontal Scaling

**Application Servers:**
- Stateless py4web instances
- Session data in Redis
- Load balancer compatible

**Database:**
- PostgreSQL with connection pooling
- Read replicas for queries
- Write master for deployments

**Agents:**
- Each hypervisor runs own agent
- No inter-agent communication
- Scales linearly with hypervisors

### Performance Optimizations

**Caching:**
- Redis for session data
- LXD cluster metadata cached
- Image lists cached per cluster

**Async Processing:**
- Background deployment workers
- Queue-based job processing
- Non-blocking API responses

**Database Indexing:**
- Indexes on frequently queried fields
- Optimized queries for listing
- Pagination for large result sets

## Monitoring & Observability

### Health Checks

**Application:**
- `/healthz` - Overall health
- Database connectivity check
- LXD library availability check

**Clusters:**
- Periodic health checks
- Connection status tracking
- Agent last-seen timestamps

### Metrics (Prometheus)

**Counters:**
- `iceshelves_deployments_total{status,type}`
- `iceshelves_http_requests_total{method,endpoint}`

**Histograms:**
- `iceshelves_deployment_duration_seconds`
- `iceshelves_http_request_duration_seconds`

**Gauges:**
- `iceshelves_active_deployments`
- `iceshelves_cluster_count`
- `iceshelves_egg_count`

### Logging

**Structured Logging:**
- JSON format for parsing
- Correlation IDs for tracing
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

**Deployment Logs:**
- Per-deployment detailed logs
- Searchable in database
- Retention policy configurable

## High Availability

### Application HA

**Multi-instance:**
- Run multiple py4web instances
- Shared PostgreSQL database
- Shared Redis for sessions

**Load Balancing:**
- HTTP load balancer
- Health check integration
- Session affinity optional

### Database HA

**PostgreSQL:**
- Primary-replica replication
- Automatic failover (pgpool, patroni)
- Point-in-time recovery

**Redis:**
- Redis Sentinel for HA
- Or Redis Cluster
- Valkey compatible

### Agent Resilience

**Failure Handling:**
- Agent restart on failure (systemd)
- Deployment retry logic
- Graceful degradation

**Network Resilience:**
- Automatic reconnection
- Exponential backoff
- Timeout handling

## Future Enhancements

### Planned Features

1. **Multi-cluster Orchestration** (Enterprise)
   - Deploy across multiple clusters
   - Cluster affinity rules
   - Geographic distribution

2. **Advanced Templates**
   - Multi-container eggs
   - Dependency management
   - Post-deployment hooks

3. **Automated Scaling**
   - Auto-scale based on metrics
   - Load balancing across instances
   - Health-based scaling

4. **Compliance & Auditing**
   - SOC2 compliance reporting
   - Audit trail export
   - Change management integration

5. **CI/CD Integration**
   - GitHub Actions integration
   - GitLab CI support
   - Webhook triggers
