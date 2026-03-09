# Registry

The registry module implements the **Observable Commerce** phygitech asset registry for Genesis Ark.

It tracks physical-digital (phygitech) assets, service endpoints, Arc identities, email aliases, nodes, and licenses across the platform.

## Contents

| File / Folder | Description |
|---|---|
| `aliases/` | Holy Grail email alias mappings |
| `arcs/` | Arc identity registry entries (includes Bluesky/AT Protocol anchoring) |
| `assets/` | Phygitech asset definitions |
| `licenses/` | License definitions and enforcement records |
| `nodes/` | VSR network node registration records |
| `services/` | Service endpoint registrations |

## Arc Identity Format

Arc entries in `arcs/` tie a Genesis Ark identity to DNS and Bluesky (AT Protocol):

```yaml
arc_id: <arc-id>
tristar_key: <tristar-key>

identity:
  bluesky_handle: <handle>.bsky.social
  did: did:plc:<identifier>
  dns_anchor: <handle>.genesis.example

network:
  vsr_node: <node-id>
```

The `did` field anchors the Arc to the AT Protocol via a DNS TXT record:

```
_atproto.<dns_anchor>  TXT  "did=<did>"
```

## Email Alias Format

Email mappings in `aliases/email-mapping.yml` define the Holy Grail alias rewrite layer:

```yaml
mappings:
  - id: <mapping-id>
    generated: <generated-address>@<arc>.arcs.genesis.example
    alias: <friendly>@<node>.genesis.example
    display_name: "<Human-readable name>"
    target: http://gateway.genesis.example/ingest/email
    tristar_key: <tristar-key>
    status: active | suspended | deregistered
```

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
- `.github/workflows/email-mapping-sync.yml` – CI validation and gateway sync
