# Genesis CI + Synthetic Baseline R0.2 (review package)

Prepared from repository evidence available on 28 October 2026.
**This ZIP was tested locally but was NOT committed to GitHub:** the
repository write action required authorisation and was declined. An empty
feature branch `test/genesis-synthetic-baseline-r01` was created before that
blocker. Do not say the fixture is active in CI until a PR is opened and
its checks pass.

## Proposed GitHub changes (no root README overwrite)

- `synthetic-baseline/fixtures.json`: fictional actors, organizations,
  Commons membership, BNR representation, synthetic licences and action policy.
- `synthetic-baseline/engine.py`: deterministic ALLOW/ESCALATE/DENY oracle,
  no operational effects, fail-closed scope checks, SHA-256 receipts.
- `synthetic-baseline/scenarios.json`: 17 expected acceptance outcomes.
- `synthetic-baseline/verify.py`: one-command fixture acceptance check.
- `synthetic-baseline/test_baseline.py`: fixture/policy isolation tests.
- `synthetic-baseline/server.py`: loopback-only local test API.
- `synthetic-baseline/test_server.py`: HTTP and replay tests.
- `.github/workflows/genesis-synthetic-baseline.yml`: proposed read-only CI.
- `docs/CI_FAILURE_TRIAGE_R01.md`: diagnosis based on exact job logs.
- `tools/prepare_browser_retry.py`: OPTIONAL patch preparer for main-branch
  browser smoke transient timeouts. By default it only prints the proposed
  diff. `--apply` is a separate explicit local operation, with CI review.

## Local verification

Extract the ZIP into a checkout of `genesis-ark` **only on the review branch**.
The ZIP deliberately contains no root `README.md` and will not replace
the repository landing page. Then run:

```sh
python3 synthetic-baseline/verify.py
python3 -m unittest discover -s synthetic-baseline -p 'test_*.py' -v
python3 synthetic-baseline/server.py
```

No login, production keys, real user information, payment rail, actual node,
or live licences are used. The local server never binds a public interface.

## Integration / authority boundary

Do not connect this synthetic oracle to live membership, licence issuance,
Warden enforcement, a deployed Gateway, SILK settlement or a live supplier.
Do not merge or deploy without independent review.

## R0.2: interactive fixture workbench and consumer mapping

The package now includes a **localhost-only, visual synthetic test workbench**:
run `python3 synthetic-baseline/server.py` and open
`http://127.0.0.1:4178/` on the **same** machine. The interface lets an
operator pick fictional actors, review membership/representation/licence
fixtures and run all 17 deterministic policy scenarios, showing inert SHA-256
receipts. No real login, real organisations, settlement or execution is made.

- `synthetic-baseline/workbench/`: static HTML/CSS/JS interface, no CDN.
- `synthetic-baseline/fixture-lock.json`, `fixture_lock.py`: immutable fixture
  content hashes verified in the acceptance gate.
- `docs/SYNTHETIC_CONSUMER_MAPPING_R02.md`: precise consumer mapping boundary
  for the Genesis Alpha control plane and the Creators Door synthetic adapters.
- `tools/browser_workbench_qa.py`: optional browser visual and control check,
  using local intercepted synthetic responses, not a live endpoint.

The baseline now has **37 passing standard-library tests**, **17 passing
synthetic decision scenarios**, and an optional browser UI smoke across
320/390/1440 pixel widths with 17 scenario interactions per width.
The external GitHub branch is **not yet populated** with these files unless a
separate successful write and CI run is documented. A downloadable ZIP cannot
by itself prove GitHub CI or cross-repository integration.
