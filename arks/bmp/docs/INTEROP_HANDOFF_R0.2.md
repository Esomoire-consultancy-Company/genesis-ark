# BMP ARK ↔ Genesis / Warden / Synnergyze / Quantum / River interoperability R0.2

**Status:** proposed contract; no live integration inferred. Source input: user-uploaded `bmp-ark-genesis-v0.1.zip` and `bmp-ark-genesis-v0.1(1).zip`, byte-identical (SHA-256 `c7ae9f558ad86aae013e92b215bca39475790d44bc3efb8468e02cd427abcf59`).

## AI-to-AI collaboration: repository-based handoff
Independent assistants cannot be presumed to share state or invoke one another. Coordinate through reviewable GitHub issues, immutable commit SHAs, versioned contracts and evidence pointers; an AI statement that something is "live" is not proof of deployment.

1. **Propose:** Contributor submits branch/PR, `source_ref`, `owner`, `intent_id`, `contracts_changed`, screenshots/media rights, endpoints, and an exact test command.
2. **Verify:** Reviewer checks file contents, contract compatibility, permission boundaries, runtime call logs, provider results and test report. Record `verified`, `simulated`, `unverified` separately.
3. **Admit:** Warden/governance reviewer accepts the proposed capability and controls; missing authority blocks only the affected action, not unrelated approved development.
4. **Implement:** Operator merges reviewed change, deploys via governed environment, captures commit SHA, environment, release and rollback reference.
5. **Evidence:** River stores authenticated execution/test receipts. Github comments or `river://`-looking URLs are not themselves River receipts.

For every AI-generated proposal preserve provenance and an explicit human/authorized-owner acceptance gate.

## Proposed service-call envelope

```json
{
  "contract_version": "vsr.execution-envelope.v0.1",
  "event_id": "evt-demo-001",
  "correlation_id": "intent-demo-001",
  "causation_id": null,
  "estate_ref": "UNVERIFIED_ESTATE",
  "asset_ref": "A-1204",
  "actor_ref": "ANONYMIZED_OR_REGISTERED_PRINCIPAL",
  "purpose": "request_flooring_option",
  "authority_ref": null,
  "idempotency_key": "demo-001",
  "source_status": "SIMULATED",
  "payload": { "anchor_ref": "FLOOR_01", "intent": "Can it be wood?" },
  "evidence_ref": null
}
```

Transport/authentication/retries/retention must be specified per provider; these are **not existing endpoint promises**.

| Handoff | Input contract | Response / gate |
|---|---|---|
| BMP → Door Resolver | Public deep-link hints or server-issued invite code | Resolve estate/asset/room eligibility |
| Door → DigitalMe | Principal proof with consent and purpose | Scoped identity reference |
| DigitalMe → Warden | Principal, estate, resource, action, policy version | Signed short-lived allow/deny decision |
| Warden → Genesis | Admitted capability lookup | Registered provider capability + version |
| Genesis → Synnergyze | Allowed intent and provider constraints | Workflow ID, provider candidates |
| Synnergyze → Provider | Authorized quote/service request | Supplier-issued quote or explicit not-ready |
| BMP → Quantum Room | Admitted participants, room, requested slot | Confirmed slot ID or not-booked |
| Services → River | Source event, issuer, digest, authority ref | Verified and retrievable receipt or rejection |
| Closing → DigitalMe | Verified legally operative owner/contract facts | Scoped entitlement grant, not property title creation |

Do not place identity documents, title deeds, payment instruments or private buyer details in public GitHub issues. Log PII only in approved data stores.

## State and error semantics

Supported states: `DRAFT`, `ADMISSION_PENDING`, `ADMITTED`, `PROVIDER_PENDING`, `QUOTE_PENDING`, `SESSION_PENDING`, `SESSION_CONFIRMED`, `EVIDENCE_PENDING`, `EVIDENCE_VERIFIED`, `CLOSED`, `REJECTED`. Represent `DENIED`, `EXPIRED`, `UNAVAILABLE`, `UNVERIFIED_SOURCE` explicitly; no silent success. Independent retries must be idempotent and correlated.

## Single source of truth
- **Code/specification:** versioned repository commit.
- **Physical-property truth:** authenticated operator/licensor records, not photos alone.
- **Authorization:** Warden policy and grants, not client query strings.
- **Supplier/commercial facts:** provider-native quotation + approval.
- **Schedule:** confirmed provider/session ID, not sample time.
- **Evidence:** River receipt verified against issuer and content.
- **Legal ownership:** legally operative external instruments, not DigitalMe UI.
