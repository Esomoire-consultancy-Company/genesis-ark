# Genesis Ark

> Root orchestration repository for the Virtual Silk Road and Genesis Stack ecosystem.

Genesis Ark is the modular platform control plane that orchestrates the **Virtual Silk Road** infrastructure. It integrates independent sub-systems into a unified, telemetry-driven, commodity-backed platform.

---

## Integrated Systems

| System | Role |
|---|---|
| **RiverOS** | Telemetry and observability |
| **EmpireOS** | Licensing and governance |
| **SynergizeOS** | Operational planning |
| **SILK** | Commodity-backed token economy |
| **Observable Commerce** | Phygitech asset registry |

---

## Repository Structure

```
genesis-ark/
├── architecture/      # System design, diagrams, and integration maps
├── registry/          # Service registry and phygitech asset registry
├── core/              # Platform control plane — bootstrap, routing, lifecycle
├── economics/         # SILK token economy, commodity backing, treasury logic
├── telemetry/         # RiverOS telemetry pipelines and observability stack
├── contracts/         # Smart contracts for governance, licensing, and tokens
├── infrastructure/    # Container, Kubernetes, and cloud deployment manifests
├── applications/      # Platform applications and workflow modules
├── governance/        # EmpireOS licensing, policy engine, and compliance
├── devkits/           # SDKs and extension kits for independent repositories
└── docs/              # Platform-level documentation and guides
```

---

## Quick Start

### Prerequisites

- Docker ≥ 24.x and Docker Compose ≥ 2.x
- `make` (GNU Make)

### Run locally

```bash
git clone https://github.com/Esomoire-consultancy-Company/genesis-ark.git
cd genesis-ark
make up
```

This starts the core platform services defined in `docker-compose.yml`.

### Useful make targets

| Target | Description |
|---|---|
| `make up` | Start all platform services |
| `make down` | Stop all platform services |
| `make status` | Show running service status |
| `make lint` | Lint configuration files |
| `make docs` | Render documentation locally |

---

## Architecture Overview

See [`architecture/README.md`](architecture/README.md) for detailed system design and integration maps.

---

## Contributing

Contributions are welcome. Please read [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) before opening a pull request.

---

## License

Licensed under the [Apache License 2.0](LICENSE).
