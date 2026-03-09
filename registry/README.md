# Registry

The registry module is the source-of-truth for all Genesis Ark identities, assets, and communication mappings.

It tracks physical-digital (phygitech) assets, service endpoints, Arc identities, email aliases, nodes, and licenses across the platform.

## Structure

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

## Identity Stack

```
Tristar Key
      │
      ▼
Genesis Ark Registry (registry/arcs/)
      │
      ▼
DNS Layer (_atproto TXT record)
      │
      ▼
AT Protocol Identity (Bluesky DID)
      │
      ▼
Virtual Silk Road Network
```

## Arc Entry Format

See `schemas/arc.yml` for the full schema.

```yaml
arc_id: <arc-id>
tristar_key: <namespace>:<arc-id>:<environment>
identity:
  bluesky_handle: <handle>.bsky.social
  did: did:plc:<identifier>
  dns_anchor: <domain>
network:
  vsr_node: <node-id>
status: active
```

## Email Alias Format

See `schemas/email-mapping.yml` for the full schema.

```yaml
mappings:
  - id: <mapping-id>
    generated: <system-address>@<arc>.arcs.genesis.example
    alias: <human-alias>@<domain>
    display_name: "Human-readable name"
    target: http://gateway.genesis.example/ingest/email
    tristar_key: <namespace>:<arc-id>:<environment>
    status: active
```

## Integration

The registry is consumed by:
- `/economics` – to verify commodity-backed asset provenance
- `/governance` – to enforce licensing policies on registered assets
- `/telemetry` – to emit asset lifecycle events to RiverOS
- `.github/workflows/email-mapping-sync.yml` – CI validation and gateway sync
