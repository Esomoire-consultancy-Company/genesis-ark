# GES Alpha Control Plane R0.1 Verification Record

## Scope

This record covers the source implementation on branch `codex/ges-alpha-control-plane-r01` for the Alpha-only Warden → capability token → WEG → bounded Docker adapter → verification → River evidence path.

## Authority boundary

- Estate: `GENESIS-ESTATE-001`
- Node: `ALPHA-NODE-001`
- Station: `GES-ALPHA-001`
- Adapter: `GEN-ADAPTER-DOCKER-001`
- First governed mutation: `container.instance.restart`
- Policy: `WARDEN-ENGINEERING-R0.1`

## Local executable verification

The implementation was exercised in an isolated local scratch workspace using Python 3.13.5 and pytest 9.0.2.

Unit command:

```bash
cd control-plane
python -m pytest -v -m "not docker_e2e"
```

Final local result: 44 passed, 4 Docker tests deselected, zero failures.

Covered negative conditions include:

- expired or malformed command envelopes denied by Warden;
- command authorization never outlives the command envelope;
- unknown target denied by Warden;
- unknown capability denied by Warden;
- production environment denied;
- wrong station denied;
- high-risk request denied;
- token payload tampering rejected;
- token expiry rejected;
- wrong token audience rejected;
- DENY decision cannot mint a token;
- replayed token rejected;
- wrong target/adapter/parameters/station/session/principal rejected at WEG;
- stale registry binding rejected;
- unsupported Docker capability never reaches the runner;
- Docker timeout outside 1..300 rejected;
- unhealthy read-back cannot become `VERIFIED`;
- CLI success requires a `VERIFIED` outcome, not merely Warden `PERMIT`;
- River evidence tampering invalidates the hash chain;
- denied production command produces zero Docker calls.

## Docker acceptance state

A disposable resource `RES-GES-TEST-CONTAINER-001` maps to Docker name `ges-alpha-test` only for the real-engine acceptance suite.

The current execution environment did not expose a Docker engine. The acceptance module therefore produced:

- registry fixture validation: PASS;
- real authorized Docker restart: SKIPPED — Docker unavailable;
- token replay real-engine path: SKIPPED — Docker unavailable;
- parameter-tamper real-engine path: SKIPPED — Docker unavailable.

No E3 claim is made from skipped tests.

## Maturity

**Current maturity: E2 — Gateway Preferred.**

Promotion to E3 — Gateway Required for the included capability requires successful execution of the real Docker acceptance tests on the registered Alpha station, including authorized restart, replay rejection, parameter-tamper rejection, target/adapter/audience/expiry/signature rejection, and a verified River evidence chain.

E4 is explicitly out of scope. Direct administrator/root Docker access can still bypass WEG until OS/service-account enforcement is introduced.

## Secret handling

The repository contains no production signing key. Tests use clearly labeled non-production secrets. Runtime signing authority is supplied via `GENESIS_WARDEN_HMAC_KEY`, and evidence records token metadata rather than secret material.

## Remaining local-station verification

On `GES-ALPHA-001`, run:

```bash
cd control-plane
python -m pytest tests/test_docker_e2e.py -v
```

Only after that command passes without skips should the included Docker restart capability be considered for E3 promotion.
