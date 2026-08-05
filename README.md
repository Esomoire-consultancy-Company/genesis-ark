# genesis-ark
Root orchestration repository for the Virtual Silk Road and Genesis Stack ecosystem.

## Warden-Enabled Actor Box
- Canonical foundation and implementation boundary: `docs/actor-box/README.md`.
- Machine-readable control-object schema: `schemas/actor-box/v1/actor-box.schema.json`.
- Warden control-plane contract: `openapi/warden/v1/openapi.yaml`.
- Registry foundation DDL: `db/actor-box/v1/001_actor_box_foundation.sql`.
- Offline validation: `python scripts/validate_actor_box_contracts.py`.
- Runnable Warden evaluator: `services/warden/`.
- Warden tests: `cd services/warden && pytest`.

## Knowledge Hub Proxy Blueprint
- Reference architecture for an enterprise-wide “holy grail” knowledge hub proxy with Virtual Silk Road sub-arcs: `docs/knowledge-hub-proxy.md`.
- Example Helm values for deploying the proxy and its partner-facing slices: `docs/snippets/knowledge-hub-proxy.values.yaml`.
