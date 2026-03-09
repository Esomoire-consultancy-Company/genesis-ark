# Licenses

This directory contains EmpireOS license registry entries for Genesis Ark Arcs, nodes, and services.

Each license entry records the governance approval, scope, and expiry for a registered entity.

## Entry Format

```yaml
license_id: license-<id>
issued_to: <arc_id | node_id | service_id>
issued_by: did:genesis:<governance-authority>
scope:
  - <permission-1>
  - <permission-2>
issued_at: <ISO-8601>
expires_at: <ISO-8601>          # omit for perpetual licenses
status: active | suspended | revoked
```

## Integration

- Licenses are enforced by the EmpireOS policy engine in `/governance`.
- Revocations trigger an event emitted to RiverOS via `/telemetry`.
