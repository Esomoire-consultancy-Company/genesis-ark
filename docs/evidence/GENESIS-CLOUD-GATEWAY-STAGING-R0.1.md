# Genesis ARK Cloud Gateway R0.1 — Staging Acceptance Evidence

**Evidence ID:** GENESIS-GATEWAY-STAGING-ACCEPTANCE-R0.1  
**Date:** 2026-10-28 (UTC)  
**Environment:** Railway project `genesis-ark-gateway-staging`, environment `staging`  
**Scope:** staging only; no production cutover or merge authorization.

## Source, build and CI

- Repository: `Esomoire-consultancy-Company/genesis-ark`
- PR: #15 (draft, not merged at acceptance)
- Gateway deployed from commit: `4131e9cf3514ed60723dd1afc8ae86180675f8c3`
- Python: 3.12 (Railpack requirements installation)
- GitHub Actions **historical staging baseline**: Python 3.11/3.12 unit and PostgreSQL 18 contract checks passed at commit `d8955084859b6c655d595cc8e28165fa05927aa6`: https://github.com/Esomoire-consultancy-Company/genesis-ark/actions/runs/40643665360 . This does not cover unmerged PR #24 hardening; consult its separately recorded CI runs.
- An additional staging-only smoke runner exists in commit `6dcf44fc2307dd816d6301607e81d094d2abda80`, not required by the pinned HTTP gateway.

## Live Railway observations

| Component | Deployment ID | Verified result |
|---|---|---|
| PostgreSQL 18.6 | `c7f4fc5f-b585-46be-8fdd-ce9f00f9e5ec` | SUCCESS, 1/1 online, persistent 5 GB volume |
| One-shot DB migration | `a1527352-a833-4702-91a9-48370022ccac` | SUCCESS; `STAGING_EVIDENCE_MIGRATION_APPLIED` |
| Gateway HTTP service | `117dbebb-0c81-49ed-9cdd-a3a5168752ea` | SUCCESS; Uvicorn listening on port 8080; `GET /readyz` 200 after migration |
| Private-network smoke job | `1aead43f-190d-456a-bd41-db70d5331f39` | SUCCESS; `STAGING_SMOKE_PASS` |

The migration job and smoke job were temporary, had no volumes or public domains, and were removed from the staging project after verification. The PostgreSQL volume and gateway service remain.

## Verified denial-only smoke assertions

The smoke job used Railway private networking. It checked:
1. `GET /healthz` returns 200.
2. `GET /readyz` returns 200, `mode: deny-only`, `execution_enabled: false`.
3. An intent without a bearer credential returns 401.
4. An intent with an invalid bearer credential returns 401.
5. A provisioned staging-issuer intent returns 200 with `result: DENY`, `execution_invoked: false`, and a 64-character evidence hash.
6. Repeating an identical request ID and intent returns the same receipt (idempotent).
7. Reusing the request ID for a different capability returns 409.

A denial receipt was inserted in the staging database. No Docker adapter, arbitrary shell, settlement action, permit or external execution route was enabled.

## Security boundaries and limitations

- The runtime PostgreSQL connection uses a dedicated non-admin role. The migration utility grants schema USAGE, table SELECT/INSERT and sequence USAGE, not UPDATE/DELETE/DDL.
- The gateway readiness check rejects administrator/overprivileged database roles.
- The temporary migration identity used the PostgreSQL administrator DSN; that temporary Railway service was deleted after successful provisioning.
- **Credential rotation not independently evidenced:** deleting the temporary job does not revoke a PostgreSQL administrator password. Verify rotation and record a dated secret-lifecycle receipt before promotion.
- No public Railway domain was provisioned for the gateway.
- The hash-chain spool is **not** the independent, authoritative RiverOS ledger, and passing this smoke test is not federation or settlement certification.
- Backups, restoration drills, Warden policy engine integration, principal-specific SSO, rate limiting, credential rotation, privacy assessment and external evidence witnessing remain promotion gates.
- Production project `zoological-recreation` was outside this staging change scope.

## Outcome

**PASS — restricted, deny-only Gateway R0.1 staging acceptance** for the enumerated behaviors.  
**NOT APPROVED — production promotion, external publication, Warden PERMIT, execution adapters, Silk settlement or RiverOS attestation.**

This record identifies observed Railway deployment and CI outcomes; it is not itself a cryptographically signed RiverOS receipt.
