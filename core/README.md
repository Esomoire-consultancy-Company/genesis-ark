# Core

The core module is the **platform control plane** for Genesis Ark. It is responsible for:

- Platform bootstrapping and lifecycle management
- Inter-module routing and message dispatch
- Health checks and readiness probes
- Configuration management

## Contents

| File / Folder | Description |
|---|---|
| `bootstrap/` | Platform startup and initialisation scripts |
| `router/` | Cross-module message routing logic |
| `config/` | Platform-wide configuration schemas |
| `health/` | Health and readiness probe endpoints |

## Bootstrap Sequence

```
1. Load platform config (config/)
2. Register all modules with the service registry (/registry)
3. Initialise telemetry pipeline (/telemetry)
4. Start governance policy engine (/governance)
5. Bring up application modules (/applications)
6. Emit platform-ready event to RiverOS
```

## Configuration

Platform configuration is loaded from environment variables and the `config/` directory. See `config/platform.yml` for defaults.
