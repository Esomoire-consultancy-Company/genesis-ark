# Genesis Smart Textile Product Passport Registry R0.1

This subsystem implements the first executable Genesis smart-textile taxonomy, SKU compiler, compatibility rules, and hierarchical Digital Product Passport (DPP) contracts. It is **DPP-ready**; it does not claim final textile-DPP compliance before the applicable product-specific rules are implemented.

## Canonical space

The R0.1 architecture has 3 integration levels × 3 integration methods × 5 conductive platforms = **45 base architectures**. It registers **17 canonical capabilities** and five initial application families.

Across all non-empty bundles of the 17 capabilities, the mathematical upper bound is 45 × (2^17 − 1) = **5,898,195 theoretical engineering configurations**. The registry does not pre-generate these. The compiler creates configurations on demand and the compatibility engine rejects unsupported or insufficiently evidenced combinations.

## SKU grammar

`ST-[USE]-[FORM]-[INT]-[METHOD]-[CAPSET]-[MAT]-[POWER]-R[REV]`

Example: `ST-SPT-TSH-YRN-KNT-ECG+TMP-AG-TRB-R01`.

## Passport hierarchy

`Smart Textile Platform -> Capability Bundle -> Product Model -> Commercial Variant -> Production Batch -> Serialized Item`

Child passports inherit engineering facts without mutating historical parent records. Released states require Warden decision references and River evidence references.

## Local verification

```bash
cd smart-textiles
python -m pip install -e '.[test]'
pytest -v
```
