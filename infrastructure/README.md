# Infrastructure

The infrastructure module contains all deployment manifests and configuration for running Genesis Ark on container and cloud infrastructure.

It supports:
- **Docker Compose** – local development and single-node deployments
- **Kubernetes** – production-grade multi-node deployments
- **Terraform** – cloud resource provisioning (optional)

## Contents

| File / Folder | Description |
|---|---|
| `k8s/` | Kubernetes manifests (Deployments, Services, ConfigMaps) |
| `helm/` | Helm charts for platform modules |
| `terraform/` | Terraform modules for cloud provisioning |
| `scripts/` | Infrastructure automation scripts |

## Kubernetes Deployment

```bash
kubectl apply -f infrastructure/k8s/namespace.yml
kubectl apply -f infrastructure/k8s/
```

## Helm Deployment

```bash
helm install genesis-ark infrastructure/helm/genesis-ark/
```

## Environment Targets

| Environment | Method |
|---|---|
| Local development | `docker-compose.yml` (repo root) |
| Staging | Kubernetes + Helm |
| Production | Kubernetes + Helm + Terraform |
