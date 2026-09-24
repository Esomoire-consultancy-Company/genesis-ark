# Genesis Engineering Station Alpha Control Plane

This directory contains the R0.1 Alpha-only governed execution path for `GES-ALPHA-001`.

## Scope

R0.1 supports one governed mutation: `container.instance.restart` against an explicitly registered Alpha resource. It does not expose arbitrary shell execution, production authority, credential reveal, database destruction, network mutation, or physical-device writes.

## Local setup

```bash
cd control-plane
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
# bash: source .venv/bin/activate
pip install -e ".[test]"
```

Supply a local signing secret at runtime; never commit it:

```bash
export GENESIS_WARDEN_HMAC_KEY="replace-with-local-random-secret"
```

PowerShell equivalent:

```powershell
$env:GENESIS_WARDEN_HMAC_KEY = "replace-with-local-random-secret"
```

The registered R0.1 resource is `RES-RIVER-WORKER-001`, whose Docker implementation name is `river-worker`.

```bash
ges-alpha restart --resource RES-RIVER-WORKER-001 --timeout 30
```

Runtime state defaults under `control-plane/.runtime/` and can be redirected with `GENESIS_REPLAY_DB` and `GENESIS_RIVER_JOURNAL`. The registry can be overridden with `GENESIS_REGISTRY_PATH` for disposable Alpha tests.

## Enforcement boundary

The path is:

`Command -> Warden -> one-shot token -> WEG -> Docker adapter -> verifier -> River evidence`

R0.1 is initially E2 (Gateway Preferred). Direct Docker administrator/root access still exists outside the gateway; E4 enforcement requires later OS/service-account controls.

## Optional signed intent gate (reference integration)

`IntentSignatureVerifier` is an additive guard for service callers. Construct
`Warden(..., intent_verifier=IntentSignatureVerifier(genesis_key_resolver))` and
pass `SignedCommandIntent` to `GovernedExecutionService.execute`. Inject the
same verifier into `WardenExecutionGateway`; the service rejects a mismatch.
With this
gate configured, missing, expired, unadmitted or altered Ed25519 intent is
denied before a capability token or Docker effect. The gateway rechecks the
signature and currently admitted key, then atomically consumes the token,
signed nonce and command ID in SQLite before Docker is called. Retries with
the same command or nonce are rejected, including after restart. The resolver must obtain
the principal's admitted current public key from Genesis; never trust a key
or `signature_verified` boolean supplied with the request. The signed payload
is `intent_bytes(command, intent)` and includes the entire command, nonce,
expiry, principal and key ID under a distinct protocol domain.

The `signed-restart --request /path/to/request.json` CLI route enables this gate
when `GENESIS_ACTOR_KEYS_PATH` points to a separately operator-provisioned
Alpha trust snapshot. The JSON request has `command` (all `Command` fields)
and `signed_intent` (`principal_id`, `key_id`, `nonce`, `expires_at`,
`signature_hex`); sign `intent_bytes(command, intent)` with Ed25519. The
trust snapshot format is `{"keys":[{"principal_id":"DM-001",
"key_id":"GENESIS-KEY-001","state":"active","valid_from":"...+00:00",
"valid_until":"...+00:00","public_key_hex":"<32-byte-hex>"}]}`. Keep this
file under operator control outside the request channel, and provision fresh
key state before using this route. The original `restart` command retains its
existing R0.1 behavior and is **not** an enforcement boundary against local
operators with Docker access.

The local file is an Alpha development adapter, not a Genesis authority or
authenticated federation source. Production use still needs a governed key
registry, authenticated ingress/session binding, WebAuthn or VC or federation
adapters as applicable, delegation evaluation, and OS controls to prevent
direct Docker bypass. A valid actor signature is never itself a Warden permit.
The signed service route refreshes the gateway clock before token consumption;
callers can inject a deterministic clock for tests.
