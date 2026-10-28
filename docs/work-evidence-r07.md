# GWIEP R0.7 — Synthetic Loopback Staging Acceptance

**Status: ALPHA TEST HARNESS ONLY.** R0.7 is stacked on R0.6 PR #25. It does **not** deploy an API or establish a connection to ChatGPT, Docker, Railway, or a real DigitalMe identity provider.

## What is exercised

R0.7 adds a narrowly constrained WSGI transport adapter (work_loopback.py) and synthetic HTTP tests (test_work_loopback_r07.py) on top of the existing R0.2-R0.6 code.

Tests bind an ephemeral port on **127.0.0.1 only**, generate in-test RSA keys, use synthetic identities and workstream IDs, and close the server after each test. No external network services are called.

The end-to-end scenario:

1. Fetch current R0.6 consent notice.
2. Deny capture before Warden registers a source.
3. Propose a grant by administrator A; refuse self approval; approve by different administrator B.
4. Deny capture without the member's own consent after administrator approval.
5. Require affirmative exact-version notice acceptance from the synthetic member.
6. Accept signed, source-observed voice-dictation + image metadata as PENDING, not River-recorded.
7. Confirm private pending=1, projected=0, recorded inputs=0.
8. Run separate local outbox drain, verify one hash-linked RiverOS projection and reconciliation.
9. Confirm projected=1 and accurate channel and attachment counts, while verified/finalized stay unknown.
10. Retry identical capture without double-counting.
11. Confirm other tenant receives no member data.
12. Withdraw consent, deny further capture and retain previously projected receipts subject to retention policy.
13. Deny hostile origins/cookies, invalid bearer tokens, oversized bodies, remote clients and unapproved routes.

## Transport boundaries

- This is a WSGI application library, NOT a server launcher. No deployment manifest, Docker port, Railway service, public URL or long-running process is created.
- The caller must bind loopback; REMOTE_ADDR and Host checks add defenses, but are not a substitute for a firewall and trusted ingress.
- Only GET/POST. POST requires explicit Content-Length <=16KiB and rejects Transfer-Encoding. The R0.6 API disallows cookies.
- HTTP is used only in ephemeral local tests. Real staging needs reviewed TLS, trusted proxy configuration, rate limits, network ACLs and secure token delivery.
- Synthetic signed JWTs are **not** genuine DigitalMe accounts or actual ChatGPT input provenance; the simulated client claims voice dictation.
- The test uses a single River consumer. Distributed exactly-once behavior, independent anchoring and backups remain unverified.
- Test success establishes a synthetic code path, NOT legal consent, operational authorization or deployed readiness.

## Commands

Focused (from repository root):

    python3 -m pytest control-plane/tests/test_work_loopback_r07.py -v

Full control-plane non-Docker regression:

    python3 -m pytest control-plane/tests -v -m "not docker_e2e"

GitHub Actions automatically runs the full suite on Python 3.11 and 3.12 for this PR.

## Gate matrix

| Gate | State |
| --- | --- |
| Synthetic identity, Warden, member consent, capture, River, reporting | Testable |
| Independent admin grant approvals | Synthetic-tested |
| Pending versus projected versus verified accounting | Testable |
| Private tenant-level summary | Synthetic-tested |
| Real DigitalMe issuer and credentials | NOT IMPLEMENTED |
| Hosted protected staging HTTPS ingress | NOT IMPLEMENTED |
| Trusted ChatGPT capture adapter / real history connection | NOT IMPLEMENTED |
| Legally reviewed notice, retention, deletion, subject rights | NOT APPROVED |
| Independent Warden signing/legal authority | NOT VERIFIED |
| Multiwriter/transactional River guarantees and external ledger anchoring | NOT VERIFIED |
| Authorized staging deployment | NOT GRANTED |
| Production | PROHIBITED |

Decision: **GO for offline synthetic engineering tests and review; NO-GO for hosting, live data or production.**
