from pathlib import Path

from smart_textiles.compatibility import evaluate_compatibility
from smart_textiles.registry import Registry

ROOT = Path(__file__).parents[1]
REGISTRY = Registry.load(ROOT / "registry")
RULES = ROOT / "compiler" / "compatibility-rules.yaml"

BASE = {
    "application_family": "SPT",
    "form_code": "TSH",
    "smart_architecture": {
        "integration_level": "YRN",
        "integration_method": "KNT",
        "conductive_platform": "AG",
        "body_contact_zone": "chest"
    },
    "capability_ids": ["ST-F01", "ST-F07"],
    "power_code": "TRB",
    "revision": 1,
    "regulatory_claim_class": "none",
    "regulatory_evidence_ids": []
}


def test_valid_sport_ecg_temperature_configuration_is_validated():
    result = evaluate_compatibility(BASE, REGISTRY, RULES)
    assert result.state == "VALIDATED_CONFIG"
    assert result.reason_codes == ()


def test_body_contact_capability_without_contact_zone_is_rejected():
    invalid = {**BASE, "smart_architecture": {k: v for k, v in BASE["smart_architecture"].items() if k != "body_contact_zone"}}
    result = evaluate_compatibility(invalid, REGISTRY, RULES)
    assert result.state == "REJECTED_CONFIG"
    assert "BODY_CONTACT_ZONE_REQUIRED" in result.reason_codes


def test_sweat_glucose_stays_prototype_only_in_r01():
    model = {**BASE, "capability_ids": ["ST-F09"]}
    result = evaluate_compatibility(model, REGISTRY, RULES)
    assert result.state == "PROTOTYPE_ONLY"
    assert "R01_EVIDENCE_MATURITY" in result.reason_codes


def test_regulated_claim_without_evidence_is_rejected():
    model = {**BASE, "regulatory_claim_class": "medical", "regulatory_evidence_ids": []}
    result = evaluate_compatibility(model, REGISTRY, RULES)
    assert result.state == "REJECTED_CONFIG"
    assert "REGULATORY_EVIDENCE_REQUIRED" in result.reason_codes
