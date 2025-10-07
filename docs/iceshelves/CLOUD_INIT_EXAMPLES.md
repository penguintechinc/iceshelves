# Cloud-init Configuration Examples

Collection of cloud-init examples for IceShelves eggs.

## Basic Examples

### Minimal Configuration

```yaml
#cloud-config
hostname: minimal-host
timezone: UTC
locale: en_US.UTF-8

users:
  - name: ubuntu
    groups: sudo
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
```

### Package Installation

```yaml
#cloud-config
hostname: package-host

package_update: true
package_upgrade: true

packages:
  - vim
  - curl
  - wget
  - git
  - htop
  - build-essential
```

### User Management

```yaml
#cloud-config

users:
  - name: admin
    groups: sudo, docker
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    ssh_authorized_keys:
      - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC... admin@laptop

  - name: developer
    groups: sudo
    shell: /bin/bash
    ssh_authorized_keys:
      - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD... dev@workstation

# Disable SSH password authentication
ssh_pwauth: false
disable_root: true
```

## Web Server Examples

### Nginx

```yaml
#cloud-config
hostname: nginx-server

package_update: true
packages:
  - nginx
  - certbot
  - python3-certbot-nginx

write_files:
  - path: /var/www/html/index.html
    content: |
      <!DOCTYPE html>
      <html>
      <head><title>Welcome</title></head>
      <body>
        <h1>Server is running!</h1>
      </body>
      </html>
    permissions: '0644'

  - path: /etc/nginx/sites-available/default
    content: |
      server {
        listen 80 default_server;
        listen [::]:80 default_server;
        root /var/www/html;
        index index.html;
        server_name _;
        location / {
          try_files $uri $uri/ =404;
        }
      }
    permissions: '0644'

runcmd:
  - systemctl enable nginx
  - systemctl start nginx
  - ufw allow 'Nginx Full'
```

### Apache

```yaml
#cloud-config
hostname: apache-server

packages:
  - apache2
  - libapache2-mod-php
  - php

write_files:
  - path: /var/www/html/index.php
    content: |
      <?php
      phpinfo();
      ?>
    permissions: '0644'

runcmd:
  - a2enmod rewrite
  - a2enmod ssl
  - systemctl enable apache2
  - systemctl restart apache2
```

## Database Examples

### MySQL

```yaml
#cloud-config
hostname: mysql-server

packages:
  - mysql-server

write_files:
  - path: /root/mysql_secure.sh
    content: |
      #!/bin/bash
      mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'SecurePassword123!';"
      mysql -e "DELETE FROM mysql.user WHERE User='';"
      mysql -e "DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');"
      mysql -e "DROP DATABASE IF EXISTS test;"
      mysql -e "DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';"
      mysql -e "FLUSH PRIVILEGES;"
    permissions: '0700'

runcmd:
  - systemctl enable mysql
  - systemctl start mysql
  - bash /root/mysql_secure.sh
  - rm /root/mysql_secure.sh
```

### PostgreSQL

```yaml
#cloud-config
hostname: postgres-server

packages:
  - postgresql
  - postgresql-contrib

write_files:
  - path: /tmp/init_postgres.sh
    content: |
      #!/bin/bash
      sudo -u postgres psql -c "CREATE DATABASE myapp;"
      sudo -u postgres psql -c "CREATE USER myapp_user WITH PASSWORD 'SecurePassword123!';"
      sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE myapp TO myapp_user;"
    permissions: '0700'

runcmd:
  - systemctl enable postgresql
  - systemctl start postgresql
  - bash /tmp/init_postgres.sh
  - rm /tmp/init_postgres.sh
```

## Container Runtime Examples

### Docker

```yaml
#cloud-config
hostname: docker-host

packages:
  - apt-transport-https
  - ca-certificates
  - curl
  - gnupg
  - lsb-release

runcmd:
  # Add Docker's official GPG key
  - curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

  # Set up repository
  - echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

  # Install Docker Engine
  - apt-get update
  - apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  # Start Docker
  - systemctl enable docker
  - systemctl start docker

  # Add ubuntu user to docker group
  - usermod -aG docker ubuntu

write_files:
  - path: /etc/docker/daemon.json
    content: |
      {
        "log-driver": "json-file",
        "log-opts": {
          "max-size": "10m",
          "max-file": "3"
        },
        "storage-driver": "overlay2"
      }
    permissions: '0644'
```

### Kubernetes Node

```yaml
#cloud-config
hostname: k8s-node

packages:
  - apt-transport-https
  - ca-certificates
  - curl

runcmd:
  # Disable swap
  - swapoff -a
  - sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab

  # Load kernel modules
  - modprobe overlay
  - modprobe br_netfilter

  # Configure sysctl
  - |
    cat <<EOF | tee /etc/sysctl.d/k8s.conf
    net.bridge.bridge-nf-call-iptables  = 1
    net.bridge.bridge-nf-call-ip6tables = 1
    net.ipv4.ip_forward                 = 1
    EOF
  - sysctl --system

  # Install containerd
  - apt-get update
  - apt-get install -y containerd
  - mkdir -p /etc/containerd
  - containerd config default | tee /etc/containerd/config.toml
  - systemctl restart containerd

  # Add Kubernetes repository
  - curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.28/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
  - echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.28/deb/ /' | tee /etc/apt/sources.list.d/kubernetes.list

  # Install Kubernetes
  - apt-get update
  - apt-get install -y kubelet kubeadm kubectl
  - apt-mark hold kubelet kubeadm kubectl
```

## Advanced Examples

### Multiple Filesystems

```yaml
#cloud-config

write_files:
  - path: /etc/motd
    content: |
      Welcome to IceShelves deployed server!
    permissions: '0644'

  - path: /etc/profile.d/custom.sh
    content: |
      export PS1="\u@\h:\w\$ "
    permissions: '0755'

  - path: /root/.bashrc
    content: |
      alias ll='ls -la'
      alias update='apt-get update && apt-get upgrade -y'
    append: true
```

### Service Configuration

```yaml
#cloud-config

packages:
  - nginx

write_files:
  - path: /etc/systemd/system/my-app.service
    content: |
      [Unit]
      Description=My Application
      After=network.target

      [Service]
      Type=simple
      User=ubuntu
      WorkingDirectory=/opt/myapp
      ExecStart=/opt/myapp/start.sh
      Restart=always

      [Install]
      WantedBy=multi-user.target
    permissions: '0644'

runcmd:
  - systemctl daemon-reload
  - systemctl enable my-app
  - systemctl start my-app
```

### Conditional Commands

```yaml
#cloud-config

runcmd:
  - |
    if [ -f /etc/debian_version ]; then
      apt-get update
      apt-get install -y nginx
    elif [ -f /etc/redhat-release ]; then
      yum install -y nginx
    fi
```

### Variables and Templates (Jinja2)

When used as IceShelves egg template:

```yaml
#cloud-config
hostname: {{ hostname }}
timezone: {{ timezone | default('UTC') }}

users:
  - name: {{ username | default('ubuntu') }}
    groups: sudo
    shell: /bin/bash

packages:
{% for package in packages %}
  - {{ package }}
{% endfor %}

write_files:
  - path: /etc/app/config.json
    content: |
      {
        "environment": "{{ environment }}",
        "api_key": "{{ api_key }}",
        "debug": {{ debug | default('false') }}
      }
    permissions: '0600'
```

## Security Best Practices

### Secure SSH Configuration

```yaml
#cloud-config

# Disable password authentication
ssh_pwauth: false

# Disable root login
disable_root: true

# Only use SSH keys
users:
  - name: ubuntu
    ssh_authorized_keys:
      - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC...

write_files:
  - path: /etc/ssh/sshd_config.d/hardening.conf
    content: |
      PermitRootLogin no
      PasswordAuthentication no
      ChallengeResponseAuthentication no
      UsePAM yes
      X11Forwarding no
      PrintMotd no
      AcceptEnv LANG LC_*
      Subsystem sftp /usr/lib/openssh/sftp-server
    permissions: '0644'

runcmd:
  - systemctl restart sshd
```

### Firewall Configuration

```yaml
#cloud-config

packages:
  - ufw

runcmd:
  - ufw default deny incoming
  - ufw default allow outgoing
  - ufw allow ssh
  - ufw allow 80/tcp
  - ufw allow 443/tcp
  - ufw --force enable
```

### Automatic Updates

```yaml
#cloud-config

packages:
  - unattended-upgrades
  - update-notifier-common

write_files:
  - path: /etc/apt/apt.conf.d/50unattended-upgrades
    content: |
      Unattended-Upgrade::Allowed-Origins {
        "${distro_id}:${distro_codename}-security";
      };
      Unattended-Upgrade::AutoFixInterruptedDpkg "true";
      Unattended-Upgrade::Remove-Unused-Dependencies "true";
      Unattended-Upgrade::Automatic-Reboot "false";
    permissions: '0644'

runcmd:
  - systemctl enable unattended-upgrades
  - systemctl start unattended-upgrades
```

## Debugging Cloud-init

### Enable Debug Logging

```yaml
#cloud-config

output:
  all: '| tee -a /var/log/cloud-init-output.log'
```

### Check Cloud-init Status

After deployment, SSH into instance:

```bash
# Check cloud-init status
sudo cloud-init status

# View cloud-init logs
sudo cat /var/log/cloud-init.log
sudo cat /var/log/cloud-init-output.log

# Re-run cloud-init (for testing)
sudo cloud-init clean
sudo cloud-init init
```

## Best Practices

1. **Always validate YAML** before deploying
2. **Use version control** for cloud-init configs
3. **Test in development** before production
4. **Keep secrets separate** - use runtime injection
5. **Document variables** used in templates
6. **Follow security best practices** - no passwords, use SSH keys
7. **Use `final_message`** to confirm completion
8. **Include health checks** in runcmd
9. **Set proper file permissions** for write_files
10. **Use package_update** before package install
