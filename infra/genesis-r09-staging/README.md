# Genesis R0.9 — read-only federation staging candidate

**Not an independent-host R0.8 federation; not a signed R0.9 mTLS attestor.** Four role-specific services are designed for the pre-existing `estate-r05-assurance/sandbox` Railway environment. Each role is a synthetic-only health/status endpoint and holds no Warden authority.

Mandatory environment settings (per service):
- `GENESIS_ROLE`: one of `authority`, `gateway`, `receiver`, `auditor_witness`.
- `GENESIS_R08_RELEASE_SHA256`: `c900b18b4f431394314600918a0ab9669ef22994869dc92790e0ef4dfa958795`.
- `GENESIS_SYNTHETIC_ONLY=true`.
- `GENESIS_BUSINESS_MUTATIONS_ENABLED=false`.
- `GENESIS_PRODUCTION_AUTHORITY=HOLD`.

The process intentionally refuses to start without these flags. It exposes only GET /healthz and GET /status. POST /attest and all business, policy and financial requests are blocked. No public domains should be created. Four services under one Railway workspace do not qualify as independent physical hosts, administrative domains, trust roots or operator accounts.

Use Railway build root `/infra/genesis-r09-staging` and healthcheck `/healthz` after staging approval. The Docker base must be pinned to a validated image digest before first deployment; the current unpinned builder image is a review blocker, not an attested release image.

Release gates: security/operations approval, distinct trust roots and separately controlled signing keys, signed deployment receipts, actual cross-host policy epoch + receiver acknowledgement and terminal fence drills, independent RiverOS witness, partition/restart and restore verification. Until then all execution remains HOLD.
