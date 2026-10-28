# Genesis DPI Synthetic Node Passport R0.1

Proof of schema and internal consistency only. Not a real physical node
commissioning, a DigitalMe identity check, a Warden permission or a RiverOS
attestation. No external API calls, device actions, geolocation, or persistence.

Run from repository root:

```bash
python3 -m unittest discover -s infrastructure/tests -v
python3 -m infrastructure.passport infrastructure/examples/synthetic-ark-001.json
```

The sample has **synthetic-only** persons, assets and locations. The validator
ensures ARK attachments cannot falsely claim takeover, active state cannot be
asserted without field acceptance, and physical/digital presence is explicit.
Real evidence and approval signatures require independent authorised verification.

Specification: `docs/architecture/GENESIS-DIGITAL-PHYSICAL-INFRASTRUCTURE-R0.1.md`.
