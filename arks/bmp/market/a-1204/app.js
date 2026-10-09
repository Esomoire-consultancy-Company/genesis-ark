const $=id=>document.getElementById(id);
const htmlEscapeNotNeeded=true; // All untrusted fixture content uses textContent, not innerHTML.
const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n;};
let data=null;
async function load(){
 try{
  const raw=await fetch("../../docs/LISTING_TEMPLATE.md",{cache:"no-store"});
  if(!raw.ok)throw new Error("Canonical Markdown unavailable");
  const md=await raw.text();
  const block=md.match(/~~~yaml\s*([\s\S]*?)~~~/i);
  if(!block)throw new Error("Canonical Markdown transformed or YAML fence missing");
  data=JSON.parse(block[1]); $("data-source").textContent="Source: canonical LISTING_TEMPLATE.md.";
 }catch(err){
  const fallback=await fetch("./listing.json",{cache:"no-store"});
  if(!fallback.ok)throw new Error("Listing fallback unavailable: "+err.message);
  data=await fallback.json(); $("data-source").textContent="Source: checked-in listing.json snapshot.";
 }
 for(const state of data.states){const opt=el("option",null,state);opt.value=state;$("stage").append(opt);}
 for(const tier of data.disclosure_levels){const opt=el("option",null,tier);opt.value=tier;$("tier").append(opt);}
 $("listing-title").textContent=data.title;
 $("listing-location").textContent=data.location;
 $("stage").addEventListener("change",render);
 $("tier").addEventListener("change",render);
 $("resolve").addEventListener("click",resolve);
 $("copy").addEventListener("click",copyRef);
 render();
}
function render(){
 const stage=$("stage").value||"TODAY",tier=$("tier").value||"GUEST";
 $("stage-label").textContent=stage;
 $("state-explainer").textContent=data.state_descriptions[stage]||"Concept state only.";
 $("anchor-grid").replaceChildren();
 for(const a of data.anchors){
  const card=el("article","anchor");card.append(el("small",null,a.id),el("h3",null,a.label));
  card.append(el("p",null,stage==="TODAY"?a.today:a.proposed));
  card.append(el("p","evidence","Evidence: "+a.evidence_status+" · Inclusion: "+a.included));
  $("anchor-grid").append(card);
 }
 $("commercial-steps").replaceChildren();
 data.commercial_flow.forEach((s,i)=>{const row=el("div","step");row.append(el("b",null,i+1),document.createTextNode(s));$("commercial-steps").append(row);});
 $("price").textContent=tier==="GUEST"?"Price gated (demo)":"₹"+(data.property_price.indicative_amount/10000000).toFixed(2)+" Cr";
 $("price-note").textContent=tier==="GUEST"?"Select a preview persona to view indicative figures. This is not Warden admission.":"Unverified property indication; additional ₹18L and ₹12L lines have unknown scope. No binding quote.";
 $("disclosure").textContent=tier+" preview only. Actual access requires server-side DigitalMe proof, Warden approval, lawful purpose and resource-scoped authorization.";
 const found=data.anchors.filter(a=>a.evidence_status==="PLACEHOLDER").length;
 $("evidence-summary").textContent=data.anchors.length+" anchors; "+found+" mock evidence URI; 0 independently verified receipts supplied.";
}
function resolve(){
 const q=$("intent").value.trim().toLowerCase();if(!q){$("intent-response").textContent="Enter an intent to preview its governance route.";return;}
 const specific=q.includes("wood")||q.includes("floor");
 $("intent-response").textContent=(specific?"FLOOR_01: site suitability, specification, approval, supplier, cost difference and warranty are required. ":"Intent classification pending operator review. ")+"Route: DigitalMe → Warden → Genesis capability graph → Synnergyze provider confirmation → commercial response → River receipt. SIMULATION ONLY; no calls executed.";
}
async function copyRef(){
 const txt="BMP-A1204 | DRAFT_UNVERIFIED | "+data.asset_id;
 try{await navigator.clipboard.writeText(txt);$("copy-status").textContent="Enquiry reference copied (no lead submitted).";}catch{$("copy-status").textContent=txt;}
}
load().catch(err=>{$("listing-title").textContent="Fixture unavailable";$("data-source").textContent=err.message;});
