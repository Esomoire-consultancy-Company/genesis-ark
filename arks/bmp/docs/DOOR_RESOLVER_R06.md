# BMP Door Resolver R0.6 — signed admission and evidence prototype

**Implementation state:** executable, testable Node.js service; **NOT production integrated**. No DigitalMe, Warden or River live connectors, keys, server deployment, QR activation, property title or access authority are provided by this module.

## Principle
Client QR parameters such as `buyer=Dubai`, `disclosure=qualified`, `rights`, `river` or `role` are **never** authority or evidence. The client cannot select principal, Warden grant, River receipt, room authorization or monetary value. All commercial values remain **DEPICTION_ONLY**.

Runtime order: Identity → Authority → Reachability → Orchestration → Execution → Evidence. In this R0.6 vertical slice the trusted registry check is performed before identity resolution to reject non-admissible resources early, followed by actual principal assertion, Warden decision and River receipt verification. It does **not** perform provider orchestration/physical execution or legal conveyance.

## What is executable
- `service/resolver.mjs`: validates strict input, resolves verified server-owned resource, validates signed DigitalMe principal assertion and Warden allow decision using registered Ed25519 public keys; requires atomic one-time DigitalMe assertion nonce store; verifies signed River receipt bound by digest, correlation ID and Warden decision. No admission response is returned unless all gates succeed.
- `service/http.mjs`: safe minimal JSON POST `/v1/door/resolve`, `GET /healthz`, 4KiB max body, no CORS credential grants or verbose error details. Standalone mode binds `127.0.0.1:8786` and **always denies** because it has no real adapters.
- `service/registry.mjs`: A-1204 **DRAFT_UNVERIFIED**, `live_enabled=false`. It cannot be admitted even if a caller presents a signed principal. Test fixture asset `LAB-0001` is isolated inside the test process, not published as a production registry.
- `scripts/validate-door-runtime.mjs`: ephemeral test Ed25519 keys/issuer stubs (not production credentials) verify admitted lab-only scenario, expired/tampered identity, wrong Warden binding, decision escalation, replay, absent/invalid River receipt, unauthorized A-1204 and HTTP failures.

## Logical service invocation
```http
POST /v1/door/resolve HTTP/1.1
Content-Type: application/json
Authorization: Bearer <registered-DigitalMe-session-token>
```
```json
{"contract_version":"bmp.door-resolve.v0.1","asset_ref":"A-1204","door_ref":"VSR:BELGAUM:A-1204:DOOR","requested_state":"TODAY","anchor_ref":"FLOOR_01"}
```
**This request MUST be denied for A-1204 at this stage.** No unverified property can become public-admitted by URL or mock signing keys.

## Adapter obligations before live enablement
1. DigitalMe connector independently authenticates a session, issues a short-lived **Ed25519 signed assertion** with audience `bmp-door-resolver`; never treats arbitrary user principal claims as trusted.
2. Warden connector issues an Ed25519 signed binding of `principal_ref`, `resource_ref`, `action=door.enter`, permissible states, disclosure and expiry; keys are registered out-of-band.
3. River persists source event before issuing a cryptographically signed receipt whose `event_digest`, `correlation_id`, `decision_id` match the request. Merely generating a `river://` string does not qualify.
4. Registry requires verified asset identity, room/door mapping, lawful publication permission, policy review, and `VERIFIED_ACTIVE` status.
5. Deployment requires authenticated TLS termination, a durable distributed atomic nonce store, rate limits, key rotation/revocation, structured privacy-protecting audit logs, idempotency policy, alarms, abuse handling and real authorization tests. Memory-only test nonce storage is **never a production solution**.
6. Restore the canonical user-visible spatial route: Earth → Virtual Estate → Place → Location → Door → Room → Window/Stage → Activity. This resolver only admits a Door; it does not own utility equipment or physical keys.
7. Review HTTP POST acceptance, replay resistance, timing and confidentiality with security engineering before enabling a production reverse proxy.

## Local commands
```bash
node arks/bmp/scripts/validate-door-runtime.mjs
node arks/bmp/service/http.mjs
# standalone healthz: http://127.0.0.1:8786/healthz (503 because adapters unavailable)
```

**Do not configure live credentials, publish a real buyer QR, represent a stub as actual DigitalMe/Warden/River admission, or set A-1204 active in this PR.**
