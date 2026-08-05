# Genesis Runtime Manager

Capability-aware control plane for the Genesis governed execution fabric.

## Implemented boundary

- registers attested runtime nodes;
- provisions Actor Box-bound runtime instances within node capacity;
- requires runtime attestation before activation;
- starts runtime sessions only with an active Warden capability;
- allocates CPU, memory, GPU, storage, network and browser slots within instance limits;
- persists hash-linked runtime events as a durable outbox;
- records health reports;
- converts critical health into an `AUTHORIZATION_REQUIRED` recovery job;
- terminates sessions and releases their resource allocations.

The service never performs autonomous recovery. Recovery execution requires a separate Warden capability with action `RUNTIME_RECOVERY_EXECUTE`.

## Local run

```bash
cd services/runtime
python -m pip install -e '.[test]'
export RUNTIME_MANAGER_API_TOKEN='replace-with-a-secret'
genesis-runtime-manager
```

The memory backend is for tests and local development. Set `RUNTIME_MANAGER_REPOSITORY_BACKEND=postgres` and `RUNTIME_MANAGER_DATABASE_URL` to use the private PostgreSQL/Supabase control-plane adapter.

## Security

Every API operation requires bearer authentication and a trusted mTLS ingress assertion. The ingress must remove caller-supplied certificate assertion headers and inject them only after successful certificate verification.
