"""R0.8: signed read-only provider preflight regression tests (no network)."""
import base64
from datetime import datetime, timedelta, timezone
import json
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from phase8_provider_probe import (
    AUDIENCE, DOMAIN, MAX_BODY, PATH, ROLES, HTTPResult, Provider,
    ProviderPreflight, canonical,
)

NOW = datetime(2026, 11, 21, 8, 0, tzinfo=timezone.utc)
COMMIT = "a" * 40

class FakeTransport:
    def __init__(self, keys, providers):
        self.keys, self.providers = keys, providers
        self.calls = []
        self.overrides = {}
        self.http_status = 200
        self.content_type = "application/json"
        self.extra_bytes = b""
        self.fail = False

    def get(self, url, headers, timeout):
        if self.fail:
            raise TimeoutError("a private internal error")
        self.calls.append((url, dict(headers), timeout))
        role = next(r for r in ROLES if self.providers[r].url == url)
        p = self.providers[role]
        issued = (NOW - timedelta(seconds=3)).isoformat()
        expires = (NOW + timedelta(seconds=60)).isoformat()
        payload = {
            "issuer": p.issuer, "audience": AUDIENCE, "environment": "staging",
            "capability": "navigate.readonly", "classification": "READONLY_SERVICE_METADATA",
            "status": "AVAILABLE", "nonce": headers["X-VSR-ReadOnly-Challenge"],
            "request_digest": headers["X-VSR-Request-Digest"],
            "commit_sha": COMMIT, "service_version": "fixture-0.8",
            "issued_at": issued, "expires_at": expires,
        }
        payload.update(self.overrides)
        envelope = {"role": role, "kid": p.key_id, "alg": "Ed25519", "payload": payload}
        signature = self.keys[role].sign(DOMAIN + canonical(envelope))
        envelope["signature"] = base64.urlsafe_b64encode(signature).decode("ascii")
        return HTTPResult(self.http_status, self.content_type, json.dumps(envelope).encode() + self.extra_bytes)

class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.keys = {role: Ed25519PrivateKey.generate() for role in ROLES}
        self.providers = {
            role: Provider(role, f"https://{role.lower().replace('_', '-')}.staging.example.org{PATH}",
                           role.lower() + "-key", role.lower() + ".issuer")
            for role in ROLES
        }
        self.transport = FakeTransport(self.keys, self.providers)
        self.anchors = {
            (role, self.providers[role].key_id): self.keys[role].public_key()
            for role in ROLES
        }
        self.hosts = frozenset(f"{role.lower().replace('_', '-')}.staging.example.org" for role in ROLES)

    def probe(self, **overrides):
        params = dict(providers=self.providers, anchors=self.anchors,
                      approved_hosts=self.hosts, transport=self.transport)
        params.update(overrides)
        return ProviderPreflight(**params).inspect(commit_sha=COMMIT, now=NOW)

    def test_four_signed_responses_are_only_metadata(self):
        result = self.probe()
        self.assertEqual(result.disposition, "SIGNED_METADATA_PREFLIGHT_COMPLETE")
        self.assertEqual(result.structurally_verified, ROLES)
        self.assertEqual(len(self.transport.calls), 4)
        self.assertFalse(result.provider_identity_operationally_attested)
        self.assertFalse(result.genesis_registration_performed)
        self.assertFalse(result.digitalme_authentication_performed)
        self.assertFalse(result.warden_authority_granted)
        self.assertFalse(result.river_receipt_emitted)
        self.assertFalse(result.engine_execution_allowed)
        self.assertFalse(result.release_allowed)
        self.assertTrue(all(timeout == 5 for _, _, timeout in self.transport.calls))

    def test_absent_configuration_holds(self):
        self.assertEqual(ProviderPreflight().inspect(commit_sha=COMMIT, now=NOW).disposition, "HOLD")

    def test_missing_transport_holds(self):
        self.assertEqual(self.probe(transport=None).reason, "PROVIDER_CONFIGURATION_OR_TRANSPORT_MISSING")

    def test_missing_host_allowlist_holds(self):
        self.assertEqual(self.probe(approved_hosts=frozenset()).reason, "APPROVED_HOST_ALLOWLIST_MISSING")

    def test_bad_commit_holds_without_network(self):
        result = ProviderPreflight(self.providers, self.anchors, self.hosts, self.transport).inspect(
            commit_sha="not-a-commit", now=NOW)
        self.assertEqual(result.reason, "BOUND_COMMIT_REQUIRED")
        self.assertEqual(self.transport.calls, [])

    def test_naive_clock_holds(self):
        self.assertEqual(ProviderPreflight(self.providers, self.anchors, self.hosts, self.transport).inspect(
            commit_sha=COMMIT, now=datetime(2026, 11, 21)).reason, "TRUSTED_CLOCK_REQUIRED")

    def _set_endpoint(self, role, url):
        self.providers = dict(self.providers)
        p = self.providers[role]
        self.providers[role] = Provider(role, url, p.key_id, p.issuer)

    def test_http_endpoint_denied(self):
        self._set_endpoint(ROLES[0], f"http://genesis-registrar.staging.example.org{PATH}")
        self.assertEqual(self.probe().reason, "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN")

    def test_localhost_endpoint_denied(self):
        self._set_endpoint(ROLES[0], f"https://localhost{PATH}")
        self.assertEqual(self.probe().reason, "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN")

    def test_ip_literal_endpoint_denied(self):
        self._set_endpoint(ROLES[0], f"https://127.0.0.1{PATH}")
        self.assertEqual(self.probe().reason, "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN")

    def test_even_explicitly_allowlisted_ip_is_denied(self):
        self._set_endpoint(ROLES[0], f"https://127.0.0.1{PATH}")
        self.hosts = self.hosts | frozenset(("127.0.0.1",))
        self.assertEqual(self.probe().reason, "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN")

    def test_local_network_suffix_denied_even_when_approved(self):
        self._set_endpoint(ROLES[0], f"https://private.internal{PATH}")
        self.hosts = self.hosts | frozenset(("private.internal",))
        self.assertEqual(self.probe().reason, "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN")

    def test_unapproved_hostname_denied(self):
        self._set_endpoint(ROLES[0], f"https://other.staging.example.org{PATH}")
        self.assertEqual(self.probe().reason, "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN")

    def test_unexpected_port_denied(self):
        self._set_endpoint(ROLES[0], f"https://genesis-registrar.staging.example.org:8443{PATH}")
        self.assertEqual(self.probe().reason, "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN")

    def test_path_denied(self):
        self._set_endpoint(ROLES[0], "https://genesis-registrar.staging.example.org/admin")
        self.assertEqual(self.probe().reason, "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN")

    def test_query_denied(self):
        self._set_endpoint(ROLES[0], f"https://genesis-registrar.staging.example.org{PATH}?token=abc")
        self.assertEqual(self.probe().reason, "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN")

    def test_userinfo_denied(self):
        self._set_endpoint(ROLES[0], f"https://user:pass@genesis-registrar.staging.example.org{PATH}")
        self.assertEqual(self.probe().reason, "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN")

    def test_duplicate_issuer_denied(self):
        target = self.providers[ROLES[1]]
        self.providers = dict(self.providers)
        self.providers[ROLES[1]] = Provider(target.role, target.url, target.key_id,
                                           self.providers[ROLES[0]].issuer)
        self.assertEqual(self.probe().reason, "PROVIDER_INDEPENDENCE_VIOLATION")

    def test_reused_signing_key_denied(self):
        self.anchors[(ROLES[1], self.providers[ROLES[1]].key_id)] = self.keys[ROLES[0]].public_key()
        self.assertEqual(self.probe().reason, "PROVIDER_SIGNING_KEY_REUSED")

    def test_missing_pin_holds(self):
        del self.anchors[(ROLES[0], self.providers[ROLES[0]].key_id)]
        self.assertEqual(self.probe().reason, "PINNED_PROVIDER_KEY_MISSING")

    def test_wrong_audience_denied(self):
        self.transport.overrides["audience"] = "other"
        self.assertEqual(self.probe().reason, "PROVIDER_METADATA_SCOPE_MISMATCH")

    def test_wrong_nonce_denied(self):
        self.transport.overrides["nonce"] = "00" * 24
        self.assertEqual(self.probe().reason, "PROVIDER_METADATA_SCOPE_MISMATCH")

    def test_wrong_request_digest_denied(self):
        self.transport.overrides["request_digest"] = "00" * 32
        self.assertEqual(self.probe().reason, "PROVIDER_METADATA_SCOPE_MISMATCH")

    def test_wrong_capability_denied(self):
        self.transport.overrides["capability"] = "container.instance.restart"
        self.assertEqual(self.probe().reason, "PROVIDER_METADATA_SCOPE_MISMATCH")

    def test_wrong_environment_denied(self):
        self.transport.overrides["environment"] = "production"
        self.assertEqual(self.probe().reason, "PROVIDER_METADATA_SCOPE_MISMATCH")

    def test_wrong_commit_denied(self):
        self.transport.overrides["commit_sha"] = "b" * 40
        self.assertEqual(self.probe().reason, "PROVIDER_METADATA_SCOPE_MISMATCH")

    def test_expired_response_denied(self):
        self.transport.overrides["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
        self.assertEqual(self.probe().reason, "PROVIDER_METADATA_STALE")

    def test_oversized_ttl_denied(self):
        self.transport.overrides["expires_at"] = (NOW + timedelta(hours=1)).isoformat()
        self.assertEqual(self.probe().reason, "PROVIDER_METADATA_STALE")

    def test_redirect_denied(self):
        self.transport.http_status = 302
        self.assertEqual(self.probe().reason, "PROVIDER_DID_NOT_RETURN_200")

    def test_wrong_content_type_denied(self):
        self.transport.content_type = "text/html"
        self.assertEqual(self.probe().reason, "PROVIDER_CONTENT_TYPE_INVALID")

    def test_body_size_cap_denied(self):
        self.transport.extra_bytes = b" " * (MAX_BODY + 1)
        self.assertEqual(self.probe().reason, "PROVIDER_BODY_TOO_LARGE")

    def test_transport_failure_holds(self):
        self.transport.fail = True
        self.assertEqual(self.probe().reason, "PROVIDER_TRANSPORT_FAILED")

    def test_bad_nonce_source_denied(self):
        result = ProviderPreflight(self.providers, self.anchors, self.hosts, self.transport).inspect(
            commit_sha=COMMIT, now=NOW, nonce_source=lambda: "short")
        self.assertEqual(result.reason, "INVALID_CHALLENGE")

    def test_only_first_verified_service_reported_before_failure(self):
        # Role 1 passes, role 2 fails when a key is inconsistent.
        p = self.providers[ROLES[1]]
        self.anchors[(ROLES[1], p.key_id)] = Ed25519PrivateKey.generate().public_key()
        result = self.probe()
        self.assertEqual(result.structurally_verified, (ROLES[0],))
        self.assertEqual(result.reason, "PROVIDER_SIGNATURE_INVALID")

    def test_empty_service_version_denied(self):
        self.transport.overrides["service_version"] = ""
        self.assertEqual(self.probe().reason, "PROVIDER_METADATA_SCOPE_MISMATCH")

    def test_no_operational_flags_even_when_metadata_good(self):
        result = self.probe()
        self.assertTrue(result.structurally_verified)
        self.assertFalse(result.release_allowed)
        self.assertFalse(result.engine_execution_allowed)

if __name__ == "__main__":
    unittest.main()
