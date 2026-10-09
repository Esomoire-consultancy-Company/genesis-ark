import { getPresentationModel } from "./presentation.mjs";
import { interpretUntrustedDoorUrl } from "./door-link.mjs";
import { getStateProjection, getAnchorDetails, getDoorPreview } from "./experience.mjs";

const $=id=>document.getElementById(id);
const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=String(text);return node;};
let data=null,display=null,selectedAnchor=null,lastTrigger=null;
const anchorDialog=$("anchor-dialog");

async function loadFixture(){
  try{
    const raw=await fetch("../../docs/LISTING_TEMPLATE.md",{cache:"no-store"});
    if(!raw.ok)throw new Error("Canonical Markdown unavailable");
    const markdown=await raw.text();
    const match=markdown.match(/~~~yaml\\s*([\\s\\S]*?)~~~/i);
    if(!match)throw new Error("Raw canonical source not available");
    $("data-source").textContent="Source: canonical LISTING_TEMPLATE.md.";
    return JSON.parse(match[1]);
  }catch{
    const fallback=await fetch("./listing.json",{cache:"no-store"});
    if(!fallback.ok)throw new Error("Snapshot listing unavailable");
    $("data-source").textContent="Source: checked-in listing.json snapshot.";
    return fallback.json();
  }
}
function populateSelect(node,values){
  node.replaceChildren();
  for(const value of values){const option=el("option",null,value);option.value=value;node.append(option);}
}
async function boot(){
  data=await loadFixture();
  display=getPresentationModel(data); // fail closed if portrayal/transaction flags are invalid
  $("presentation-disclaimer").textContent=display.disclaimer;
  $("listing-title").textContent=data.title;
  $("listing-location").textContent=data.location;
  populateSelect($("stage"),data.states);
  populateSelect($("tier"),data.disclosure_levels);
  const hints=interpretUntrustedDoorUrl(window.location.href); // URL is navigation input, NEVER authority.
  $("stage").value=hints.requested_state;
  selectedAnchor=hints.requested_anchor;
  if(["en","ar","en-IN","en-AE","ar-AE"].includes(hints.locale_hint))$("door-locale").value=hints.locale_hint;
  $("stage").addEventListener("change",render);
  $("tier").addEventListener("change",render);
  $("door-locale").addEventListener("change",renderDoor);
  $("resolve").addEventListener("click",resolve);
  $("copy").addEventListener("click",copyRef);
  $("copy-door").addEventListener("click",copyDoor);
  $("drawer-close").addEventListener("click",()=>anchorDialog.close());
  anchorDialog.addEventListener("close",()=>lastTrigger?.focus());
  $("clear-anchor").addEventListener("click",()=>{selectedAnchor=null;render();});
  render();
}
function render(){
  if(!data)return;
  const state=$("stage").value, tier=$("tier").value;
  const scene=getStateProjection(data,state);
  $("stage-label").textContent=scene.state+" · CONCEPT";
  $("state-explainer").textContent=scene.description;
  $("stage-heading").textContent=scene.heading;
  $("stage-warning").textContent=scene.warning;
  const rail=$("state-rail");rail.replaceChildren();
  for(const s of data.states){
    const button=el("button","rail-choice"+(s===state?" is-active":""),s);
    button.type="button";
    button.setAttribute("aria-pressed",String(s===state));
    button.addEventListener("click",()=>{$("stage").value=s;render();});
    rail.append(button);
  }
  const grid=$("anchor-grid");grid.replaceChildren();
  for(const a of data.anchors){
    const card=el("button","anchor"+(selectedAnchor===a.id?" selected":""));
    card.type="button";card.setAttribute("aria-haspopup","dialog");
    card.setAttribute("aria-label","Inspect "+a.label+" component "+a.id);
    card.append(el("small",null,a.id),el("h3",null,a.label),
      el("p",null,state==="TODAY"?a.today:a.proposed),
      el("p","evidence","Evidence: "+a.evidence_status+" · Inclusion: "+a.included));
    card.addEventListener("click",()=>openAnchor(a.id,card));
    grid.append(card);
  }
  $("clear-anchor").disabled=selectedAnchor===null;
  const steps=$("commercial-steps");steps.replaceChildren();
  for(const [index,name] of data.commercial_flow.entries()){
    const row=el("div","step");row.append(el("b",null,index+1),document.createTextNode(name));steps.append(row);
  }
  $("price").textContent=display.base_display;
  $("price-note").textContent="Illustrative depiction only. Not a verified price, amount payable, valuation or offer.";
  const bundleNode=$("bundle-examples");bundleNode.replaceChildren();
  for(const bundle of display.bundle_examples){
    const row=el("div","step");row.append(el("span",null,bundle.label+" — "),el("strong",null,bundle.amount_display));bundleNode.append(row);
  }
  $("disclosure").textContent=tier+" preview persona only. Effective access remains GUEST until DigitalMe identity and Warden admission are evaluated by a real service.";
  $("evidence-summary").textContent=data.anchors.length+" anchor records; 0 authenticated River receipts provided. References are mock identifiers, not verified proof.";
  if(anchorDialog.open && selectedAnchor)renderAnchorDialog();
  renderDoor();
}
function openAnchor(id,trigger){
  selectedAnchor=id;lastTrigger=trigger;
  render();
  renderAnchorDialog();
  if(typeof anchorDialog.showModal==="function")anchorDialog.showModal();
  else {anchorDialog.setAttribute("open","");$("drawer-close").focus();}
}
function renderAnchorDialog(){
  const detail=getAnchorDetails(data,selectedAnchor,$("stage").value);
  $("drawer-title").textContent=detail.label+" · "+detail.id;
  $("drawer-note").textContent="Source-supplied concept only. No supplier, warranty, inclusion or River record is verified.";
  const body=$("anchor-fields");body.replaceChildren();
  const fields=[
    ["Current reference",detail.today],
    ["Proposed configuration",detail.proposed],
    ["Included",detail.included],
    ["Supplier",detail.supplier],
    ["Warranty",detail.warranty],
    ["Evidence reference",detail.evidence_ref],
    ["Evidence status",detail.evidence_status+" — NOT VERIFIED"]
  ];
  for(const [key,value] of fields){body.append(el("dt",null,key),el("dd",null,value));}
}
function renderDoor(){
  if(!data)return;
  const preview=getDoorPreview(data,{state:$("stage").value,anchor:selectedAnchor,locale:$("door-locale").value});
  $("door-url").textContent=preview.url;
  $("door-status").textContent="Inactive example URL · requested state "+preview.requested_state+" · "+(preview.requested_anchor??"No anchor")+" · effective disclosure: GUEST · no booking or River receipt.";
}
function resolve(){
  const intent=$("intent").value.trim().toLowerCase();
  if(!intent){$("intent-response").textContent="Enter a proposed request to preview routing.";return;}
  const flooring=intent.includes("wood")||intent.includes("floor");
  $("intent-response").textContent=(flooring?"FLOOR_01 suitability and replacement specification would require a site check. ":"Review of the requested anchor and capability is required. ")+
  "Proposed sequence: DigitalMe → Warden → Genesis → Synnergyze → provider response → River. SIMULATED ONLY; no external API, cost quote or work order was issued.";
}
async function copyText(value,target,success){
  try {await navigator.clipboard.writeText(value);$(target).textContent=success;}
  catch {$(target).textContent="Clipboard unavailable. Select the visible reference manually.";}
}
function copyRef(){
  copyText("BMP-A1204 | DRAFT_UNVERIFIED | "+data.asset_id,"copy-status","Demonstration reference copied. No lead submitted.");
}
function copyDoor(){
  copyText($("door-url").textContent,"door-copy-status","Inactive example link copied. Not a live Door or QR destination.");
}
boot().catch(err=>{
  $("listing-title").textContent="Preview unavailable";
  $("data-source").textContent="Validation failed: "+err.message;
  $("stage-warning").textContent="No listing may be displayed as a verified property or offer until its source passes validation.";
});
