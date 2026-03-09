# Governance

The governance module implements **EmpireOS** — the licensing and governance layer for Genesis Ark.

EmpireOS controls:
- Platform licensing policies and enforcement
- Access control and role management
- Regulatory compliance frameworks
- Cross-module policy engine

## Contents

| File / Folder | Description |
|---|---|
| `policies/` | Policy definitions (OPA Rego or YAML) |
| `roles/` | Role and permission definitions |
| `licensing/` | License templates and enforcement rules |
| `compliance/` | Regulatory and audit frameworks |
| `votes/` | On-chain governance vote records |

## Policy Engine

Governance policies are evaluated at runtime against platform actions. Policies can be written in [OPA Rego](https://www.openpolicyagent.org/) and are hot-reloaded without downtime.

```
Action Request
     │
     ▼
Policy Engine (EmpireOS)
     │
     ├── ALLOW ──► Action proceeds + telemetry event emitted
     └── DENY  ──► Action blocked + audit log entry created
```

## Integration

- **Contracts** – on-chain enforcement for SILK and registry actions
- **Telemetry** – policy decisions streamed as events to RiverOS
- **Core** – bootstraps with governance engine on platform start
