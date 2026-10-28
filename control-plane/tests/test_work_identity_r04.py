"""R0.4 acceptance: external signed JWT, consent/revocation and tenant isolation."""
import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from genesis_control_plane.work_capture import sign_packet
from genesis_control_plane.work_consent import WardenConsentStore
from genesis_control_plane.work_fabric import DigitalMeWorkFabric
from genesis_control_plane.work_gateway import AdmissionDenied, ConsentGrant, RegisteredSource
from genesis_control_plane.work_identity import (
    DigitalMeAccessVerifier, IdentityContext, IdentityDenied, TokenRevocations,
)

NOW = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)
ISSUER = "https://identity.example.invalid"
AUDIENCE = "genesis-work-gateway-alpha"
SOURCE_KEY = b"test-adapter-hmac-very-long-r04-isolated-only-key"


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@pytest.fixture()
def env(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = key.public_key().public_numbers()
    jwks = {"keys": [{"kty": "RSA", "alg": "RS256", "use": "sig", "kid": "KEY-01",
                      "n": b64(numbers.n.to_bytes((numbers.n.bit_length() + 7)//8, "big")),
                      "e": b64(numbers.e.to_bytes((numbers.e.bit_length() + 7)//8, "big"))}]}
    revoked = TokenRevocations(tmp_path / "revoke.sqlite")
    verifier = DigitalMeAccessVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=jwks, revocations=revoked)
    store = WardenConsentStore(tmp_path / "consent.sqlite")
    fabric = DigitalMeWorkFabric(
        verifier=verifier, consent=store,
        source_key_resolver=lambda tenant, source: SOURCE_KEY if source == "APP-01" else None,
        ledger_path=tmp_path / "ledger.sqlite", journal_path=tmp_path / "river.jsonl",
    )
    return {"key": key, "revoked": revoked, "verifier": verifier,
            "store": store, "fabric": fabric, "tmp_path": tmp_path}


def mint(env, *, tenant="BNR-T1", sub="DM-001", sid="SID-01",
         scopes="work:capture work:read", jti="JTI-01", overrides=None, header=None):
    claims = {
        "iss": ISSUER, "aud": AUDIENCE, "token_use": "access",
        "sub": sub, "tenant_id": tenant, "station_id": "GES-ALPHA-001",
        "source": "APP-01", "sid": sid, "jti": jti,
        "scope": scopes, "iat": int((NOW-timedelta(seconds=20)).timestamp()),
        "nbf": int((NOW-timedelta(seconds=20)).timestamp()),
        "exp": int((NOW+timedelta(minutes=5)).timestamp()),
    }
    claims.update(overrides or {})
    head = {"alg": "RS256", "typ": "JWT", "kid": "KEY-01"}
    head.update(header or {})
    encoded = b64(json.dumps(head, separators=(",", ":")).encode()) + "." + b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = env["key"].sign(encoded.encode(), padding.PKCS1v15(), hashes.SHA256())
    return encoded + "." + b64(signature)


def administrator(tenant="BNR-T1", subject="DM-ADMIN"):
    return IdentityContext(ISSUER, subject, tenant, "GES-ALPHA-001",
                           "APP-01", "ADMIN-SID", "ADMIN-JTI", frozenset({"work:admin"}),
                           int((NOW+timedelta(minutes=5)).timestamp()))


def provision(env, *, tenant="BNR-T1", sub="DM-001", work="GW-001"):
    source = RegisteredSource(tenant, sub, "GES-ALPHA-001", "APP-01",
                              frozenset({"typed", "voice_dictation", "voice_live"}))
    grant = ConsentGrant("CONSENT-" + tenant + "-" + sub + "-" + work, tenant, sub,
                         "GES-ALPHA-001", "APP-01", work, datetime.now(timezone.utc)+timedelta(days=1))
    admin = administrator(tenant)
    env["store"].register_source(admin, source=source)
    env["store"].register_grant(admin, grant=grant)
    return source, grant


def packet(tenant="BNR-T1", work="GW-001", *, message="MSG-001", sid="SID-01", capture="CAP-001"):
    data = dict(kind="work.input", payload={
        "tenant_id": tenant, "work_id": work, "message_id": message, "capture_id": capture,
        "channel": "voice_dictation", "provenance": "observed", "nature": "command",
        "modalities": ["text", "image"],
        "attachments": [{"asset_id": "IMAGE-01", "modality": "image"}],
    }, station_id="GES-ALPHA-001", principal_id="DM-001",
        session_id=sid, correlation_id="COR-001", source="APP-01",
        issued_at=NOW.isoformat())
    return sign_packet(data, SOURCE_KEY)


def test_verified_capture_private_counts_and_dedup(env):
    provision(env)
    token = mint(env)
    p = packet()
    first = env["fabric"].capture(access_token=token, packet=p, now=NOW)
    assert not first.duplicate
    second = env["fabric"].capture(access_token=token, packet=p, now=NOW)
    assert second.duplicate and first.record_hash == second.record_hash
    summary = env["fabric"].private_counts(access_token=token, work_id="GW-001", now=NOW)
    assert summary["input_messages"] == 1
    assert summary["channels_observed"] == {"voice_dictation": 1}
    assert summary["attached_assets"] == {"image": 1}
    assert summary["privacy_scope"] == "tenant+principal+work"


def test_read_isolates_tenant_and_principal(env):
    provision(env)
    env["fabric"].capture(access_token=mint(env), packet=packet(), now=NOW)
    foreign_tenant = mint(env, tenant="BNR-T2", jti="JTI-T2")
    foreign_member = mint(env, sub="DM-002", jti="JTI-M2")
    for token in (foreign_tenant, foreign_member):
        result = env["fabric"].private_counts(access_token=token, work_id="GW-001", now=NOW)
        assert result["receipt_count"] == 0
        assert result["input_messages"] == 0


def test_invalid_signature_and_wrong_issuer_denied(env):
    token = mint(env, overrides={"iss": "https://attacker.invalid"})
    with pytest.raises(IdentityDenied, match="ISSUER_AUDIENCE_DENIED"):
        env["verifier"].verify(token, required_scope="work:read", now=NOW)
    token = mint(env)
    broken = token[:-5] + "AAAAA"
    with pytest.raises(IdentityDenied, match="SIGNATURE_INVALID"):
        env["verifier"].verify(broken, required_scope="work:read", now=NOW)


@pytest.mark.parametrize("overrides,reason", [
    ({"aud": "different"}, "ISSUER_AUDIENCE_DENIED"),
    ({"token_use": "id"}, "ACCESS_TOKEN_REQUIRED"),
    ({"exp": int((NOW-timedelta(seconds=1)).timestamp())}, "TOKEN_EXPIRED_OR_EARLY"),
    ({"nbf": int((NOW+timedelta(minutes=3)).timestamp())}, "TOKEN_EXPIRED_OR_EARLY"),
    ({"exp": int((NOW+timedelta(hours=2)).timestamp())}, "TOKEN_LIFETIME_DENIED"),
    ({"tenant_id": ""}, "TENANT_INVALID"),
])
def test_unacceptable_claims_denied(env, overrides, reason):
    with pytest.raises(IdentityDenied, match=reason):
        env["verifier"].verify(mint(env, overrides=overrides), required_scope="work:read", now=NOW)


def test_reject_algorithm_confusion_and_unknown_key(env):
    with pytest.raises(IdentityDenied, match="ALGORITHM_DENIED"):
        env["verifier"].verify(mint(env, header={"alg":"none"}), required_scope="work:read", now=NOW)
    with pytest.raises(IdentityDenied, match="UNKNOWN_KID"):
        env["verifier"].verify(mint(env, header={"kid":"other"}), required_scope="work:read", now=NOW)


def test_reject_insufficient_scope_and_revoked_token_or_session(env):
    token = mint(env, scopes="work:read")
    with pytest.raises(IdentityDenied, match="SCOPE_DENIED"):
        env["verifier"].verify(token, required_scope="work:capture", now=NOW)
    token = mint(env)
    env["revoked"].revoke_token(ISSUER, "JTI-01")
    with pytest.raises(IdentityDenied, match="TOKEN_REVOKED"):
        env["verifier"].verify(token, required_scope="work:read", now=NOW)
    another = mint(env, jti="JTI-02")
    env["revoked"].revoke_session(ISSUER, "SID-01")
    with pytest.raises(IdentityDenied, match="TOKEN_REVOKED"):
        env["verifier"].verify(another, required_scope="work:read", now=NOW)


def test_revoked_consent_immediately_denies_new_capture(env):
    _, grant = provision(env)
    env["fabric"].capture(access_token=mint(env), packet=packet(), now=NOW)
    env["store"].revoke_grant(administrator(), grant.consent_id)
    with pytest.raises(AdmissionDenied, match="UNAMBIGUOUS_CONSENT_REQUIRED"):
        env["fabric"].capture(access_token=mint(env), packet=packet(message="MSG-002", capture="CAP-002"), now=NOW)


def test_revoked_source_denies_capture(env):
    source, _ = provision(env)
    env["store"].revoke_source(administrator(), source)
    with pytest.raises(AdmissionDenied, match="SOURCE_NOT_REGISTERED"):
        env["fabric"].capture(access_token=mint(env), packet=packet(), now=NOW)


def test_no_self_grants_or_cross_tenant_admin_grants(env):
    source = RegisteredSource("BNR-T1", "DM-001", "GES-ALPHA-001", "APP-01", frozenset({"typed"}))
    with pytest.raises(AdmissionDenied, match="SELF_GRANT_DENIED"):
        env["store"].register_source(administrator(subject="DM-001"), source=source)
    with pytest.raises(AdmissionDenied, match="SELF_GRANT_DENIED"):
        env["store"].register_source(administrator(tenant="BNR-T2"), source=source)


def test_read_scope_is_separate_and_capture_requires_consent(env):
    provision(env)
    with pytest.raises(IdentityDenied, match="SCOPE_DENIED"):
        env["fabric"].private_counts(access_token=mint(env, scopes="work:capture"),
                                     work_id="GW-001", now=NOW)
    with pytest.raises(IdentityDenied, match="SCOPE_DENIED"):
        env["fabric"].capture(access_token=mint(env, scopes="work:read"),
                              packet=packet(), now=NOW)
    with pytest.raises(AdmissionDenied, match="UNAMBIGUOUS_CONSENT_REQUIRED"):
        env["fabric"].capture(access_token=mint(env), packet=packet(work="GW-OTHER"), now=NOW)


def test_tampered_river_blocks_private_read(env):
    provision(env)
    env["fabric"].capture(access_token=mint(env), packet=packet(), now=NOW)
    f = env["tmp_path"] / "river.jsonl"
    f.write_text(f.read_text().replace("voice_dictation", "typed"))
    with pytest.raises(AdmissionDenied, match="RIVER_CHAIN_INVALID"):
        env["fabric"].private_counts(access_token=mint(env), work_id="GW-001", now=NOW)


def test_no_evidence_or_table_enumeration_before_capture(env):
    with pytest.raises(AdmissionDenied, match="EVIDENCE_NOT_READY"):
        env["fabric"].private_counts(access_token=mint(env), work_id="GW-001", now=NOW)
