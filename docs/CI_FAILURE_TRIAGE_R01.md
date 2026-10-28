# Genesis CI Failure Triage R0.1

Scope: review of the 28 October 2026 GitHub Actions alerts. This is a
**diagnostic classification**, not an assertion that every branch is healthy.
Check commit SHA, branch, job, run date and the latest relevant run; a red
historical notification remains red even after later fixes.

| Run / example | First actionable signal | Classification | What it does NOT show |
| --- | --- | --- | --- |
| genesis-ark `40667998565`, `main` | 320px Chrome smoke `TimeoutError('timed out')`; 390/768/1440 passed | CI browser transport instability | Does not indicate missing real users or licences |
| genesis-ark `40659229896`, physical preview | Test expected `physical infrastructure passports` literal not present in rendered page | Source/acceptance contract mismatch | No identity or licence check was involved |
| genesis-ark `40666515118`, GWIEP API | Two-admin grant test expected a regex match and failed | Test/security-contract mismatch | Not evidence of missing live users |
| creators-door `40668279495`, synthetic campaign | Synthetic campaign test expected a rejection that did not occur | Authorization test/implementation mismatch | Tests already use synthetic identity and entitlement adapters |

Later observed successful runs:

- Gateway PR #19 branch: `40664815896` / `40664826870`.
- Genesis public-site preview on `feat/genesis-digital-physical-r01`:
  `40659339711` / `40659333595`.
- GWIEP assurance on `fix/gateway-r01-assurance-20261028`:
  `40666503500` / `40666496930`.
- Creators Door latest run of both relevant checks:
  `40668445640` and `40668445545`.

Success of a *particular commit* does not imply all branches or the next
commit are green. At diagnosis time the Gateway `main` push failed at
`40667998565` after PR #19 was merged, so the main-branch reliability
problem needs a fresh, green main-branch run after an approved fix.

## Preferred failure taxonomy

1. `INFRA_TRANSIENT`: network/driver timeout with no assertion failure.
   At most one fresh browser-session retry; keep the first failure visible.
2. `CONTRACT_MISMATCH`: an asserted source/route/regex no longer matches a
   documented spec. Fix the implementation or adjust the spec only after
   review; do not change assertions merely to turn CI green.
3. `AUTHORITY_DENIED_EXPECTED`: a deliberate Warden denial under negative
   synthetic tests. This is a passing test if the expected outcome is DENY.
4. `AUTHORITY_BYPASS_BUG`: expected rejection was absent. This is a real
   failure; never retry as infrastructure and never allow promotion.
5. `FIXTURE_MISSING`: synthetic actor/membership/licence/representation
   absent or expired in the fixed test clock. Repair the shared fixture,
   then test negative cases as well.
6. `SERVICE_DEPENDENCY_UNAVAILABLE`: a declared external dependency absent.
   Integration tests should be separately gated; pure unit tests must run
   without a real connected service.

## Operational gate

- A PR needs its own green status at the **current head SHA**.
- The branch required for release must independently pass its **own** checks.
- Correlate duplicate push/PR events; avoid treating 2 notifications for one
  commit as 2 independent defects.
- Maintain a fixed fake clock, fictional actors and test entitlements.
- Tests may predict `ALLOW`, but actual tool execution must remain disabled
  in this fixture and any wider rehearsal until separately reviewed.
- Deny-by-default tests are first class: expired, revoked, wrong node,
  unregistered individual, wrong supplier and forged authority.
- Production and identity integration is a separate project and approval gate.
