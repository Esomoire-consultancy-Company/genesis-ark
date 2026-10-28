# Genesis synthetic actor and licence baseline R0.1

**Status:** candidate test contract; not a production registry, real licence,
operational identity service, account issuer, credential generator, or payment
simulation with external effects.

This fixture defines fictional DigitalMe-like actors, a Commons membership,
BNR nodes, representative delegations, legal supplier bindings, synthetic
licence entitlements, permission policies, and deterministic River-style
receipts. It establishes a shared acceptance *vocabulary* rather than
silently modifying any existing service.

## Run the sandbox

From repository root (Python 3.10 or later):

```sh
python3 synthetic-baseline/verify.py
python3 -m unittest discover -s synthetic-baseline -p 'test_*.py' -v
```

No installations, network, credentials, APIs, live users, storage services,
payments, GitHub permissions or secrets are required.

## Identity, authority and legal supplier boundaries

- All actor, organisation, representation and licence IDs begin `SYN-`.
- Actor and membership state are checked before any entitlement is considered.
- Subscription quoting requires active Commons membership, valid BNR node
  representation, correct synthetic licence scope, and an explicitly named
  legal supplier separate from the Commons and the BNR node.
- An `ALLOW` means the synthetic policy oracle predicts permission *for a
  fictional test scenario*. It still sets `executable: false` and never
  performs any action.
- An `ESCALATE` is review-required and never silently becomes an approval.
- Unknown action, unregistered actor, invalid membership, expired licence,
  wrong node, wrong supplier and non-synthetic environment are all DENY.
- Repeating a request ID with identical parameters is idempotent; replaying
  the same ID with changed parameters is rejected.
- Every outcome includes a SHA-256 digest for reproducible synthetic evidence,
  but this is not a deployed RiverOS evidence record.
- This fixture must not create real DigitalMe accounts, official legal
  licences, third-party subscriptions, invoices, payments or deployments.

## Use by other repositories

Adopt the fixture as a versioned contract in a separate reviewed PR. Clients
can map `SYN-ACTOR-*`, `SYN-ORG-*` and `SYN-LIC-*` into their **own** test
adapters, but must not treat the fixture as an authority service. Consumer
repos should test both happy paths and rejection cases and assert zero
real effects. Only after separately reviewed API/contract bridges are
available should cross-repo CI attempt integration.

## Acceptance state

The synthetic acceptance suite is independent of any browser smoke test.
Browser timeouts should be classified as `CI_INFRA_TRANSIENT` and retried in
bounded fashion only if the error is clearly transport-related; policy test
failures, denied decisions and assertions must never be retried into success.

## Try fictional users in a local endpoint

```sh
python3 synthetic-baseline/server.py
```

The simulator binds only to `127.0.0.1:4178` and offers synthetic-only
routes. `GET /health` reports non-operational status; `GET /catalog` and
`GET /scenarios` list fictional fixture data; `POST /simulate` returns an
inert policy receipt. The browser workbench is served from `/` with local
JavaScript/CSS. No real identities or execution endpoints are exposed. No real login, billing, settlement or
privileged operation is possible. Example:

```sh
curl -sS -X POST http://127.0.0.1:4178/simulate \
  -H 'Content-Type: application/json' \
  -d '{"request_id":"SYN-REQ-DEMO-001","actor_id":"SYN-ACTOR-CREATOR-01","action":"creator.draft.synthetic","environment":"synthetic-ci"}'
```

The server is an optional local demonstration only, **not** a service to
expose on public hosting. No runtime endpoint should be wired to the actual
Genesis Gateway until a separate authority, authentication and evidence
review has passed.

## R0.2 local interactive workbench

Run the same loopback simulator and visit [http://127.0.0.1:4178/](http://127.0.0.1:4178/):

```sh
python3 synthetic-baseline/server.py
```

The browser workbench includes a fictional actor selector, an inspection of
Commons membership/BNR representation/synthetic licences, a scenario selector,
and a non-executable decision and digest view. It never offers a login or a
real authority surface. Its JavaScript and stylesheet are served locally with
restrictive CSP and no third-party assets. The server's API now also exposes
`GET /scenarios` for the shared acceptance matrix. The HTTP contract suite
checks the local endpoints, metadata and no-live-route boundary.

Optional visual browser validation (requires an installed local Chromium and
Playwright Python):

```sh
python3 tools/browser_workbench_qa.py
```

This optional test renders the workbench with explicitly intercepted synthetic
responses and the real local `SyntheticOracle`; it does not open an external
web address or require a browser to connect to the loopback HTTP server.
The ordinary server contract tests separately exercise the real loopback HTTP
routes. A live browser-to-server deployment test remains a separate gate.

The canonical `fixtures.json` and `scenarios.json` hashes are pinned in
`synthetic-baseline/fixture-lock.json`. The lock is reviewed and must only be
regenerated after a deliberate fixture schema/content change. Neither `ALLOW`
nor `ESCALATE` may ever dispatch a real effect.

See `docs/SYNTHETIC_CONSUMER_MAPPING_R02.md` before adding a consumer adapter.
