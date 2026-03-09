# DevKits

The devkits module provides **SDKs and extension kits** that allow independent repositories to integrate with the Genesis Ark platform without forking this repository.

## Contents

| File / Folder | Description |
|---|---|
| `sdk-core/` | Core SDK for platform API access |
| `sdk-telemetry/` | RiverOS telemetry emission helpers |
| `sdk-contracts/` | Contract interaction utilities |
| `contract-tools/` | Deployment and management CLI for contracts |
| `templates/` | Starter templates for new integrations |

## Extension Model

External repositories integrate with Genesis Ark by:

1. Importing the relevant SDK from `devkits/`.
2. Registering their service in the platform registry (`/registry`).
3. Declaring governance policies (`/governance/policies`).
4. Emitting lifecycle events via the telemetry SDK.

```
External Repository
       │
       ├── imports devkits/sdk-core/
       ├── imports devkits/sdk-telemetry/
       └── registers via /registry API
```

## SDK Languages

| Language | SDK | Status |
|---|---|---|
| Python | `sdk-core/python/` | Planned |
| TypeScript | `sdk-core/typescript/` | Planned |
| Go | `sdk-core/go/` | Planned |

Contributions to SDKs are welcome. See [`docs/CONTRIBUTING.md`](../docs/CONTRIBUTING.md).
