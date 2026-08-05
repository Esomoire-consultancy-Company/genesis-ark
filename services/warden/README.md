# Genesis Warden Service

Runnable, deny-by-default policy and capability service for the Warden-Enabled Actor Box.

## Implemented operations

- `POST /v1/policy-decisions/evaluate`
- `POST /v1/capabilities/issue`
- `POST /v1/capabilities/{capabilityId}/revoke`
- `POST /v1/boxes/{boxId}/lock`
- `GET /v1/boxes/{boxId}/control-state`

The operation IDs match `../../openapi/warden/v1/openapi.yaml`.

## Security boundary

Every control-plane operation requires both:

1. a bearer token matching `WARDEN_API_TOKEN`; and
2. a trusted ingress assertion header, defaulting to `X-Client-Cert-Verified: SUCCESS`.

The ingress or service mesh must remove any caller-supplied version of this header and inject it only after successful client-certificate verification. The service must not be exposed directly to untrusted networks.

## Local run

```bash
cd services/warden
python -m pip install -e '.[test]'
export WARDEN_API_TOKEN='replace-with-a-secret'
warden-service
```

The default service starts with an empty in-memory registry and therefore denies policy requests until an authoritative registry adapter supplies Actor Box state. The in-memory adapter exists for deterministic tests and local development; it is not the production system of record.

## Test

```bash
cd services/warden
pytest
```

The tests prove:

- missing state denies;
- failed runtime attestation denies;
- missing cross-zone boundary rules deny;
- valid human authority allows;
- delegated write-capable work without human approval is reduced to read-only;
- capability issue, revocation and emergency Box lock work end to end;
- RiverOS-style evidence events maintain a per-Box hash chain;
- generated API operation IDs match the canonical contract.
