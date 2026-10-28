# Genesis Synthetic Baseline R0.2 — Local Evidence Receipt

**Scope:** a locally executed, fictional, non-executable test baseline.
**Date:** 2026-10-28.
**Environment:** Python 3, localhost HTTP contract suite, local Chromium via Playwright with synthetic responses explicitly intercepted.
**Repository state:** package produced in working container. No statement of CI or live deployment success is made.

## Verification results

| Check | Command / evidence | Outcome |
| --- | --- | --- |
| Permission scenarios | `python3 synthetic-baseline/verify.py` | 17 expected ALLOW/ESCALATE/DENY results; `effects == 0` |
| Fixture and simulator HTTP contracts | `python3 -m unittest discover -s synthetic-baseline -p 'test_*.py' -q` | 37 tests pass |
| JS parser | `node --check synthetic-baseline/workbench/workbench.js` | Pass |
| Optional UI interaction smoke | `python3 tools/browser_workbench_qa.py` | 17 scenario interactions each at 320, 390 and 1440; no horizontal overflow or JS errors |
| Localhost HTTP routing | `test_server.py` server bound to 127.0.0.1 | Pass; real identity/licence/settlement routes absent |
| Provenance | `synthetic-baseline/fixture-lock.json` | Pinned SHA-256 digests of actor and scenario fixtures |

The optional browser QA uses a browser navigation-free `about:blank` rendering with local CSS/JS and **intercepted** synthetic API responses, because the evaluation environment blocks arbitrary browser network navigation. The Python HTTP test suite separately exercises the live loopback simulator. This is not end-to-end browser-over-HTTP deployment acceptance; that still needs CI or an authorised staging environment.

## Fault-specific diagnosis from GitHub Actions

1. Main-branch Genesis Gateway run `40667998565` timed out at the 320px browser smoke. 390px, 768px and 1440px passed; no user account or licence validation was involved.
2. A historic public-site run `40659229896` reported a literal copy/contract mismatch for a physical infrastructure page, not missing real actors.
3. The historic creators-door run `40668279495` reported an expected synthetic rejection that did not occur. This is an **authorization test failure** and is not safely retried as transient infrastructure. Later branch checks passed.
4. An older GWIEP admin-grant run `40666515118` failed its two-independent-admin assertion. This is a contract/security invariant concern, not a request to issue real admin licences.

## Promotion gates

- A test ALLOW result is not production permission and is never executable.
- Each consumer must pin the fixture digest and independently verify negative cases.
- GitHub CI must run on the **exact** proposed branch head after files are uploaded, not rely on locally produced green results.
- The Gateway main-branch browser timeout requires separate source-controlled, bounded transport-only retry and a fresh main-branch result after approval.
- No existing PR is merged and no production or live identity integration is authorised by this package.
