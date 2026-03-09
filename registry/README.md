# Registry

The registry module implements the **Observable Commerce** phygitech asset registry for Genesis Ark.

It tracks physical-digital (phygitech) assets, service endpoints, and module metadata across the platform.

## Contents

| File / Folder | Description |
|---|---|
| `assets/` | Phygitech asset definitions |
| `services/` | Service endpoint registrations |
| `schemas/` | JSON schemas for registry entries |

## Registry Entry Format

```json
{
  "id": "asset-<uuid>",
  "type": "phygitech | service | module",
  "name": "Human-readable name",
  "owner": "did:genesis:<owner-id>",
  "metadata": {},
  "registered_at": "ISO-8601 timestamp",
  "status": "active | suspended | deregistered"
}
```

## Integration

The registry is consumed by:
- `/economics` – to verify commodity-backed asset provenance
- `/governance` – to enforce licensing policies on registered assets
- `/telemetry` – to emit asset lifecycle events to RiverOS
