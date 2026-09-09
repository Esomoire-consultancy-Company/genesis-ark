# Smart Textile Product Passport Registry — Design R0.1

## Status
Approved direction from the September 9, 2026 smart-textile SKU and product-passport design discussion. This document converts the IEEE Smart Textiles taxonomy into a Genesis-native registry and configuration model.

## Repository Role
`genesis-ark` is the root orchestration repository for Genesis/VSR. This design adds a Smart Textile Registry contract without binding the first release to a specific UI, database engine, ERP, marketplace, or factory system.

## Objective
Create a governed registry that can:

1. represent smart-textile engineering architectures;
2. represent reusable sensing, actuation, energy and interface capabilities;
3. compile only valid product configurations;
4. issue human-readable engineering SKU identities;
5. separate model, variant, batch and serialized-item identity;
6. generate DPP-ready product passport records;
7. preserve material, electronics, software and manufacturing genealogy;
8. let Warden authorize configuration and lifecycle transitions;
9. let River preserve evidence for issuance, testing, manufacturing and change;
10. remain additive when textile-specific EU DPP requirements are finalized.

## Source Taxonomy
IEEE Technology Navigator, `Smart Textiles`, retrieved September 9, 2026, is the initial technical taxonomy anchor.

The source explicitly distinguishes:
- fiber-, yarn- and fabric-level integration;
- woven, knitted and embroidered integration;
- conductive silver, steel, copper, carbon nanotube and conductive polymer structures;
- textile electrodes and biopotential sensing;
- pressure, movement/posture, temperature and sweat-metabolite sensing;
- piezoelectric and triboelectric energy harvesting;
- thermochromic and electroactive actuation;
- clinical, athletic, military/first-responder, wearable-computing and industrial-safety applications.

IEEE also identifies washability, mechanical robustness, electrode placement, contact pressure, fabric construction, signal quality and motion artifacts as material engineering concerns. These therefore belong in the passport evidence model rather than being treated only as descriptive merchandising data.

## Regulatory Design Basis
The registry is DPP-ready, not declared textile-DPP-compliant at R0.1.

The ESPR framework permits DPP granularity at product-model, batch or individual-item level and requires persistent unique identifiers, interoperable structured data and differentiated access. Textile-apparel-specific requirements are still being finalized through a future delegated act. R0.1 therefore keeps regulatory fields modular and versioned.

Personal customer data must remain outside the public product passport unless there is a separate lawful and explicit consent basis. DigitalMe session identity is an authority context, not a public passport field.

## Design Alternatives

### A. Flat commercial SKU registry
Every size, colour and functional configuration receives a fully duplicated passport.

Rejected because it creates large-scale duplication of engineering, material, test and conformity data and makes corrections difficult to propagate safely.

### B. Hierarchical configuration and passport registry
Selected.

Hierarchy:

```text
Smart Textile Platform
  -> Capability Bundle
    -> Product Model
      -> Commercial Variant
        -> Production Batch
          -> Serialized Item
```

Engineering and compliance data are inherited downward unless explicitly overridden by a versioned child record.

### C. Capability-only registry
Capabilities are registered, but material architecture and integration method are treated as free-form product metadata.

Rejected because conductivity, washability, repairability, recyclability, signal behavior and manufacturing evidence materially depend on textile architecture.

## Canonical Configuration Axes

### Integration Level
- `FBR` — Fiber-level
- `YRN` — Yarn-level
- `FAB` — Fabric-level

### Integration Method
- `WVN` — Woven
- `KNT` — Knitted
- `EMB` — Embroidered

### Conductive Platform
- `AG` — Silver
- `STL` — Steel
- `CU` — Copper
- `CNT` — Carbon nanotube
- `CPY` — Conductive polymer

The initial base engineering architecture space is therefore:

`3 integration levels x 3 integration methods x 5 conductive platforms = 45 base architectures`.

## Capability Registry R0.1

| Capability ID | English Name | Class |
|---|---|---|
| `ST-F01` | ECG / biopotential sensing | physiological sensing |
| `ST-F02` | Respiration sensing | physiological sensing |
| `ST-F03` | Muscle activity sensing | physiological sensing |
| `ST-F04` | Pressure sensing | mechanical sensing |
| `ST-F05` | Motion / strain sensing | mechanical sensing |
| `ST-F06` | Posture sensing | mechanical sensing |
| `ST-F07` | Skin temperature sensing | thermal sensing |
| `ST-F08` | Sweat lactate sensing | biochemical sensing |
| `ST-F09` | Sweat glucose sensing | biochemical sensing |
| `ST-F10` | Toxic-gas / chemical exposure sensing | environmental sensing |
| `ST-F11` | Thermal-hazard sensing | environmental sensing |
| `ST-F12` | Piezoelectric energy harvesting | energy |
| `ST-F13` | Triboelectric energy harvesting | energy |
| `ST-F14` | Thermochromic actuation | actuation |
| `ST-F15` | Electroactive actuation | actuation |
| `ST-F16` | Textile input interface | human-machine interface |
| `ST-F17` | Flexible textile display | human-machine interface |

Capability records are immutable identities. New knowledge changes metadata by version or supersession; it does not recycle an existing capability ID for another meaning.

## Application Registry R0.1

Canonical application families:

- `HLT` — Healthcare / clinical monitoring
- `SPT` — Sport / performance
- `DFR` — Defence / first responder
- `IND` — Industrial / workforce safety
- `HMI` — Wearable computing / human-machine interface

Additional applications are additive and must not rewrite these identifiers.

## Configuration-Space Mathematics

### Single-function engineering roots
`45 base architectures x 17 capabilities = 765` theoretical single-function engineering configurations.

### Multi-capability theoretical upper bound
If every non-empty combination of the 17 capabilities were allowed on every architecture:

`45 x (2^17 - 1) = 5,898,195` theoretical engineering configurations.

This is deliberately treated as an upper bound, not a manufacturing target. Many combinations will be physically incompatible, commercially pointless, unsafe, redundant or uneconomic.

The registry therefore MUST NOT pre-generate every combination. It stores canonical axes and compiles configurations on demand through compatibility rules.

## Compatibility Compiler

A valid engineering configuration is produced only when all required rules pass.

Initial rule classes:

1. **architecture compatibility** — capability can be implemented at the selected integration level/method;
2. **material compatibility** — conductive platform supports the electrical/chemical/mechanical requirement;
3. **body-contact compatibility** — skin-contact capabilities have valid contact-zone and material requirements;
4. **power compatibility** — source, storage and peak-load requirements are feasible;
5. **signal compatibility** — electrode/sensor geometry and placement can meet declared signal targets;
6. **washability compatibility** — laundering method and cycle target are supported;
7. **manufacturing compatibility** — selected mill/factory process can execute the configuration;
8. **application compatibility** — capability bundle is permitted for the declared use case;
9. **safety compatibility** — electrical, thermal, chemical and mechanical limits pass;
10. **regulatory-claim compatibility** — medical, PPE or other regulated claims require the corresponding evidence state.

Compiler output states:
- `VALIDATED_CONFIG`
- `VALIDATED_WITH_CONDITIONS`
- `PROTOTYPE_ONLY`
- `REJECTED_CONFIG`

Warden decides whether a requested transition may proceed; the compiler itself does not grant authority.

## Human-Readable SKU Grammar

Engineering model SKU:

`ST-[USE]-[FORM]-[INT]-[METHOD]-[CAPSET]-[MAT]-[POWER]-R[REV]`

Example:

`ST-SPT-TSH-YRN-KNT-ECG+TMP-AG-TRB-R01`

English dictionary:
- `ST` — Smart Textile
- `SPT` — Sport
- `TSH` — T-Shirt
- `YRN` — Yarn-integrated
- `KNT` — Knitted
- `ECG+TMP` — ECG plus temperature sensing
- `AG` — Silver conductive platform
- `TRB` — Triboelectric power support
- `R01` — Engineering revision 01

Machine identifiers may use UUIDs, hashes or other globally unique identifiers underneath, but every registry object MUST also expose a stable English name and human-readable code.

## Identity Hierarchy

### 1. Smart Textile Platform
Defines common architecture, material system and capability technology family.

### 2. Capability Bundle
Defines the ordered set of capabilities and their configuration constraints.

### 3. Product Model
Defines one technical product design. This is the main engineering/DPP inheritance root.

### 4. Commercial Variant
Defines merchandising differences such as size, colour, fit and region where those changes do not alter the underlying engineering design.

### 5. Production Batch
Defines the manufacturing lot, plant, line, time window, incoming material lots and process evidence.

### 6. Serialized Item
Defines a single physical product when item-level identity is required, especially for electronics, calibration, repair, firmware state, warranty or regulated traceability.

## Product Passport Contract

Minimum top-level domains:

```yaml
passport:
  passport_id:
  passport_level: model | batch | item
  schema_version:
  status:
  effective_from:
  supersedes:

identity:
  platform_id:
  capability_bundle_id:
  model_id:
  commercial_variant_id:
  batch_id:
  item_id:
  human_readable_sku:
  persistent_product_identifier:

application:
  application_family:
  intended_use:
  prohibited_use:
  regulatory_claim_class:

textile:
  fibre_composition:
  yarn_specification:
  fabric_structure:
  gsm:
  construction_method:
  dyes:
  finishes:

smart_architecture:
  integration_level:
  integration_method:
  conductive_platform:
  conductive_pattern:
  sensor_locations:
  actuator_locations:
  detachable_modules:

capabilities:
  capability_ids: []
  measured_parameters: []
  measurement_ranges: []
  accuracy_targets: []
  sampling_profiles: []

power:
  source_types: []
  storage:
  charging:
  harvesting:
  power_budget:

electronics:
  controller:
  communications: []
  module_ids: []
  firmware_version:
  software_version:

performance:
  signal_quality:
  calibration:
  wash_cycle_rating:
  abrasion_rating:
  bend_rating:
  stretch_rating:
  environmental_limits:

safety:
  electrical:
  thermal:
  chemical:
  skin_contact:
  warnings: []

manufacturing:
  fibre_supplier:
  yarn_supplier:
  fabric_mill:
  dyeing_finishing_unit:
  electronics_supplier:
  garment_factory:
  production_line:
  manufacturing_location_id:

traceability:
  material_lot_ids: []
  component_lot_ids: []
  production_started_at:
  production_completed_at:

circularity:
  repairability:
  electronics_removal:
  battery_removal:
  fibre_recovery:
  electronics_recovery:
  recyclability:
  end_of_life_route:

evidence:
  test_report_ids: []
  calibration_record_ids: []
  conformity_record_ids: []
  river_receipt_ids: []
```

## Passport Inheritance Rules

1. Model owns common engineering and conformity declarations.
2. Variant inherits model data and adds commercial attributes.
3. Batch inherits model/variant data and adds manufacturing evidence.
4. Item inherits all above and adds serialized electronics, calibration, firmware, repair and lifecycle events.
5. Child records never silently mutate parent records.
6. A material, hardware or functionality change that affects technical characteristics creates a new model revision.
7. A software/configuration change may remain an item/configuration event only when it does not invalidate model-level technical or regulatory claims.
8. Every supersession states authority, effective date, reason and evidence.

## Genesis / Warden / River Responsibilities

### Genesis
Canonical registry for:
- platform identities;
- capability identities;
- application families;
- product models;
- variants;
- batches;
- items;
- schema and vocabulary versions.

### Warden
Authorizes governed transitions, including:
- configuration validation request;
- prototype approval;
- engineering model release;
- production batch release;
- item activation;
- firmware/configuration update;
- regulated-claim activation;
- recall/quarantine;
- repair/refurbishment state change;
- end-of-life closure.

Warden does not rewrite evidence and does not generate engineering facts.

### River
Records evidence for:
- configuration compilation;
- material receipt;
- manufacturing process events;
- tests and calibration;
- Warden decisions;
- passport issuance;
- firmware/configuration change;
- repair and refurbishment;
- recall/quarantine;
- recycling/end-of-life.

## Lifecycle State Machine

```text
DRAFT_CONFIG
  -> PROTOTYPE_APPROVED
  -> ENGINEERING_VALIDATED
  -> MODEL_RELEASED
  -> BATCH_RELEASED
  -> ITEM_ACTIVE
  -> IN_SERVICE
  -> REPAIR | REFURBISH | QUARANTINE | RECALL
  -> RETIRED
  -> RECYCLED | DISPOSED
```

Transitions are additive evidence events. Historical states are not overwritten.

## Error and Exception Handling

Distinct failure classes:
- invalid taxonomy value;
- incompatible architecture;
- missing engineering evidence;
- missing regulatory evidence;
- duplicate human-readable SKU;
- identifier collision;
- supersession conflict;
- batch genealogy gap;
- item genealogy gap;
- unapproved configuration change;
- evidence-store failure.

A passport must not advance to a released state when mandatory evidence for that state is unavailable.

## Initial Files Planned

Implementation should remain small and independently testable:

```text
smart-textiles/
  README.md
  registry/
    integration-levels.yaml
    integration-methods.yaml
    conductive-platforms.yaml
    capabilities.yaml
    applications.yaml
    code-dictionary.yaml
  contracts/
    smart-textile-platform.schema.json
    capability-bundle.schema.json
    product-model.schema.json
    product-passport.schema.json
  compiler/
    compatibility-rules.yaml
    sku-grammar.yaml
  examples/
    sport-ecg-temperature-shirt.model.yaml
    industrial-thermal-gas-jacket.model.yaml
  tests/
    registry-validation/
    compiler-validation/
    passport-inheritance/
```

## Testing Strategy

### Taxonomy tests
- exactly 3 initial integration levels;
- exactly 3 initial integration methods;
- exactly 5 initial conductive platforms;
- exactly 17 initial capabilities;
- canonical IDs unique and immutable.

### SKU compiler tests
- deterministic output for identical model input;
- different technical architecture produces different engineering SKU;
- size/colour-only change remains a child commercial variant;
- duplicate engineering SKU rejected;
- unknown code rejected.

### Compatibility tests
- invalid architecture-capability combinations rejected;
- missing required power profile rejected;
- missing regulated-claim evidence prevents release;
- prototype-only combinations cannot become released models without required evidence.

### Passport inheritance tests
- model fields inherit to variant/batch/item;
- child overrides are explicit and versioned;
- parent edits do not silently rewrite historical issued passports;
- supersession chain remains traversable.

### River/Warden contract tests
- release requires Warden decision ID;
- issuance emits River receipt ID;
- denied configuration does not become released;
- firmware/configuration transition preserves prior state.

## Acceptance Criteria

R0.1 design is implemented successfully when:
- the 45 base architectures are representable without pre-generating them;
- all 17 canonical capabilities validate;
- the compiler can generate and reject sample configurations deterministically;
- one human-readable engineering SKU is generated from structured input;
- model/variant/batch/item identities are distinct;
- passport JSON validates against schema;
- two reference products compile successfully;
- invalid configuration fixtures fail for the correct reason;
- Warden release and River evidence references are mandatory at release state;
- every machine ID has an operator-readable English label/code;
- no final textile-DPP-compliance claim is made before the applicable delegated requirements are implemented.

## Deferred

- exhaustive application-capability compatibility matrix;
- medical-device/PPE certification logic;
- product-specific radio/battery compliance;
- ERP/PLM/Shopify/marketplace adapters;
- factory machine integration;
- QR/NFC carrier issuance;
- EU DPP Registry API adapter;
- GS1 identifier binding;
- consumer passport UI;
- repair/recycling partner portal;
- DigitalMe personal health-data storage.

These are additive future slices and must not require breaking the R0.1 identifiers.

## Recommended First Implementation Slice

Implement only:
1. the five registry YAML files plus English code dictionary;
2. the product-model and product-passport JSON Schemas;
3. a deterministic SKU compiler;
4. a compatibility-rule engine with a small explicit starter rule set;
5. two positive and four negative fixtures;
6. Warden/River reference fields without requiring live service integration.

This proves the taxonomy, identity hierarchy, configuration compiler and passport inheritance model before connecting factories, ERP, DPP infrastructure or live smart garments.