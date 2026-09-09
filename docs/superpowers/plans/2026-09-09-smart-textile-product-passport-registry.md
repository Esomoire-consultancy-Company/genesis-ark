# Smart Textile Product Passport Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first executable Smart Textile Registry slice that validates the approved taxonomy, compiles deterministic engineering SKUs, evaluates starter compatibility rules, assembles hierarchical product passports, and enforces Warden/River release references.

**Architecture:** Implement `smart-textiles/` as a Python 3.11 sibling subsystem inside `genesis-ark`, following the existing repository's pytest conventions. Canonical YAML registries are loaded into a small immutable registry API; JSON Schema validates model/passport shape; pure Python compiler and compatibility functions make deterministic decisions; passport assembly and release guards remain side-effect free so live Genesis, Warden and River service integration can be added later without breaking identifiers.

**Tech Stack:** Python >=3.11, pytest >=8.0, PyYAML >=6.0, jsonschema >=4.23, JSON Schema Draft 2020-12, YAML.

**Spec:** `docs/superpowers/specs/2026-09-09-smart-textile-product-passport-registry-design.md`

## Global Constraints

- Keep the hierarchy `Smart Textile Platform -> Capability Bundle -> Product Model -> Commercial Variant -> Production Batch -> Serialized Item`.
- Initial canonical registry contains exactly 3 integration levels, 3 integration methods, 5 conductive platforms, 17 capabilities and 5 application families.
- Never pre-generate the 5,898,195 theoretical configuration combinations; compile configurations on demand.
- Every machine identifier must have a stable English name and human-readable code.
- Capability IDs are immutable identities; later changes use versioning or supersession rather than ID reuse.
- DPP output is `DPP-ready`, not declared final textile-DPP-compliant.
- Model/batch/item hierarchy must preserve historical state; child records never silently mutate parents.
- Warden authorizes lifecycle transitions; the compiler does not grant authority.
- River references evidence; no personal DigitalMe/customer data belongs in the public passport.
- Released states require both a Warden decision reference and at least one River receipt reference.
- Follow test-first development: every new Python function must have a failing test observed before implementation.
- Do not add database, API server, ERP, Shopify, QR/NFC, GS1, EU DPP Registry, live Warden, or live River integration in R0.1.

---

## File Structure

```text
smart-textiles/
  pyproject.toml
  README.md
  registry/
    integration-levels.yaml
    integration-methods.yaml
    conductive-platforms.yaml
    capabilities.yaml
    applications.yaml
    code-dictionary.yaml
  contracts/
    product-model.schema.json
    product-passport.schema.json
  compiler/
    compatibility-rules.yaml
  src/smart_textiles/
    __init__.py
    errors.py
    registry.py
    schema_validation.py
    sku.py
    compatibility.py
    passport.py
    release.py
  examples/
    sport-ecg-temperature-shirt.model.yaml
    industrial-thermal-gas-jacket.model.yaml
    invalid-unknown-code.model.yaml
    invalid-missing-contact.model.yaml
    invalid-regulated-evidence.model.yaml
    invalid-duplicate-sku.catalog.yaml
  tests/
    test_registry.py
    test_schema_validation.py
    test_sku.py
    test_compatibility.py
    test_passport.py
    test_release.py
    test_examples.py
.github/workflows/smart-textiles.yml
```

Each Python module owns one concern; YAML is authoritative source data, not embedded duplicate constants.

---

### Task 1: Registry Package and Canonical Taxonomy

**Files:**
- Create: `smart-textiles/pyproject.toml`
- Create: `smart-textiles/src/smart_textiles/__init__.py`
- Create: `smart-textiles/src/smart_textiles/errors.py`
- Create: `smart-textiles/src/smart_textiles/registry.py`
- Create: `smart-textiles/registry/integration-levels.yaml`
- Create: `smart-textiles/registry/integration-methods.yaml`
- Create: `smart-textiles/registry/conductive-platforms.yaml`
- Create: `smart-textiles/registry/capabilities.yaml`
- Create: `smart-textiles/registry/applications.yaml`
- Create: `smart-textiles/registry/code-dictionary.yaml`
- Test: `smart-textiles/tests/test_registry.py`

**Interfaces:**
- Consumes: YAML registry files under `smart-textiles/registry/`.
- Produces: `Registry.load(root: Path) -> Registry`, `Registry.codes(kind: str) -> tuple[str, ...]`, `Registry.entry(kind: str, code: str) -> Mapping[str, Any]`, and `UnknownRegistryCode`.

- [ ] **Step 1: Add project metadata and test dependencies**

Create `smart-textiles/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "genesis-smart-textiles"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["PyYAML>=6.0", "jsonschema>=4.23"]

[project.optional-dependencies]
test = ["pytest>=8.0"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
addopts = "-q"
```

Run:

```bash
cd smart-textiles
python -m pip install -e '.[test]'
```

Expected: package installs without dependency-resolution errors.

- [ ] **Step 2: Write the failing registry test**

Create `tests/test_registry.py`:

```python
from pathlib import Path
import pytest

from smart_textiles.errors import UnknownRegistryCode
from smart_textiles.registry import Registry

ROOT = Path(__file__).parents[1]


def test_registry_loads_canonical_r01_counts_and_labels():
    registry = Registry.load(ROOT / "registry")
    assert registry.codes("integration_levels") == ("FAB", "FBR", "YRN")
    assert registry.codes("integration_methods") == ("EMB", "KNT", "WVN")
    assert registry.codes("conductive_platforms") == ("AG", "CNT", "CPY", "CU", "STL")
    assert len(registry.codes("capabilities")) == 17
    assert registry.entry("capabilities", "ST-F01")["name"] == "ECG / biopotential sensing"
    assert registry.entry("applications", "SPT")["name"] == "Sport / performance"


def test_registry_rejects_unknown_code():
    registry = Registry.load(ROOT / "registry")
    with pytest.raises(UnknownRegistryCode, match="NOPE"):
        registry.entry("capabilities", "NOPE")
```

Run:

```bash
pytest tests/test_registry.py -v
```

Expected: FAIL because `smart_textiles.registry` and registry files do not yet exist.

- [ ] **Step 3: Create canonical registry YAML**

Use list-of-records format `code`, `name`, `class` where applicable.

`integration-levels.yaml`:

```yaml
- code: FBR
  name: Fiber-level
- code: YRN
  name: Yarn-level
- code: FAB
  name: Fabric-level
```

`integration-methods.yaml`:

```yaml
- code: WVN
  name: Woven
- code: KNT
  name: Knitted
- code: EMB
  name: Embroidered
```

`conductive-platforms.yaml`:

```yaml
- code: AG
  name: Silver
- code: STL
  name: Steel
- code: CU
  name: Copper
- code: CNT
  name: Carbon nanotube
- code: CPY
  name: Conductive polymer
```

`applications.yaml`:

```yaml
- code: HLT
  name: Healthcare / clinical monitoring
- code: SPT
  name: Sport / performance
- code: DFR
  name: Defence / first responder
- code: IND
  name: Industrial / workforce safety
- code: HMI
  name: Wearable computing / human-machine interface
```

`capabilities.yaml`:

```yaml
- code: ST-F01
  name: ECG / biopotential sensing
  class: physiological_sensing
- code: ST-F02
  name: Respiration sensing
  class: physiological_sensing
- code: ST-F03
  name: Muscle activity sensing
  class: physiological_sensing
- code: ST-F04
  name: Pressure sensing
  class: mechanical_sensing
- code: ST-F05
  name: Motion / strain sensing
  class: mechanical_sensing
- code: ST-F06
  name: Posture sensing
  class: mechanical_sensing
- code: ST-F07
  name: Skin temperature sensing
  class: thermal_sensing
- code: ST-F08
  name: Sweat lactate sensing
  class: biochemical_sensing
- code: ST-F09
  name: Sweat glucose sensing
  class: biochemical_sensing
- code: ST-F10
  name: Toxic-gas / chemical exposure sensing
  class: environmental_sensing
- code: ST-F11
  name: Thermal-hazard sensing
  class: environmental_sensing
- code: ST-F12
  name: Piezoelectric energy harvesting
  class: energy
- code: ST-F13
  name: Triboelectric energy harvesting
  class: energy
- code: ST-F14
  name: Thermochromic actuation
  class: actuation
- code: ST-F15
  name: Electroactive actuation
  class: actuation
- code: ST-F16
  name: Textile input interface
  class: human_machine_interface
- code: ST-F17
  name: Flexible textile display
  class: human_machine_interface
```

`code-dictionary.yaml`:

```yaml
forms:
  TSH: T-Shirt
  JKT: Jacket
  VST: Vest
  LEG: Legging / trouser
  SCK: Sock
  GLV: Glove
  SLV: Sleeve / band
  HDW: Headwear
  PNL: Textile panel / wrap
power:
  PAS: Passive / no onboard power
  BAT: Battery-powered
  PZO: Piezoelectric harvesting
  TRB: Triboelectric harvesting
capability_short_codes:
  ST-F01: ECG
  ST-F02: RSP
  ST-F03: EMG
  ST-F04: PRS
  ST-F05: STR
  ST-F06: PST
  ST-F07: TMP
  ST-F08: LAC
  ST-F09: GLC
  ST-F10: GAS
  ST-F11: THZ
  ST-F12: PZO
  ST-F13: TRB
  ST-F14: THC
  ST-F15: EAC
  ST-F16: INP
  ST-F17: DSP
```

- [ ] **Step 4: Implement the minimal immutable registry API**

Create `errors.py`:

```python
class SmartTextileError(ValueError):
    pass


class UnknownRegistryCode(SmartTextileError):
    pass
```

Create `registry.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

from .errors import UnknownRegistryCode

FILES = {
    "integration_levels": "integration-levels.yaml",
    "integration_methods": "integration-methods.yaml",
    "conductive_platforms": "conductive-platforms.yaml",
    "capabilities": "capabilities.yaml",
    "applications": "applications.yaml",
}


@dataclass(frozen=True)
class Registry:
    data: Mapping[str, Mapping[str, Mapping[str, Any]]]
    dictionary: Mapping[str, Any]

    @classmethod
    def load(cls, root: Path) -> "Registry":
        loaded = {}
        for kind, filename in FILES.items():
            records = yaml.safe_load((root / filename).read_text(encoding="utf-8"))
            by_code = {record["code"]: MappingProxyType(dict(record)) for record in records}
            if len(by_code) != len(records):
                raise ValueError(f"duplicate registry code in {filename}")
            loaded[kind] = MappingProxyType(by_code)
        dictionary = yaml.safe_load((root / "code-dictionary.yaml").read_text(encoding="utf-8"))
        return cls(MappingProxyType(loaded), MappingProxyType(dictionary))

    def codes(self, kind: str) -> tuple[str, ...]:
        return tuple(sorted(self.data[kind]))

    def entry(self, kind: str, code: str) -> Mapping[str, Any]:
        try:
            return self.data[kind][code]
        except KeyError as exc:
            raise UnknownRegistryCode(f"unknown {kind} code: {code}") from exc
```

Create `__init__.py` with no side effects.

- [ ] **Step 5: Run registry tests**

Run:

```bash
pytest tests/test_registry.py -v
```

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add smart-textiles
git commit -m "feat: add smart textile canonical registry"
```

---

### Task 2: Product Model and Product Passport JSON Schema Validation

**Files:**
- Create: `smart-textiles/contracts/product-model.schema.json`
- Create: `smart-textiles/contracts/product-passport.schema.json`
- Create: `smart-textiles/src/smart_textiles/schema_validation.py`
- Test: `smart-textiles/tests/test_schema_validation.py`

**Interfaces:**
- Consumes: JSON-compatible mappings and schema files under `contracts/`.
- Produces: `validate_document(document: Mapping[str, Any], schema_name: str, schema_root: Path) -> None` and `SchemaValidationError`.

- [ ] **Step 1: Write failing schema-validation tests**

Create `tests/test_schema_validation.py`:

```python
from pathlib import Path
import pytest

from smart_textiles.schema_validation import SchemaValidationError, validate_document

ROOT = Path(__file__).parents[1]

VALID_MODEL = {
    "model_id": "STM-SPT-TSH-0001-R01",
    "platform_id": "STP-0001",
    "application_family": "SPT",
    "form_code": "TSH",
    "smart_architecture": {
        "integration_level": "YRN",
        "integration_method": "KNT",
        "conductive_platform": "AG"
    },
    "capability_ids": ["ST-F01", "ST-F07"],
    "power_code": "TRB",
    "revision": 1,
    "lifecycle_state": "DRAFT_CONFIG"
}


def test_valid_product_model_matches_schema():
    validate_document(VALID_MODEL, "product-model.schema.json", ROOT / "contracts")


def test_model_without_identity_is_rejected():
    invalid = dict(VALID_MODEL)
    invalid.pop("model_id")
    with pytest.raises(SchemaValidationError, match="model_id"):
        validate_document(invalid, "product-model.schema.json", ROOT / "contracts")
```

Run:

```bash
pytest tests/test_schema_validation.py -v
```

Expected: FAIL because schema validation module does not exist.

- [ ] **Step 2: Create the product-model schema**

Create a Draft 2020-12 schema with these exact constraints:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:genesis:smart-textiles:product-model:r0.1",
  "type": "object",
  "required": ["model_id", "platform_id", "application_family", "form_code", "smart_architecture", "capability_ids", "power_code", "revision", "lifecycle_state"],
  "properties": {
    "model_id": {"type": "string", "minLength": 1},
    "platform_id": {"type": "string", "minLength": 1},
    "application_family": {"enum": ["HLT", "SPT", "DFR", "IND", "HMI"]},
    "form_code": {"enum": ["TSH", "JKT", "VST", "LEG", "SCK", "GLV", "SLV", "HDW", "PNL"]},
    "smart_architecture": {
      "type": "object",
      "required": ["integration_level", "integration_method", "conductive_platform"],
      "properties": {
        "integration_level": {"enum": ["FBR", "YRN", "FAB"]},
        "integration_method": {"enum": ["WVN", "KNT", "EMB"]},
        "conductive_platform": {"enum": ["AG", "STL", "CU", "CNT", "CPY"]},
        "body_contact_zone": {"type": "string", "minLength": 1}
      },
      "additionalProperties": true
    },
    "capability_ids": {
      "type": "array",
      "minItems": 1,
      "uniqueItems": true,
      "items": {"type": "string", "pattern": "^ST-F(0[1-9]|1[0-7])$"}
    },
    "power_code": {"enum": ["PAS", "BAT", "PZO", "TRB"]},
    "revision": {"type": "integer", "minimum": 1},
    "lifecycle_state": {"enum": ["DRAFT_CONFIG", "PROTOTYPE_APPROVED", "ENGINEERING_VALIDATED", "MODEL_RELEASED", "BATCH_RELEASED", "ITEM_ACTIVE", "IN_SERVICE", "REPAIR", "REFURBISH", "QUARANTINE", "RECALL", "RETIRED", "RECYCLED", "DISPOSED"]},
    "intended_use": {"type": "string"},
    "regulatory_claim_class": {"enum": ["none", "medical", "ppe", "other_regulated"]},
    "regulatory_evidence_ids": {"type": "array", "items": {"type": "string", "minLength": 1}},
    "warden_decision_id": {"type": "string", "minLength": 1},
    "river_receipt_ids": {"type": "array", "items": {"type": "string", "minLength": 1}}
  },
  "additionalProperties": true
}
```

- [ ] **Step 3: Create the product-passport schema**

Create a Draft 2020-12 schema requiring the approved top-level domains while allowing additive fields:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:genesis:smart-textiles:product-passport:r0.1",
  "type": "object",
  "required": ["passport", "identity", "application", "textile", "smart_architecture", "capabilities", "power", "electronics", "performance", "safety", "manufacturing", "traceability", "circularity", "evidence"],
  "properties": {
    "passport": {
      "type": "object",
      "required": ["passport_id", "passport_level", "schema_version", "status"],
      "properties": {
        "passport_id": {"type": "string", "minLength": 1},
        "passport_level": {"enum": ["model", "batch", "item"]},
        "schema_version": {"const": "0.1"},
        "status": {"type": "string", "minLength": 1},
        "effective_from": {"type": "string"},
        "supersedes": {"type": ["string", "null"]}
      },
      "additionalProperties": true
    },
    "identity": {
      "type": "object",
      "required": ["platform_id", "model_id", "human_readable_sku"],
      "properties": {
        "platform_id": {"type": "string", "minLength": 1},
        "capability_bundle_id": {"type": ["string", "null"]},
        "model_id": {"type": "string", "minLength": 1},
        "commercial_variant_id": {"type": ["string", "null"]},
        "batch_id": {"type": ["string", "null"]},
        "item_id": {"type": ["string", "null"]},
        "human_readable_sku": {"type": "string", "minLength": 1},
        "persistent_product_identifier": {"type": ["string", "null"]}
      },
      "additionalProperties": true
    },
    "application": {"type": "object"},
    "textile": {"type": "object"},
    "smart_architecture": {"type": "object"},
    "capabilities": {"type": "object"},
    "power": {"type": "object"},
    "electronics": {"type": "object"},
    "performance": {"type": "object"},
    "safety": {"type": "object"},
    "manufacturing": {"type": "object"},
    "traceability": {"type": "object"},
    "circularity": {"type": "object"},
    "evidence": {"type": "object"}
  },
  "additionalProperties": true
}
```

- [ ] **Step 4: Implement schema validation wrapper**

Add to `errors.py`:

```python
class SchemaValidationError(SmartTextileError):
    pass
```

Create `schema_validation.py`:

```python
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .errors import SchemaValidationError


def validate_document(document: Mapping[str, Any], schema_name: str, schema_root: Path) -> None:
    schema = json.loads((schema_root / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        path = ".".join(str(part) for part in error.path) or "<root>"
        raise SchemaValidationError(f"{path}: {error.message}")
```

- [ ] **Step 5: Run schema tests**

```bash
pytest tests/test_schema_validation.py -v
```

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add smart-textiles/contracts smart-textiles/src/smart_textiles/errors.py smart-textiles/src/smart_textiles/schema_validation.py smart-textiles/tests/test_schema_validation.py
git commit -m "feat: validate smart textile model and passport schemas"
```

---

### Task 3: Deterministic Human-Readable SKU Compiler

**Files:**
- Create: `smart-textiles/src/smart_textiles/sku.py`
- Test: `smart-textiles/tests/test_sku.py`

**Interfaces:**
- Consumes: product-model mapping and `Registry`.
- Produces: `compile_engineering_sku(model: Mapping[str, Any], registry: Registry) -> str` and `compile_catalog(models: Iterable[Mapping[str, Any]], registry: Registry) -> dict[str, Mapping[str, Any]]`.

- [ ] **Step 1: Write failing compiler tests**

```python
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
```

Run:

```bash
pytest tests/test_sku.py -v
```

Expected: FAIL because `smart_textiles.sku` does not exist.

- [ ] **Step 2: Add code-dictionary lookup helpers to Registry**

Extend `Registry`:

```python
    def dictionary_entry(self, group: str, code: str) -> str:
        try:
            return self.dictionary[group][code]
        except KeyError as exc:
            raise UnknownRegistryCode(f"unknown {group} code: {code}") from exc
```

- [ ] **Step 3: Implement minimal SKU compiler**

Create `sku.py`:

```python
from typing import Any, Iterable, Mapping

from .errors import SmartTextileError
from .registry import Registry


def compile_engineering_sku(model: Mapping[str, Any], registry: Registry) -> str:
    use = model["application_family"]
    registry.entry("applications", use)
    form = model["form_code"]
    registry.dictionary_entry("forms", form)

    architecture = model["smart_architecture"]
    integration = architecture["integration_level"]
    method = architecture["integration_method"]
    material = architecture["conductive_platform"]
    registry.entry("integration_levels", integration)
    registry.entry("integration_methods", method)
    registry.entry("conductive_platforms", material)

    capability_ids = sorted(model["capability_ids"])
    for capability_id in capability_ids:
        registry.entry("capabilities", capability_id)
    capability_set = "+".join(
        registry.dictionary_entry("capability_short_codes", capability_id)
        for capability_id in capability_ids
    )

    power = model["power_code"]
    registry.dictionary_entry("power", power)
    revision = int(model["revision"])
    if revision < 1:
        raise SmartTextileError("revision must be >= 1")

    return f"ST-{use}-{form}-{integration}-{method}-{capability_set}-{material}-{power}-R{revision:02d}"


def compile_catalog(models: Iterable[Mapping[str, Any]], registry: Registry) -> dict[str, Mapping[str, Any]]:
    compiled = {}
    for model in models:
        sku = compile_engineering_sku(model, registry)
        if sku in compiled:
            raise SmartTextileError(f"duplicate engineering SKU: {sku}")
        compiled[sku] = model
    return compiled
```

- [ ] **Step 4: Run compiler tests**

```bash
pytest tests/test_sku.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Run registry regression tests**

```bash
pytest tests/test_registry.py tests/test_sku.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add smart-textiles/src/smart_textiles/registry.py smart-textiles/src/smart_textiles/sku.py smart-textiles/tests/test_sku.py
git commit -m "feat: compile deterministic smart textile SKUs"
```

---

### Task 4: Starter Compatibility Rule Engine

**Files:**
- Create: `smart-textiles/compiler/compatibility-rules.yaml`
- Create: `smart-textiles/src/smart_textiles/compatibility.py`
- Test: `smart-textiles/tests/test_compatibility.py`

**Interfaces:**
- Consumes: model mapping, Registry, rules YAML.
- Produces: `CompatibilityResult(state: str, reason_codes: tuple[str, ...])` and `evaluate_compatibility(model, registry, rules_path) -> CompatibilityResult`.

- [ ] **Step 1: Write failing compatibility tests**

```python
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
```

Run:

```bash
pytest tests/test_compatibility.py -v
```

Expected: FAIL because compatibility engine does not exist.

- [ ] **Step 2: Create explicit starter rules**

`compatibility-rules.yaml`:

```yaml
body_contact_required:
  - ST-F01
  - ST-F03
  - ST-F04
  - ST-F07
  - ST-F08
  - ST-F09

power_profile_required:
  - ST-F15
  - ST-F16
  - ST-F17

prototype_only_capabilities:
  ST-F08: R01_EVIDENCE_MATURITY
  ST-F09: R01_EVIDENCE_MATURITY

regulated_claim_classes:
  - medical
  - ppe
  - other_regulated
```

These are R0.1 governance/validation rules, not claims that other engineering architectures are scientifically impossible.

- [ ] **Step 3: Implement compatibility evaluator**

Create `compatibility.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .registry import Registry


@dataclass(frozen=True)
class CompatibilityResult:
    state: str
    reason_codes: tuple[str, ...]


def evaluate_compatibility(model: Mapping[str, Any], registry: Registry, rules_path: Path) -> CompatibilityResult:
    for capability_id in model["capability_ids"]:
        registry.entry("capabilities", capability_id)

    rules = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    reasons: list[str] = []
    architecture = model["smart_architecture"]
    capabilities = set(model["capability_ids"])

    if capabilities.intersection(rules["body_contact_required"]) and not architecture.get("body_contact_zone"):
        reasons.append("BODY_CONTACT_ZONE_REQUIRED")

    if capabilities.intersection(rules["power_profile_required"]) and not model.get("power_profile"):
        reasons.append("POWER_PROFILE_REQUIRED")

    claim = model.get("regulatory_claim_class", "none")
    if claim in rules["regulated_claim_classes"] and not model.get("regulatory_evidence_ids"):
        reasons.append("REGULATORY_EVIDENCE_REQUIRED")

    if reasons:
        return CompatibilityResult("REJECTED_CONFIG", tuple(sorted(set(reasons))))

    prototype_reasons = {
        rules["prototype_only_capabilities"][capability]
        for capability in capabilities
        if capability in rules["prototype_only_capabilities"]
    }
    if prototype_reasons:
        return CompatibilityResult("PROTOTYPE_ONLY", tuple(sorted(prototype_reasons)))

    return CompatibilityResult("VALIDATED_CONFIG", ())
```

- [ ] **Step 4: Run compatibility tests**

```bash
pytest tests/test_compatibility.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add smart-textiles/compiler smart-textiles/src/smart_textiles/compatibility.py smart-textiles/tests/test_compatibility.py
git commit -m "feat: add smart textile compatibility rules"
```

---

### Task 5: Hierarchical Passport Assembly and Non-Mutating Inheritance

**Files:**
- Create: `smart-textiles/src/smart_textiles/passport.py`
- Test: `smart-textiles/tests/test_passport.py`

**Interfaces:**
- Consumes: a model passport seed and optional variant/batch/item overlays.
- Produces: `deep_merge(parent, child) -> dict[str, Any]` and `assemble_passport(model, *, variant=None, batch=None, item=None) -> dict[str, Any]`.

- [ ] **Step 1: Write failing inheritance tests**

```python
from copy import deepcopy

from smart_textiles.passport import assemble_passport

MODEL = {
    "passport": {"passport_id": "DPP-MODEL-001", "passport_level": "model", "schema_version": "0.1", "status": "ENGINEERING_VALIDATED"},
    "identity": {"platform_id": "STP-0001", "model_id": "STM-0001-R01", "human_readable_sku": "ST-SPT-TSH-YRN-KNT-ECG+TMP-AG-TRB-R01"},
    "application": {"application_family": "SPT", "intended_use": "athletic monitoring"},
    "textile": {"fibre_composition": "polyamide/elastane"},
    "smart_architecture": {"integration_level": "YRN", "integration_method": "KNT", "conductive_platform": "AG"},
    "capabilities": {"capability_ids": ["ST-F01", "ST-F07"]},
    "power": {"source_types": ["TRB"]},
    "electronics": {"firmware_version": "1.0.0"},
    "performance": {},
    "safety": {},
    "manufacturing": {},
    "traceability": {},
    "circularity": {},
    "evidence": {"river_receipt_ids": []}
}


def test_variant_and_item_inherit_without_mutating_model():
    original = deepcopy(MODEL)
    variant = {"identity": {"commercial_variant_id": "VAR-BLK-M"}, "commercial": {"colour": "black", "size": "M"}}
    item = {"passport": {"passport_id": "DPP-ITEM-001", "passport_level": "item"}, "identity": {"item_id": "ITEM-0001"}, "electronics": {"firmware_version": "1.0.1"}}
    result = assemble_passport(MODEL, variant=variant, item=item)
    assert result["identity"]["model_id"] == "STM-0001-R01"
    assert result["identity"]["commercial_variant_id"] == "VAR-BLK-M"
    assert result["identity"]["item_id"] == "ITEM-0001"
    assert result["electronics"]["firmware_version"] == "1.0.1"
    assert MODEL == original


def test_batch_overlay_preserves_model_identity():
    batch = {"identity": {"batch_id": "BATCH-0001"}, "manufacturing": {"production_line": "LINE-07"}}
    result = assemble_passport(MODEL, batch=batch)
    assert result["identity"]["model_id"] == "STM-0001-R01"
    assert result["identity"]["batch_id"] == "BATCH-0001"
    assert result["manufacturing"]["production_line"] == "LINE-07"
```

Run:

```bash
pytest tests/test_passport.py -v
```

Expected: FAIL because passport module does not exist.

- [ ] **Step 2: Implement recursive non-mutating merge**

Create `passport.py`:

```python
from copy import deepcopy
from typing import Any, Mapping


def deep_merge(parent: Mapping[str, Any], child: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(parent))
    for key, value in child.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def assemble_passport(
    model: Mapping[str, Any],
    *,
    variant: Mapping[str, Any] | None = None,
    batch: Mapping[str, Any] | None = None,
    item: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = deepcopy(dict(model))
    for overlay in (variant, batch, item):
        if overlay is not None:
            result = deep_merge(result, overlay)
    return result
```

- [ ] **Step 3: Run passport tests**

```bash
pytest tests/test_passport.py -v
```

Expected: 2 PASS.

- [ ] **Step 4: Run schema validation against an assembled item**

Extend `test_passport.py` with:

```python
from pathlib import Path
from smart_textiles.schema_validation import validate_document

ROOT = Path(__file__).parents[1]


def test_assembled_item_remains_passport_schema_valid():
    item = {"passport": {"passport_id": "DPP-ITEM-001", "passport_level": "item"}, "identity": {"item_id": "ITEM-0001"}}
    result = assemble_passport(MODEL, item=item)
    validate_document(result, "product-passport.schema.json", ROOT / "contracts")
```

Run:

```bash
pytest tests/test_passport.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add smart-textiles/src/smart_textiles/passport.py smart-textiles/tests/test_passport.py
git commit -m "feat: assemble hierarchical smart textile passports"
```

---

### Task 6: Warden and River Release Readiness Guard

**Files:**
- Create: `smart-textiles/src/smart_textiles/release.py`
- Test: `smart-textiles/tests/test_release.py`

**Interfaces:**
- Consumes: product-model or passport mapping.
- Produces: `assert_release_ready(document: Mapping[str, Any]) -> None` and `ReleaseReadinessError`.

- [ ] **Step 1: Write failing release-gate tests**

```python
import pytest

from smart_textiles.errors import ReleaseReadinessError
from smart_textiles.release import assert_release_ready


def test_released_model_requires_warden_and_river_references():
    model = {"lifecycle_state": "MODEL_RELEASED", "regulatory_claim_class": "none", "river_receipt_ids": []}
    with pytest.raises(ReleaseReadinessError) as exc:
        assert_release_ready(model)
    assert set(exc.value.reason_codes) == {"WARDEN_DECISION_REQUIRED", "RIVER_RECEIPT_REQUIRED"}


def test_released_model_with_authority_and_evidence_passes():
    model = {
        "lifecycle_state": "MODEL_RELEASED",
        "regulatory_claim_class": "none",
        "warden_decision_id": "WD-ST-0001",
        "river_receipt_ids": ["RVR-ST-0001"]
    }
    assert_release_ready(model)


def test_regulated_released_model_requires_regulatory_evidence():
    model = {
        "lifecycle_state": "MODEL_RELEASED",
        "regulatory_claim_class": "medical",
        "warden_decision_id": "WD-ST-0001",
        "river_receipt_ids": ["RVR-ST-0001"],
        "regulatory_evidence_ids": []
    }
    with pytest.raises(ReleaseReadinessError) as exc:
        assert_release_ready(model)
    assert exc.value.reason_codes == ("REGULATORY_EVIDENCE_REQUIRED",)
```

Run:

```bash
pytest tests/test_release.py -v
```

Expected: FAIL because release module and error type do not exist.

- [ ] **Step 2: Add release error type**

Extend `errors.py`:

```python
class ReleaseReadinessError(SmartTextileError):
    def __init__(self, reason_codes: tuple[str, ...]):
        self.reason_codes = reason_codes
        super().__init__(", ".join(reason_codes))
```

- [ ] **Step 3: Implement release readiness guard**

Create `release.py`:

```python
from typing import Any, Mapping

from .errors import ReleaseReadinessError

RELEASED_STATES = {"MODEL_RELEASED", "BATCH_RELEASED", "ITEM_ACTIVE"}
REGULATED_CLAIMS = {"medical", "ppe", "other_regulated"}


def assert_release_ready(document: Mapping[str, Any]) -> None:
    state = document.get("lifecycle_state") or document.get("passport", {}).get("status")
    if state not in RELEASED_STATES:
        return

    reasons: list[str] = []
    if not document.get("warden_decision_id") and not document.get("evidence", {}).get("warden_decision_id"):
        reasons.append("WARDEN_DECISION_REQUIRED")

    river_ids = document.get("river_receipt_ids") or document.get("evidence", {}).get("river_receipt_ids") or []
    if not river_ids:
        reasons.append("RIVER_RECEIPT_REQUIRED")

    claim = document.get("regulatory_claim_class") or document.get("application", {}).get("regulatory_claim_class", "none")
    regulatory_ids = document.get("regulatory_evidence_ids") or document.get("evidence", {}).get("conformity_record_ids") or []
    if claim in REGULATED_CLAIMS and not regulatory_ids:
        reasons.append("REGULATORY_EVIDENCE_REQUIRED")

    if reasons:
        raise ReleaseReadinessError(tuple(sorted(reasons)))
```

- [ ] **Step 4: Run release tests**

```bash
pytest tests/test_release.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Run all unit tests**

```bash
pytest -v
```

Expected: all tests from Tasks 1-6 PASS.

- [ ] **Step 6: Commit**

```bash
git add smart-textiles/src/smart_textiles/errors.py smart-textiles/src/smart_textiles/release.py smart-textiles/tests/test_release.py
git commit -m "feat: require Warden and River evidence for release"
```

---

### Task 7: Reference Products and End-to-End Configuration Tests

**Files:**
- Create: `smart-textiles/examples/sport-ecg-temperature-shirt.model.yaml`
- Create: `smart-textiles/examples/industrial-thermal-gas-jacket.model.yaml`
- Create: `smart-textiles/examples/invalid-unknown-code.model.yaml`
- Create: `smart-textiles/examples/invalid-missing-contact.model.yaml`
- Create: `smart-textiles/examples/invalid-regulated-evidence.model.yaml`
- Create: `smart-textiles/examples/invalid-duplicate-sku.catalog.yaml`
- Create: `smart-textiles/tests/test_examples.py`
- Create: `smart-textiles/README.md`

**Interfaces:**
- Consumes: registry, schema validator, SKU compiler, compatibility engine and release guard.
- Produces: two passing reference configurations and four named negative fixtures proving failure behavior.

- [ ] **Step 1: Write the failing end-to-end test before fixtures exist**

```python
from pathlib import Path
import yaml

from smart_textiles.compatibility import evaluate_compatibility
from smart_textiles.registry import Registry
from smart_textiles.schema_validation import validate_document
from smart_textiles.sku import compile_engineering_sku

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
```

Run:

```bash
pytest tests/test_examples.py -v
```

Expected: FAIL because example files do not exist.

- [ ] **Step 2: Create the positive reference fixtures**

`sport-ecg-temperature-shirt.model.yaml`:

```yaml
model_id: STM-SPT-TSH-0001-R01
platform_id: STP-SPORT-PHYSIO-0001
application_family: SPT
form_code: TSH
smart_architecture:
  integration_level: YRN
  integration_method: KNT
  conductive_platform: AG
  body_contact_zone: chest
capability_ids:
  - ST-F01
  - ST-F07
power_code: TRB
revision: 1
lifecycle_state: ENGINEERING_VALIDATED
intended_use: Athletic physiological monitoring prototype/reference model
regulatory_claim_class: none
regulatory_evidence_ids: []
river_receipt_ids: []
```

`industrial-thermal-gas-jacket.model.yaml`:

```yaml
model_id: STM-IND-JKT-0001-R01
platform_id: STP-IND-SAFETY-0001
application_family: IND
form_code: JKT
smart_architecture:
  integration_level: FAB
  integration_method: EMB
  conductive_platform: CU
capability_ids:
  - ST-F10
  - ST-F11
power_code: BAT
revision: 1
lifecycle_state: ENGINEERING_VALIDATED
intended_use: Industrial environmental hazard monitoring reference model
regulatory_claim_class: none
regulatory_evidence_ids: []
river_receipt_ids: []
```

- [ ] **Step 3: Add negative fixture tests with exact failure reasons**

Extend `test_examples.py`:

```python
import pytest

from smart_textiles.errors import SchemaValidationError, SmartTextileError, UnknownRegistryCode
from smart_textiles.sku import compile_catalog


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
```

- [ ] **Step 4: Create negative fixtures**

`invalid-unknown-code.model.yaml`: copy the sport model but set `smart_architecture.conductive_platform: GOLD`.

`invalid-missing-contact.model.yaml`: use the sport model with `ST-F01` but omit `body_contact_zone`.

`invalid-regulated-evidence.model.yaml`: use the sport model with `regulatory_claim_class: medical` and `regulatory_evidence_ids: []`.

`invalid-duplicate-sku.catalog.yaml`:

```yaml
models:
  - application_family: SPT
    form_code: TSH
    smart_architecture:
      integration_level: YRN
      integration_method: KNT
      conductive_platform: AG
    capability_ids: [ST-F01, ST-F07]
    power_code: TRB
    revision: 1
  - application_family: SPT
    form_code: TSH
    smart_architecture:
      integration_level: YRN
      integration_method: KNT
      conductive_platform: AG
    capability_ids: [ST-F07, ST-F01]
    power_code: TRB
    revision: 1
```

- [ ] **Step 5: Run reference and negative tests**

```bash
pytest tests/test_examples.py -v
```

Expected: 6 PASS.

- [ ] **Step 6: Add operator README**

`smart-textiles/README.md` must document:
- purpose and `DPP-ready` status;
- the 45 base architecture calculation;
- the 17 canonical capabilities;
- why the 5,898,195 theoretical upper bound is not pre-generated;
- SKU grammar `ST-[USE]-[FORM]-[INT]-[METHOD]-[CAPSET]-[MAT]-[POWER]-R[REV]`;
- model -> variant -> batch -> item inheritance;
- exact local commands:

```bash
cd smart-textiles
python -m pip install -e '.[test]'
pytest -v
```

- [ ] **Step 7: Commit**

```bash
git add smart-textiles/examples smart-textiles/tests/test_examples.py smart-textiles/README.md
git commit -m "test: add smart textile reference passports"
```

---

### Task 8: CI Gate and Final Verification

**Files:**
- Create: `.github/workflows/smart-textiles.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: complete `smart-textiles/` subsystem.
- Produces: repeatable Python 3.11 CI check and root-repository navigation link.

- [ ] **Step 1: Add GitHub Actions workflow**

Create `.github/workflows/smart-textiles.yml`:

```yaml
name: Smart Textiles R0.1

on:
  pull_request:
    paths:
      - "smart-textiles/**"
      - ".github/workflows/smart-textiles.yml"
  push:
    paths:
      - "smart-textiles/**"
      - ".github/workflows/smart-textiles.yml"

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install
        working-directory: smart-textiles
        run: python -m pip install -e '.[test]'
      - name: Test
        working-directory: smart-textiles
        run: pytest -v
```

- [ ] **Step 2: Update root README navigation**

Add a section without changing existing Alpha-control-plane wording:

```markdown
## Smart Textile Product Passport Registry

The R0.1 smart-textile taxonomy, compatibility compiler, human-readable SKU grammar, and DPP-ready passport contracts live under `smart-textiles/`.

- Design: `docs/superpowers/specs/2026-09-09-smart-textile-product-passport-registry-design.md`
- Implementation plan: `docs/superpowers/plans/2026-09-09-smart-textile-product-passport-registry.md`
- Operator guide: `smart-textiles/README.md`
```

- [ ] **Step 3: Run the complete test suite for the new subsystem**

```bash
cd smart-textiles
pytest -v
```

Expected: all registry, schema, SKU, compatibility, passport, release and example tests PASS with no warnings or errors.

- [ ] **Step 4: Verify canonical counts explicitly**

Run:

```bash
python - <<'PY'
from pathlib import Path
from smart_textiles.registry import Registry
r = Registry.load(Path('registry'))
assert len(r.codes('integration_levels')) == 3
assert len(r.codes('integration_methods')) == 3
assert len(r.codes('conductive_platforms')) == 5
assert len(r.codes('capabilities')) == 17
assert len(r.codes('applications')) == 5
print('registry counts verified')
PY
```

Expected output:

```text
registry counts verified
```

- [ ] **Step 5: Verify the two reference SKUs from executable code**

Run:

```bash
python - <<'PY'
from pathlib import Path
import yaml
from smart_textiles.registry import Registry
from smart_textiles.sku import compile_engineering_sku
root = Path('.')
r = Registry.load(root / 'registry')
for name in ('sport-ecg-temperature-shirt.model.yaml', 'industrial-thermal-gas-jacket.model.yaml'):
    model = yaml.safe_load((root / 'examples' / name).read_text())
    print(name, compile_engineering_sku(model, r))
PY
```

Expected output contains:

```text
ST-SPT-TSH-YRN-KNT-ECG+TMP-AG-TRB-R01
ST-IND-JKT-FAB-EMB-GAS+THZ-CU-BAT-R01
```

- [ ] **Step 6: Commit final CI/docs gate**

```bash
git add .github/workflows/smart-textiles.yml README.md
git commit -m "ci: verify smart textile registry r0.1"
```

- [ ] **Step 7: Final branch verification**

```bash
git status --short
git log --oneline --max-count=8
```

Expected: clean working tree and a sequence of focused commits for registry, schemas, SKU compiler, compatibility engine, passport inheritance, release guard, reference fixtures and CI.

---

## Spec Coverage Self-Review

- Canonical 3 x 3 x 5 architecture axes: Task 1.
- Seventeen capability identities and five applications: Task 1.
- Human-readable English dictionary and SKU grammar: Tasks 1 and 3.
- No pre-generation of theoretical multi-capability space: global constraint; compiler is on-demand in Task 3.
- Product-model and passport contracts: Task 2.
- Compatibility states `VALIDATED_CONFIG`, `PROTOTYPE_ONLY`, `REJECTED_CONFIG`: Task 4.
- Hierarchical model/variant/batch/item inheritance without silent mutation: Task 5.
- Warden and River mandatory at release states: Task 6.
- Two positive and four negative reference fixtures: Task 7.
- Executable verification and CI: Task 8.
- Deferred integrations remain absent from this plan.

## Execution Boundary

This plan intentionally stops before live Alpha deployment. The remote Alpha station must be online and separately qualified before installing or running this subsystem there. GitHub implementation can proceed independently; Alpha deployment becomes a later governed execution step with its own Warden/River evidence.