import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {getAnchorDetails,getStateProjection,getDoorPreview} from "../market/a-1204/experience.mjs";
import {interpretUntrustedDoorUrl} from "../market/a-1204/door-link.mjs";
const read=(p)=>readFileSync(new URL(p,import.meta.url),"utf8");
const fixture=JSON.parse(read("../market/a-1204/listing.json"));
const states=["TODAY","PLANNED","FINISHED","CONFIGURED","DELIVERED"];
for(const state of states){
 const scene=getStateProjection(fixture,state);
 assert.equal(scene.state,state);
 assert.equal(scene.simulation,true);
 assert.equal(scene.media_verified,false);
 assert.equal(scene.physical_completion_verified,false);
 assert.ok(scene.warning.length>25);
}
assert.equal(fixture.anchors.length,6);
for(const anchor of fixture.anchors){
 for(const state of states){
  const a=getAnchorDetails(fixture,anchor.id,state);
  assert.equal(a.id,anchor.id);
  assert.equal(a.evidence_verified,false);
  assert.equal(a.specification_verified,false);
  assert.ok(a.included&&a.supplier&&a.warranty);
 }
}
assert.throws(()=>getStateProjection(fixture,"APPROVED"),/Unsupported/);
assert.throws(()=>getAnchorDetails(fixture,"ADMIN", "FINISHED"),/Unknown/);
assert.throws(()=>getDoorPreview(fixture,{state:"FINISHED",anchor:"NOT_REAL"}),/Unknown/);
const p=getDoorPreview(fixture,{state:"FINISHED",anchor:"FLOOR_01",locale:"ar-AE"});
assert.equal(new URL(p.url).hostname,"example.invalid");
assert.equal(new URL(p.url).searchParams.get("state"),"FINISHED");
assert.equal(new URL(p.url).searchParams.get("anchor"),"FLOOR_01");
assert.equal(new URL(p.url).searchParams.get("locale"),"ar-AE");
assert.equal(p.effective_disclosure,"GUEST");
assert.equal(p.active_destination,false);
assert.equal(p.evidence_verified,false);
assert.equal(p.booking_confirmed,false);
for(const key of ["buyer","disclosure","role","rights","river","token"])assert.equal(new URL(p.url).searchParams.has(key),false);
const tampered=p.url+"&disclosure=VERIFIED&role=OWNER&river=river://fake&buyer=Dubai";
const interpreted=interpretUntrustedDoorUrl(tampered);
assert.equal(interpreted.effective_disclosure,"GUEST");
assert.equal(interpreted.admitted,false);
assert.equal(interpreted.evidence_verified,false);
const altered=structuredClone(fixture);altered.transaction_enabled=true;
assert.throws(()=>getStateProjection(altered,"TODAY"),/nontransactional/);
const html=read("../market/a-1204/index.html");
const app=read("../market/a-1204/app.js");
for(const id of ["state-rail","stage-heading","stage-warning","anchor-grid","anchor-dialog","drawer-title","drawer-close","anchor-fields","door-locale","door-url","door-status","copy-door","bundle-examples","presentation-disclaimer"]){
 assert.ok(html.includes('id="'+id+'"'),"Missing UI element "+id);
}
for(const action of ["getStateProjection","getAnchorDetails","getDoorPreview","getPresentationModel","interpretUntrustedDoorUrl"]){
 assert.ok(app.includes(action),"Missing wiring "+action);
}
assert.ok(html.includes('aria-labelledby="drawer-title"'));
assert.ok(html.includes('role="group"'));
assert.ok(html.includes("NOT A LIVE OFFER"));
assert.ok(html.includes("Copy inactive example link"));
assert.ok(app.includes(String.raw`/~~~yaml\s*([\s\S]*?)~~~/i`),"Canonical YAML fence parser must retain functional regex escapes");
assert.ok(app.includes("node.dataset.anchorId===lastAnchorId"),"Closing the drawer must restore focus to current rendered anchor button");
console.log("PASS: R0.5 5-state scene, 30 anchor state combinations, inactive Door previews, authority tampering and view bindings.");
