# Genesis Governed CloudBrowser

CloudBrowser is the first governed application executed through the Warden-Enabled Actor Box. It brokers isolated browser sessions and material browser actions; it does not grant unrestricted browser automation.

## Trust flow

```text
DigitalMe + Actor Box context
        ↓
Warden session decision and capability
        ↓
Ephemeral CloudBrowser session partition
        ↓
Domain, action, file, credential and data-boundary checks
        ↓
Human approval interception for consequential actions
        ↓
Bounded executor
        ↓
RiverOS-style evidence and compute usage
```

## Implemented API

- `POST /v1/browser-sessions`
- `GET /v1/browser-sessions/{sessionId}`
- `POST /v1/browser-sessions/{sessionId}/actions/evaluate`
- `POST /v1/browser-sessions/{sessionId}/approve`
- `POST /v1/browser-sessions/{sessionId}/pause`
- `POST /v1/browser-sessions/{sessionId}/terminate`
- `GET /v1/browser-sessions/{sessionId}/evidence`
- `GET /v1/browser-sessions/{sessionId}/usage`

## Enforced controls

- Warden must authorize and materialize the session capability.
- Every action must match the browser policy and Warden authority.
- Domain rules support exact hosts and explicit `*.subdomain` rules only.
- Raw passwords, tokens, secrets, API keys and private keys are rejected.
- Credential use accepts only a vault `credential_reference`.
- Upload, download, clipboard and screen capture remain separately controlled.
- High-impact actions pause for DigitalMe approval.
- Paused, expired or terminated sessions cannot execute new actions.
- Session and action events form a per-session evidence hash chain.
- Runtime, network, file, connector, action and approval usage is metered.

## Current executor boundary

The included `DeterministicBrowserExecutor` proves governance and orchestration without performing network access. A later isolated Chromium/Cloud Browser runtime must implement the same `BrowserExecutor` protocol and may not bypass Warden, policy, approval, evidence or metering.

## Run

```bash
cd services/cloudbrowser
python -m pip install -e . --no-build-isolation
export CLOUDBROWSER_API_TOKEN='replace-with-a-secret'
export CLOUDBROWSER_WARDEN_API_TOKEN='replace-with-a-warden-token'
cloudbrowser-service
```

## Test

```bash
cd services/cloudbrowser
pytest
```
