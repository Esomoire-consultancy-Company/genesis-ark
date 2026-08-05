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
- Complete verification record: `VALIDATION.md`.

## Genesis Runtime Platform
- Capability-aware Runtime Manager: `services/runtime/`.
- Runtime authority and lifecycle contract: `docs/runtime-platform.md`.
- Runtime API contract: `openapi/runtime/v1/openapi.yaml`.
- Runtime object schema: `schemas/runtime/v1/runtime.schema.json`.
- Private-schema migration: `db/runtime/v1/004_genesis_runtime_platform.sql`.
- Runtime validation: `python scripts/validate_runtime_platform.py`.

## Validation
```bash
python scripts/validate_actor_box_contracts.py
python scripts/validate_cloudbrowser_contracts.py
python scripts/validate_authoritative_runtime.py
python scripts/validate_runtime_platform.py
PYTHONPATH=services/warden/src pytest -q services/warden/tests
PYTHONPATH=services/cloudbrowser/src:services/warden/src pytest -q services/cloudbrowser/tests
PYTHONPATH=services/runtime/src pytest -q services/runtime/tests
```

## Knowledge Hub Proxy Blueprint
- Reference architecture for an enterprise-wide knowledge hub proxy with Virtual Silk Road sub-arcs: `docs/knowledge-hub-proxy.md`.
- Example Helm values: `docs/snippets/knowledge-hub-proxy.values.yaml`.
