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
