"""Phase 5 fixture-only contract regression tests: no authority implied."""
import unittest
from datetime import datetime, timedelta, timezone
from staging_chain import StagingNavigationChain, MemoryFixtureReplay, _route_hash

NOW = datetime(2026, 11, 21, 5, 0, tzinfo=timezone.utc)

class Registrar:
    def __init__(self):
        self.records = {i: dict(registration_state="ACTIVE", revoked=False,
            station_ids=["KS-DEMO"], genesis_id="REG-" + i, version="1.0.0",
            source_ref="SOURCE-" + i, attestation_ref="ATTEST-" + i,
            engine_execution_allowed=False) for i in ("FOR-0001", "FOR-0003")}
    def resolve(self, framework_ids, station_id):
        return self.records

class Identity:
    def __init__(self, now):
        self.claim = dict(verified=True, revoked=False, consent_granted=True,
            mandate_active=True, capability="navigate.readonly", issuer="DIGITALME-FIXTURE",
            expires_at=(now + timedelta(seconds=60)).isoformat())
    def verify(self, intent):
        return {**intent, **self.claim}

class Warden:
    def __init__(self, now):
        self.override = {}
        self.expiry = (now + timedelta(seconds=50)).isoformat()
    def evaluate(self, payload):
        return {**payload, "decision": "PERMIT", "decision_id": "WD-FIXTURE-1",
                "policy_id": "WARDEN-SANDBOX-001", "issuer": "STAGING-FIXTURE",
                "audience": "vsr.knowledge-roads.staging", "revoked": False,
                "expires_at": self.expiry, **self.override}

class River:
    def __init__(self):
        self.override = {}
        self.events = []
    def acknowledge(self, event):
        self.events.append(event)
        return {"status": "FIXTURE_ACK", "classification": "TEST_ONLY",
                "route_digest": event["route_digest"], "decision_id": event["decision_id"],
                "fixture_receipt_id": "FIXTURE-RIVER-01", **self.override}

class StagingTests(unittest.TestCase):
    def setUp(self):
        self.reg = Registrar()
        self.idp = Identity(NOW)
        self.warden = Warden(NOW)
        self.river = River()
        self.replay = MemoryFixtureReplay()
        self.chain = StagingNavigationChain(self.reg, self.idp, self.warden, self.river, self.replay)
        self.req = dict(request_id="REQ-DEMO", principal_id="PRINCIPAL-DEMO",
            session_id="SESSION-DEMO", estate_id="ESTATE-DEMO", station_id="KS-DEMO",
            location_id="LOC-DEMO", purpose="planning", capability="navigate.readonly",
            steps=["FOR-0001", "FOR-0003"], execute=False, mutation=False,
            expires_at=(NOW + timedelta(seconds=60)).isoformat())

    def check(self, reason, change=None, req=None, disposition=None):
        if change: change()
        result = self.chain.evaluate(self.req if req is None else req, NOW)
        self.assertEqual(result.reason, reason)
        if disposition: self.assertEqual(result.disposition, disposition)
        self.assertFalse(result.external_authority_granted)
        self.assertFalse(result.engine_execution_allowed)
        self.assertFalse(result.river_receipt_emitted)
        return result

    def test_happy_fixture_path_never_grants_authority(self):
        result = self.check("NO_LIVE_AUTHORITY_OR_EVIDENCE", disposition="STAGING_PREVIEW_ACCEPTED")
        self.assertTrue(result.simulated_evidence_ack)
        self.assertEqual(len(self.river.events), 1)
        self.assertEqual(self.river.events[0]["classification"], "TEST_ONLY")

    def test_ports_missing_hold(self):
        chain = StagingNavigationChain()
        self.assertEqual(chain.evaluate(self.req, NOW).reason, "TRUSTED_SERVICE_ADAPTERS_NOT_CONNECTED")

    def test_production_action_disallowed(self):
        self.check("UNSUPPORTED_CAPABILITY", req={**self.req, "capability": "execute.engine"})

    def test_execute_disallowed(self):
        self.check("EXECUTION_OR_MUTATION_NOT_ALLOWED", req={**self.req, "execute": True})

    def test_execute_not_specified_disallowed(self):
        req = dict(self.req); del req["execute"]
        self.check("EXECUTION_OR_MUTATION_NOT_ALLOWED", req=req)

    def test_proposed_registry_held(self):
        self.check("REGISTRY_RECORD_NOT_ACTIVE_OR_REVOKED",
                   lambda: self.reg.records["FOR-0001"].update(registration_state="PROPOSED_LOCAL_ONLY"))

    def test_revoked_registry_held(self):
        self.check("REGISTRY_RECORD_NOT_ACTIVE_OR_REVOKED",
                   lambda: self.reg.records["FOR-0001"].update(revoked=True))

    def test_station_mismatch_denied(self):
        self.check("FRAMEWORK_OUT_OF_STATION_SCOPE", req={**self.req, "station_id": "KS-OTHER"})

    def test_bad_station_bindings_held(self):
        self.check("INVALID_REGISTRY_STATION_BINDINGS",
                   lambda: self.reg.records["FOR-0001"].update(station_ids=None))

    def test_registry_provenance_missing_held(self):
        self.check("REGISTRY_PROVENANCE_INCOMPLETE", lambda: self.reg.records["FOR-0001"].update(source_ref=""))

    def test_registry_collision_held(self):
        self.check("GENESIS_ID_COLLISION", lambda: self.reg.records["FOR-0003"].update(genesis_id="REG-FOR-0001"))

    def test_engine_registry_not_admitted(self):
        self.check("ENGINE_EXECUTION_REGISTRY_SCOPE",
                   lambda: self.reg.records["FOR-0001"].update(engine_execution_allowed=True))

    def test_identity_unverified(self):
        self.check("IDENTITY_NOT_VERIFIED", lambda: self.idp.claim.update(verified=False))

    def test_identity_no_consent(self):
        self.check("CONSENT_OR_MANDATE_MISSING", lambda: self.idp.claim.update(consent_granted=False))

    def test_identity_no_mandate(self):
        self.check("CONSENT_OR_MANDATE_MISSING", lambda: self.idp.claim.update(mandate_active=False))

    def test_identity_scope_mismatch(self):
        self.check("IDENTITY_SCOPE_MISMATCH", lambda: self.idp.claim.update(estate_id="ESTATE-WRONG"))

    def test_identity_expired(self):
        self.check("IDENTITY_ATTESTATION_EXPIRED",
                   lambda: self.idp.claim.update(expires_at=(NOW-timedelta(seconds=1)).isoformat()))

    def test_warden_not_permit(self):
        self.check("WARDEN_NO_SCOPED_PERMIT", lambda: self.warden.override.update(decision="DENY"))

    def test_warden_different_route(self):
        self.check("WARDEN_SCOPE_OR_ROUTE_MISMATCH", lambda: self.warden.override.update(route_digest="WRONG"))

    def test_warden_different_principal(self):
        self.check("WARDEN_SCOPE_OR_ROUTE_MISMATCH", lambda: self.warden.override.update(principal_id="OTHER"))

    def test_warden_revoked(self):
        self.check("WARDEN_DECISION_REVOKED", lambda: self.warden.override.update(revoked=True))

    def test_warden_expiry(self):
        self.check("WARDEN_DECISION_EXPIRED_OR_EXCESSIVE",
                   lambda: setattr(self.warden, "expiry", (NOW-timedelta(seconds=1)).isoformat()))

    def test_replay_denial(self):
        self.chain.evaluate(self.req, NOW)
        self.check("DUPLICATE_WARDEN_DECISION")

    def test_river_ack_mismatch(self):
        self.check("RIVER_FIXTURE_ACK_MISSING_OR_MISMATCHED",
                   lambda: self.river.override.update(route_digest="WRONG"))

    def test_missing_purpose(self):
        self.check("MISSING_IDENTITY_SCOPE_OR_PURPOSE", req={**self.req, "purpose": ""})

    def test_expired_intent(self):
        self.check("INVALID_INTENT_EXPIRY", req={**self.req, "expires_at": (NOW-timedelta(seconds=1)).isoformat()})

    def test_ttl_long(self):
        self.check("INTENT_TTL_EXCEEDS_POLICY", req={**self.req, "expires_at": (NOW+timedelta(minutes=6)).isoformat()})

    def test_duplicate_steps(self):
        self.check("INVALID_OR_DUPLICATE_FRAMEWORK", req={**self.req, "steps": ["FOR-0001", "FOR-0001"]})

    def test_hash_includes_provenance_and_order(self):
        original = self.chain.evaluate(self.req, NOW).route_digest
        self.reg.records["FOR-0001"]["source_ref"] = "NEW-SOURCE"
        updated = StagingNavigationChain(self.reg, self.idp, self.warden, self.river,
                                         MemoryFixtureReplay()).evaluate(self.req, NOW).route_digest
        self.assertNotEqual(original, updated)
        self.assertNotEqual(_route_hash(self.req, [dict(source_id="A")]),
                            _route_hash(self.req, [dict(source_id="B")]))

    def test_no_real_evidence_flag_under_fixture(self):
        result = self.chain.evaluate(self.req, NOW)
        self.assertTrue(result.simulated_evidence_ack)
        self.assertFalse(result.river_receipt_emitted)

    def test_port_exception_no_details_leaked(self):
        class ExplodingRegistrar:
            def resolve(self, framework_ids, station_id): raise RuntimeError("private-secret")
        self.chain.registrar = ExplodingRegistrar()
        result = self.check("REGISTRAR_PORT_UNAVAILABLE")
        self.assertNotIn("private-secret", str(result))

if __name__ == "__main__":
    unittest.main()
