import {readFileSync} from "node:fs";
import assert from "node:assert/strict";
const read=(name)=>readFileSync(new URL(name,import.meta.url),"utf8");
const md=read("../docs/LISTING_TEMPLATE.md");
const block=md.match(/~~~yaml\s*([\s\S]*?)~~~/i);
assert.ok(block,"YAML 1.2-compatible JSON block required");
const canonical=JSON.parse(block[1]);
const snapshot=JSON.parse(read("../market/a-1204/listing.json"));
assert.deepEqual(snapshot,canonical,"JSON snapshot diverges from canonical LISTING_TEMPLATE.md");
assert.equal(canonical.publication_status,"DRAFT_UNVERIFIED");
assert.equal(canonical.transaction_enabled,false);
assert.deepEqual(canonical.states,["TODAY","PLANNED","FINISHED","CONFIGURED","DELIVERED"]);
assert.deepEqual(canonical.anchors.map(a=>a.id),["FLOOR_01","ARCH_01","GLAZE_01","KITCHEN_01","BALC_01","LIGHT_01"]);
assert.ok(canonical.anchors.every(a=>a.evidence_status!=="VERIFIED"),"Fixture cannot claim verified evidence");
assert.equal(canonical.evidence_requirements.length,9);
for(const a of canonical.anchors){assert.ok(a.label&&a.included&&a.warranty);if(a.evidence_status==="PLACEHOLDER")assert.ok(a.evidence_ref);}
console.log("PASS: BMP A-1204 canonical fixture, disclosure/status gate and six anchors; snapshot in sync.");
