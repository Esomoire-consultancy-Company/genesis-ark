# Synnergyze capability routing

Intent → DigitalMe/estate context → Warden authorization → Genesis capability graph → Synnergyze provider selection → supplier confirmation → commercial impact → River outcome.

**Example: "Can the floor be wood?"**
1. BMP resolves the action to A-1204/FLOOR_01 with a specified user intent.
2. Warden checks whether this principal may request a configuration quote (not property access/title).
3. Genesis returns eligible installation/design capabilities and jurisdictions.
4. Synnergyze queries authorized suppliers for feasibility, approvals, load/installation constraints, bill of materials, cost, lead time, warranty.
5. Compare approved marble baseline with requested wood alternative; return price *difference* and risks only with source-backed quotes.
6. Capture quote, authorization, accepted specification, installer work and evidence references in River.

Return `NOT_READY` when policy, supplier verification, safety or pricing inputs are missing. Provider-native services execute work. Do not invent approvals or quote amounts. Runtime order is Identity → Authority → Reachability → Orchestration → Execution → Evidence.
