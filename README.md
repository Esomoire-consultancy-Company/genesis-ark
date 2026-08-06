# genesis-ark

Root orchestration repository for the governed Genesis execution stack used by the Virtual Silk Road ecosystem.

## Authority boundary

The stack executes authority; it does not originate it.

```text
Anchor / owner / governing authority
→ BNR canonical registration
→ DigitalMe principal and representation
→ Warden capability, approval and revocation
→ Actor Box / CloudBrowser / Runtime / Edge execution
→ Genesis Control Tower operational projection
→ RiverOS evidence
→ SILK settlement where value moves
```

## Components

### Warden-Enabled Actor Box
- Foundation: `docs/actor-box/README.md`
- Schema: `schemas/actor-box/v1/actor-box.schema.json`
- API: `openapi/warden/v1/openapi.yaml`
- Migration: `db/actor-box/v1/001_actor_box_foundation.sql`
- Service: `services/warden/`

### Governed CloudBrowser
- Service: `services/cloudbrowser/`
- API: `openapi/cloudbrowser/v1/openapi.yaml`
- Schema: `schemas/cloudbrowser/v1/cloudbrowser.schema.json`
- Migration: `db/cloudbrowser/v1/002_cloud_browser_foundation.sql`

### Authoritative runtime hardening
- Migration: `db/authoritative/v1/003_authoritative_runtime_hardening.sql`
- Operating contract: `docs/authoritative-runtime.md`

### Genesis Runtime Platform
- Service: `services/runtime/`
- API: `openapi/runtime/v1/openapi.yaml`
- Schema: `schemas/runtime/v1/runtime.schema.json`
- Migration: `db/runtime/v1/004_genesis_runtime_platform.sql`
- Architecture: `docs/runtime-platform.md`

### Genesis Edge Node
- Service: `services/edge-node/`
- API: `openapi/edge-node/v1/openapi.yaml`
- Schema: `schemas/edge-node/v1/edge-node.schema.json`
- Migration: `db/edge-node/v1/005_genesis_edge_node.sql`
- Architecture: `docs/edge-node.md`

### Genesis Control Tower
- Service: `services/control-tower/`
- API: `openapi/control-tower/v1/openapi.yaml`
- Schema: `schemas/control-tower/v1/control-tower.schema.json`
- Migration: `db/control-tower/v1/006_genesis_control_tower.sql`
- Architecture: `docs/control-tower.md`

## Ordered migrations

```text
001 Actor Box foundation
002 CloudBrowser foundation
003 Authoritative runtime hardening
004 Genesis Runtime Platform
005 Genesis Edge Node
006 Genesis Control Tower
```

## Local verification

```bash
python scripts/validate_actor_box_contracts.py
python scripts/validate_cloudbrowser_contracts.py
python scripts/validate_authoritative_runtime.py
python scripts/validate_runtime_platform.py
python scripts/validate_edge_node_contracts.py
python scripts/validate_control_tower_contracts.py

PYTHONPATH=services/warden/src pytest -q services/warden/tests
PYTHONPATH=services/cloudbrowser/src:services/warden/src pytest -q services/cloudbrowser/tests
PYTHONPATH=services/runtime/src pytest -q services/runtime/tests
PYTHONPATH=services/edge-node/src pytest -q services/edge-node/tests
PYTHONPATH=services/control-tower/src pytest -q services/control-tower/tests
```

## Deployment boundary

The repository contains control-plane services, contracts, migrations and reference container images. It does not constitute a completed production deployment. Live database migration, secret provisioning, network policy, host supervisor integration, RiverOS relay deployment, observability, backup/restore and disaster-recovery validation must be completed in an isolated environment before production use.

## Additional architecture

- Knowledge Hub Proxy blueprint: `docs/knowledge-hub-proxy.md`
- Example Helm values: `docs/snippets/knowledge-hub-proxy.values.yaml`
