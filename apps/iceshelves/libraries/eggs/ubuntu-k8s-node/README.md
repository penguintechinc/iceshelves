# Ubuntu Kubernetes Node

Kubernetes worker node ready to join an existing cluster.

## Features
- Kubernetes v1.28 components (kubelet, kubeadm, kubectl)
- containerd runtime
- Proper kernel configuration for Kubernetes
- Swap disabled
- Ready to join cluster

## Post-Deployment
```bash
# On master, get join command
kubeadm token create --print-join-command

# On this node, run the join command
sudo kubeadm join [master-ip]:6443 --token [token] --discovery-token-ca-cert-hash [hash]
```

## Version
1.0.0 - Kubernetes v1.28
