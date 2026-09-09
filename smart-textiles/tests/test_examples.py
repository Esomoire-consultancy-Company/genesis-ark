from pathlib import Path
import pytest
import yaml

from smart_textiles.compatibility import evaluate_compatibility
from smart_textiles.errors import SmartTextileError, UnknownRegistryCode
from smart_textiles.registry import Registry
from smart_textiles.schema_validation import validate_document
from smart_textiles.sku import compile_catalog, compile_engineering_sku

ROOT = Path(__file__).parents[1]
REGISTRY = Registry.load(ROOT / "registry")
RULES = ROOT / "compiler" / "compatibility-rules.yaml"


def load_example(name: str):
    return yaml.safe_load((ROOT / "examples" / name).read_text(encoding="utf-8"))


def test_reference_sport_shirt_compiles_and_validates():
    model = load_example("sport-ecg-temperature-shirt.model.yaml")
    validate_document(model, "product-model.schema.json", ROOT / "contracts")
    assert compile_engineering_sku(model, REGISTRY) == "ST-SPT-TSH-YRN-KNT-ECG+TMP-AG-TRB-R01"
    assert evaluate_compatibility(model, REGISTRY, RULES).state == "VALIDATED_CONFIG"


def test_reference_industrial_jacket_compiles_and_validates():
    model = load_example("industrial-thermal-gas-jacket.model.yaml")
    validate_document(model, "product-model.schema.json", ROOT / "contracts")
    assert compile_engineering_sku(model, REGISTRY) == "ST-IND-JKT-FAB-EMB-GAS+THZ-CU-BAT-R01"
    assert evaluate_compatibility(model, REGISTRY, RULES).state == "VALIDATED_CONFIG"


def test_invalid_unknown_code_fixture_fails_registry_lookup():
    model = load_example("invalid-unknown-code.model.yaml")
    with pytest.raises(UnknownRegistryCode):
        compile_engineering_sku(model, REGISTRY)


def test_invalid_missing_contact_fixture_is_rejected_for_contact_zone():
    model = load_example("invalid-missing-contact.model.yaml")
    result = evaluate_compatibility(model, REGISTRY, RULES)
    assert result.state == "REJECTED_CONFIG"
    assert result.reason_codes == ("BODY_CONTACT_ZONE_REQUIRED",)


def test_invalid_regulated_fixture_is_rejected_for_evidence():
    model = load_example("invalid-regulated-evidence.model.yaml")
    result = evaluate_compatibility(model, REGISTRY, RULES)
    assert result.state == "REJECTED_CONFIG"
    assert result.reason_codes == ("REGULATORY_EVIDENCE_REQUIRED",)


def test_duplicate_catalog_fixture_is_rejected():
    catalog = load_example("invalid-duplicate-sku.catalog.yaml")
    with pytest.raises(SmartTextileError, match="duplicate engineering SKU"):
        compile_catalog(catalog["models"], REGISTRY)
