// BMP commercial display-only fixture contract, v0.2.
// This module does not authorize quoting, checkout, offers, invoicing or settlement.
export function getPresentationModel(fixture) {
  if (!fixture || fixture.schema_version !== "bmp.property-listing.v0.2") throw new Error("Unsupported listing contract");
  const p = fixture.presentation;
  if (!p || p.cost_mode !== "DEPICTION_ONLY" || fixture.transaction_enabled !== false ||
      p.quote_enabled !== false || p.payment_enabled !== false ||
      p.commercial_settlement_enabled !== false ||
      fixture.property_price?.amount_purpose !== "VISUAL_MOCKUP_ONLY")
    throw new Error("Financial depiction boundary not satisfied");
  if (p.arithmetic_policy !== "DISPLAY_EXAMPLES_AS_PROVIDED_DO_NOT_RECONCILE_OR_REPRICE")
    throw new Error("Do not derive quotes from depicted figures");
  if (typeof p.disclaimer !== "string" || !p.disclaimer.includes("illustrative") || !p.disclaimer.includes("not verified"))
    throw new Error("Illustrative-only disclaimer is required");
  if (typeof p.base_display !== "string" || !Array.isArray(p.bundle_examples) || p.bundle_examples.length < 3)
    throw new Error("Depiction bundle data missing");
  for (const line of p.bundle_examples) {
    if (line.purpose !== "DEPICTION_ONLY" || typeof line.label !== "string" ||
        typeof line.amount_display !== "string" || !line.label || !line.amount_display)
      throw new Error("Every bundle amount must be an explicit display example");
  }
  return Object.freeze({
    mode:p.cost_mode,
    disclaimer:p.disclaimer,
    base_display:p.base_display,
    bundle_examples:p.bundle_examples.map(x=>Object.freeze({label:x.label,amount_display:x.amount_display}))
  });
}
