from pathlib import Path
import pytest

from smart_textiles.errors import SmartTextileError, UnknownRegistryCode
from smart_textiles.registry import Registry
from smart_textiles.sku import compile_catalog, compile_engineering_sku

ROOT = Path(__file__).parents[1]
REGISTRY = Registry.load(ROOT / "registry")

MODEL = {
    "application_family": "SPT",
    "form_code": "TSH",
    "smart_architecture": {
        "integration_level": "YRN",
        "integration_method": "KNT",
        "conductive_platform": "AG"
    },
    "capability_ids": ["ST-F07", "ST-F01"],
    "power_code": "TRB",
    "revision": 1
}


def test_sku_is_deterministic_and_capabilities_are_canonicalized():
    assert compile_engineering_sku(MODEL, REGISTRY) == "ST-SPT-TSH-YRN-KNT-ECG+TMP-AG-TRB-R01"


def test_unknown_form_code_is_rejected():
    invalid = {**MODEL, "form_code": "NOPE"}
    with pytest.raises(UnknownRegistryCode, match="NOPE"):
        compile_engineering_sku(invalid, REGISTRY)


def test_catalog_rejects_duplicate_engineering_sku():
    with pytest.raises(SmartTextileError, match="duplicate engineering SKU"):
        compile_catalog([MODEL, dict(MODEL)], REGISTRY)
