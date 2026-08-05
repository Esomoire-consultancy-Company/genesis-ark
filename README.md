# genesis-ark
Root orchestration repository for the Virtual Silk Road and Genesis Stack ecosystem.

## Warden-Enabled Actor Box
- Canonical foundation and implementation boundary: `docs/actor-box/README.md`.
- Machine-readable control-object schema: `schemas/actor-box/v1/actor-box.schema.json`.
- Warden control-plane contract: `openapi/warden/v1/openapi.yaml`.
- Registry foundation DDL: `db/actor-box/v1/001_actor_box_foundation.sql`.
- Runnable Warden evaluator: `services/warden/`.

## Governed CloudBrowser
- Governed broker and Chromium runtime: `services/cloudbrowser/`.
- CloudBrowser API contract: `openapi/cloudbrowser/v1/openapi.yaml`.
- CloudBrowser registry migration: `db/cloudbrowser/v1/002_cloud_browser_foundation.sql`.

## Authoritative Runtime
- PostgreSQL/Supabase hardening migration: `db/authoritative/v1/003_authoritative_runtime_hardening.sql`.
- Operating and deployment contract: `docs/authoritative-runtime.md`.
- Runtime validation: `python scripts/validate_authoritative_runtime.py`.

## Genesis Runtime Platform
- Capability-aware Runtime Manager: `services/runtime/`.
- Runtime API contract: `openapi/runtime/v1/openapi.yaml`.
- Runtime object schema: `schemas/runtime/v1/runtime.schema.json`.
- Private runtime migration: `db/runtime/v1/004_genesis_runtime_platform.sql`.
- Architecture contract: `docs/runtime-platform.md`.

## Genesis Edge Node
- Secure Edge Node controller and host-agent primitives: `services/edge-node/`.
- Edge Node API contract: `openapi/edge-node/v1/openapi.yaml`.
- Edge Node object schema: `schemas/edge-node/v1/edge-node.schema.json`.
- Enrollment, heartbeat, command and evidence migration: `db/edge-node/v1/005_genesis_edge_node.sql`.
- Architecture contract: `docs/edge-node.md`.

## Genesis Control Tower
- Governed fleet operations and dashboards: `services/control-tower/`.
- Control Tower API contract: `openapi/control-tower/v1/openapi.yaml`.
- Control Tower JSON Schema: `schemas/control-tower/v1/control-tower.schema.json`.
- Control Tower migration: `db/control-tower/v1/006_genesis_control_tower.sql`.
- Authority and operating contract: `docs/control-tower.md`.

## Ordered migrations

```text
001 Actor Box foundation
002 CloudBrowser foundation
003 Authoritative runtime hardening
004 Genesis Runtime Platform
005 Genesis Edge Node
006 Genesis Control Tower
```

## Validation
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

## Knowledge Hub Proxy Blueprint
- Reference architecture for an enterprise-wide knowledge hub proxy with Virtual Silk Road sub-arcs: `docs/knowledge-hub-proxy.md`.
- Example Helm values: `docs/snippets/knowledge-hub-proxy.values.yaml`.
