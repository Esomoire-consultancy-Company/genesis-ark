# Genesis Work Intelligence & Evidence Protocol — R0.6 Staging API and Consent UI

**Status: source/tests ONLY. No live API service, deployment, ChatGPT connection or DigitalMe identity provider.** Stacked on R0.5 draft PR #23, R0.4 PR #21, R0.3 PR #20, and R0.2 PR #18.

## New controls

### Source-only, in-process API contract
The work_api.py module accepts an ApiRequest(method,path,headers,body) and returns an ApiResponse. It never binds to a network socket, registers an HTTP server, or accepts cookies. The caller supplies verified transport security, TLS, a supported bearer credential, trusted key configuration and reverse-proxy protection before this can ever be exposed. 16 KiB JSON size cap, duplicate JSON key rejection, exact body allowlist, same-origin policy, disabled cookie auth, no-store/cache/referrer/CSP response headers, no secrets in error results.

Routes:
- GET /v1/work/notice — public static versioned purpose/notice (no data).
- POST /v1/work/consent — member opt-in with version, expiry and explicit affirmative choice.
- POST /v1/work/withdraw — member-initiated prospective withdrawal.
- POST /v1/work/capture — authorized signed capture into R0.5 pending outbox; no immediate River projection.
- GET /v1/work/{work_id}/progress — tenant/principal/work-scoped counts of pending, blocked, projected.
- POST /v1/admin/reviews — authenticated admin proposes narrowly scoped source/work grant.
- POST /v1/admin/reviews/{proposal_id}/approve — independent second administrator with work:approve and work:admin permissions approves.
- GET /v1/admin/reviews/{proposal_id} — tenant-scoped status; no cross-tenant enumeration.
No public drain, unrestricted River read, arbitrary admin grant, JSONL write, production Docker control, tool execution, or verification/finalization route exists.

### Member consent interface
control-plane/ui/work-evidence.html is an unhosted review asset, disabled by default. It requires an approved HTTPS authentication shell to supply short-lived access tokens through an in-memory GenesisAuth interface. The page does not store access tokens, connect to ChatGPT, or generate any telemetry by itself. It displays the current notice, requires an explicit checkbox, and supports workstream-specific opt-in, withdrawal and private counts **only** if that secure backend is configured. Do not host publicly until security review.

### Consent evidence
work_notice.py binds the exact notice version/hash, authenticated subject token ID hash, named workstream and chosen expiry to subject consent. The member's notice acknowledgment, subject consent and audit receipt are committed atomically in one local SQLite transaction. The implementation is a technical receipt, not a legal opinion on notice sufficiency.

### Administrative grant assurance
work_review.py creates a pending, timestamped grant proposal. A second administrator must hold both work:admin and work:approve, belong to the correct tenant and station, and differ from both the proposer and the target beneficiary. Only then are R0.4 source/grant records materialized. Approvals are one-shot and proposal states persist (pending/applying/approved). A crashed applying proposal fails closed, requiring explicit reconciliation, not automatic approval.

Important: the legacy R0.4 store permits direct administrator grants for offline testing; real deployment must expose only the R0.6 protected review path. The cross-database final grant application and proposal status are not atomic. The applying state flags uncertainty; before release, introduce a single transactional ledger or an explicit recoverable outbox, plus auditable review signatures, anti-self-provisioning, policy version and administrator revocation.

## Evaluable evidence states
Submitted != Accepted; Pending != Projected; Projected != Verified; Approved != Executed; Finalized requires actual evidence and separate human review. The UI reports source and state, never guessed keyboard-versus-speech history. For historic ChatGPT exports, source remains unknown unless the export reliably proves otherwise. LBM and OCM remain persistent lifecycle duties.

## Security and release gates — must remain HOLD
- Real DigitalMe/OIDC issuer integration with issuer/audience/key rotation, revocation, token delivery and independent session security review.
- Trusted HTTPS ingress, origin/header normalization, CSRF and CORS enforcement, request quotas, WAF/rate limits, structured audits and transport-layer tests.
- Independent, two-human Warden approvals with evidenced identities and delegated authority; approval audit must be independently anchored.
- Consent notice review for lawful basis, purpose, retention, withdrawal, subject rights and jurisdictional policy.
- Transactional consistency of admin proposal and grant writes, and River outbox projection under crash and multi-worker conditions; independent hash checkpoints and backups.
- Hard disablement of any production ChatGPT history reading/voice capture until consent and source adapter approval.
- Tenant isolation, sensitive identifier validation, redaction, encryption and retention review; no full prompt/transcript/file payload in the River metadata ledger.
- Review real-world runtime identity and infrastructure rather than treating synthetic CI success as production authority.
- No merge, deployment, permission change or external connection from this R0.6 draft.

## Tests

Python 3.11 and 3.12 test matrix via .github/workflows/ges-alpha-control-plane.yml. Local:

    python -m pytest control-plane/tests -v -m "not docker_e2e"

New tests: work_api_r06, covering notice acceptance, no implicit consent, two-administrator grant, scope/tenant isolation, input capture, work progress, origin and cookie denial, JSON duplicate key, tampered tokens, and safe errors.
