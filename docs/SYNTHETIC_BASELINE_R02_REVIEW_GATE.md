# Genesis Synthetic Baseline R0.2 — Complete local review package

**Status:** synthetic-only, draft-PR review. Source-controlled package import is not production authority.

## Imported scope

This branch now imports the full locally tested 22-file R0.2 **source** package, including:

- 10 fictional DigitalMe-style actors, Commons memberships, BNR representations, supplier-scoped *synthetic* licences, and 17 expected policy decision scenarios;
- deterministic, fail-closed oracle, SHA-256 fixture locks, idempotence/replay tests and synthetic receipt digests (not live RiverOS records);
- localhost-only HTTP simulator and browser workbench;
- 37 unit and local HTTP contract tests;
- GitHub Actions verification using pinned actions and read-only checkout;
- consumer mappings, risk and failure-triage documentation, optional browser QA and browser CI timeout review tooling.

The original R0.2 review ZIP also includes two optional PNG screenshots under `qa/`. They are **not** imported into GitHub: all 22 text sources are imported, with screenshots remaining supplemental and reproducible using the optional browser QA script.

## CI acceptance

```sh
python3 synthetic-baseline/verify.py
python3 -m unittest discover -s synthetic-baseline -p 'test_*.py' -v
node --check synthetic-baseline/workbench/workbench.js
```

CI verifies the actual branch source, not a stale success from another commit. The fixture lock must match the exact imported fixture JSON files. Local preflight of this package passed 17 scenario cases and 37 tests; GitHub acceptance must pass on the new head before release.

## Security boundaries

The local server binds only to `127.0.0.1`; it is not a production or public web service. All actors, memberships, licences, representations and decisions are fictional. An `ALLOW` receipt has `synthetic: true`, `executable: false` and cannot become a real Warden permit, payment, official licence, GitHub write entitlement, production deployment or authority to represent a legal entity.

## Not yet integrated

This review imports the reference baseline, **not** cross-repository consumer adoption. Creators Door, Genesis Control Plane and other modules must explicitly map the contract into separate, bounded, synthetic-only adapters with their own independently green tests. The browser-test timeout repair script is provided as a review-before-apply tool; this PR does not patch the live Gateway smoke test or add an automatic policy retry.

**Promotion gate:** Exact-head CI + human review required before merge. No production effects or public deployment are permitted in this PR.
