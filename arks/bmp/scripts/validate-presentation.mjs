import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { getPresentationModel } from "../market/a-1204/presentation.mjs";
const original = JSON.parse(readFileSync(new URL("../market/a-1204/listing.json",import.meta.url),"utf8"));
const rendered = getPresentationModel(original);
assert.equal(rendered.mode,"DEPICTION_ONLY");
assert.deepEqual(rendered.bundle_examples.map(x=>x.amount_display),["₹4.80 Cr","₹5.21 Cr","₹5.41 Cr","Example / Variable"]);
assert.match(rendered.disclaimer,/not verified/);
assert.equal(original.transaction_enabled,false);
for (const mutate of [
 d=>{d.transaction_enabled=true;},
 d=>{d.presentation.cost_mode="LIVE";},
 d=>{d.presentation.quote_enabled=true;},
 d=>{d.presentation.payment_enabled=true;},
 d=>{d.presentation.bundle_examples[0].purpose="QUOTE";},
 d=>{d.property_price.amount_purpose="PAYABLE";},
 d=>{d.presentation.arithmetic_policy="CALCULATE_REAL_TOTAL";}
]) {
 const changed=structuredClone(original);mutate(changed);
 assert.throws(()=>getPresentationModel(changed),/boundary|display example|derive quotes/);
}
console.log("PASS: depiction-only values preserved; seven transaction/quotation escalation mutations rejected.");
