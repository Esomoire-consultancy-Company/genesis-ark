# Genesis Governed CloudBrowser

CloudBrowser is the first governed application executed through the Warden-Enabled Actor Box. It brokers isolated browser sessions and material actions; it does not grant unrestricted automation.

## Trust flow

```text
DigitalMe + Actor Box context
        ↓
Warden decision and short-lived capability
        ↓
Non-persistent Chromium BrowserContext
        ↓
Domain, action, file and credential controls
        ↓
Durable authorization or DigitalMe approval
        ↓
Bounded browser execution
        ↓
RiverOS-style evidence and usage metering
```

## API

- `POST /v1/browser-sessions`
- `GET /v1/browser-sessions/{sessionId}`
- `POST /v1/browser-sessions/{sessionId}/actions/evaluate`
- `POST /v1/browser-sessions/{sessionId}/approve`
- `POST /v1/browser-sessions/{sessionId}/pause`
- `POST /v1/browser-sessions/{sessionId}/terminate`
- `GET /v1/browser-sessions/{sessionId}/evidence`
- `GET /v1/browser-sessions/{sessionId}/usage`

## Execution guarantees

- Every session and action is checked by browser policy and Warden.
- Raw credentials and secrets are rejected; credential references fail closed without a configured provider.
- Action IDs are idempotent and cannot be reused with a different request.
- A normal action is durably recorded as `ALLOW` before Chromium executes.
- A consequential action is durably recorded as `APPROVED` before execution.
- Client retries do not re-execute an already recorded action.
- Evidence chains and state/usage writes are serialized transactionally per session.
- Pausing, expiry and termination close the Chromium context.

## Chromium mode

`CLOUDBROWSER_EXECUTOR_MODE=PLAYWRIGHT` activates the isolated Playwright adapter. Each session receives a fresh BrowserContext with service workers blocked, no permissions granted by default, request interception, domain allowlisting and owner-only quarantine directories.

The Playwright package is pinned to `1.61.0`; its browser binaries must match that version.

```bash
cd services/cloudbrowser
python -m pip install -e '.[production,test]'
export CLOUDBROWSER_REPOSITORY_BACKEND=postgres
export CLOUDBROWSER_DATABASE_URL='<protected connection string>'
export CLOUDBROWSER_EXECUTOR_MODE=PLAYWRIGHT
export CLOUDBROWSER_API_TOKEN='<secret>'
export CLOUDBROWSER_WARDEN_API_TOKEN='<secret>'
cloudbrowser-service
```

## Container

Build from the repository root:

```bash
docker build -f services/cloudbrowser/Dockerfile -t genesis-cloudbrowser .
```

Run it as the image's `pwuser` with a suitable seccomp profile and network egress policy. Do not run the browser as root and do not disable the Chromium sandbox.

## Test

```bash
PYTHONPATH=services/cloudbrowser/src:services/warden/src pytest -q services/cloudbrowser/tests
```

The suite includes real system-Chromium checks when `/usr/bin/chromium` is available, including cookie isolation, domain blocking and context termination.
