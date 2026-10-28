# GWIEP R0.4 — Independent identity verification, durable consent and private reads

**Status:** Alpha, source-and-test only. **HOLD: no deployment, live client, or production identity authority.** This is stacked on R0.3 draft PR #20 and R0.2 draft PR #18.

## What R0.4 adds

- Offline RS256 access-token verification with a locally pinned operator-trusted RSA public JWKS. Requires exact HTTPS issuer, one audience string, access token use, strict typ/alg/kid, valid signature, subject/tenant/station/source/session/jti, explicit scope, not-before/issued/expiry checks and maximum 15-minute token lifetime.
- Durable SQLite token and session revocation lookups, checked on each operation. The local token test generation code remains isolated to test fixtures; this verifier **does not** issue identity tokens.
- Tenant-scoped WardenConsentStore for authorized source registrations and explicit per-workstream consent, expiration and revocation. A separately verified work:admin actor provisions consent; cannot issue a grant to their own principal. The store resolves scope per request rather than trusting a caller-provided grant.
- DigitalMeWorkFabric.capture() checks the access token with work:capture, resolves the trusted consent/source, looks up the server-held source signing key, and invokes the existing R0.3 gateway with identity-derived claims. The R0.3 fixture session path remains available only as local test compatibility.
- DigitalMeWorkFabric.private_counts() requires independent work:read permission and queries only receipts indexed to the exact tenant+principal+work ID. It verifies the River chain and every selected receipt before producing metadata-only totals. No arbitrary payload export or cross-tenant enumeration.
- Cross-tenant source packet replay uses tenant+source+capture ID, rather than assuming that source names are globally unique.

## Unchanged boundaries

- No real DigitalMe identity provider or OIDC discovery is configured. The test issuer is fictitious, and fixture tokens are not credentials.
- The JWKS is provided out of band; no unauthenticated or dynamic remote public-key retrieval is allowed. A production identity provider requires trusted issuer configuration, key lifecycle, session revocation integration, nonce/PKCE if browser login is used, and operational availability controls.
- No HTTP server, customer onboarding, personal ChatGPT history read, voice recorder, Docker mutation, production deployment, sharing or merge.
- Signed source observation is not proof that ChatGPT exposed its keyboard or microphone origin; only future trusted capture clients can directly attest that origin.
- Work capture cannot create Warden verification, finalization or acceptance events. Counts of recorded tool calls are not proof of successful execution.
- R0.3 River JSONL and SQLite acceptance index are still not a single atomic database transaction. Concurrent direct journal writers are prohibited. A real deployment needs a transactional outbox/event stream, strict key rotation, robust backups, privacy assessment and independent hash anchoring.
- R0.4 administration uses a trusted IdentityContext object in a local library, not a remotely protected admin API. A deployed admin route must authenticate and verify the admin JWT itself, require a second-party authorization for sensitive changes, and issue audited grants with human approvals.
- Consent stored in SQLite represents Warden's local permission to record work, not an assertion of valid legal consent by itself. Before deployment, bind grants to evidence of user opt-in, purposes, retention, withdrawal, notice and policy version.
- Private work totals currently cover R0.3 indexed capture receipts only; historical R0.2 backfill is not included in authenticated read scope until an authorized import registration process is built.
- Avoid free-form identifiers in production, enforce bounded canonical IDs and prohibit sensitive personal information in source labels.

## Test gates

Run the control-plane test suite on Python 3.11 and 3.12:

    python -m pytest control-plane/tests -v -m "not docker_e2e"

Additional R0.4 tests target invalid issuer/audience/algorithm, expired/future tokens, scope denial, token and session revocation, unauthorized self-grant, revoked source/grant, missing evidence, invalid River chain and exact tenant/principal isolation.

## Next gates

1. Integrate a supported DigitalMe/OIDC provider in staging with approved issuer and pinned JWKS lifecycle. No production user auth is configured by this PR.
2. Convert administrative consent provisioning into Warden-authorized, human-signed workflows, including withdrawal evidence.
3. Provide separately authenticated, tenant-filtered review and reconciliation APIs, not just a Python library.
4. Replace the dual-store path with transactional durability and add multi-writer/chaos acceptance tests.
5. Add a consent-gated ChatGPT export importer only after the user supplies/approves the data source.
6. Review security, privacy and retention before enabling any service.
