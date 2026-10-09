import {buildPublicDoorLink, interpretUntrustedDoorUrl} from "./door-link.mjs";
// R0.5: pure projection helpers. They do not turn samples into real-world facts or permissions.
const STATES=["TODAY","PLANNED","FINISHED","CONFIGURED","DELIVERED"];
const STAGE_CONTEXT={
  TODAY:{heading:"Reference condition · source not authenticated",label:"As-is reference",warning:"The described 8 Oct 2026 construction condition has not been independently verified. The stage illustration is conceptual, not a site photograph."},
  PLANNED:{heading:"Proposed design · not approved construction",label:"Planning concept",warning:"Illustrates intended design choices. No approved plan, licensed BIM or supplier confirmation is established by this preview."},
  FINISHED:{heading:"Illustrative finished scene · not as-built",label:"Finished concept",warning:"Depicts a potential completed look. It is not evidence of actual work, completion, inclusion or handover."},
  CONFIGURED:{heading:"Buyer configuration · hypothetical",label:"Personalization concept",warning:"Any buyer-selected finish is a hypothetical preference, not an accepted change order or provider quotation."},
  DELIVERED:{heading:"Handover workflow · not delivered",label:"Future handover",warning:"No actual delivery, acceptance, title transfer or certified as-built record has been confirmed."}
};
export function getStateProjection(fixture,state){
  if(!fixture || fixture.publication_status!=="DRAFT_UNVERIFIED" || fixture.transaction_enabled!==false)
    throw new Error("Only unverified nontransactional pilot fixtures are supported");
  if(!STATES.includes(state)||!fixture.states.includes(state))
    throw new Error("Unsupported property state");
  const x=STAGE_CONTEXT[state];
  return Object.freeze({state,label:x.label,heading:x.heading,warning:x.warning,description:fixture.state_descriptions[state],simulation:true,media_verified:false,physical_completion_verified:false});
}
export function getAnchorDetails(fixture,anchorId,state){
  const stage=getStateProjection(fixture,state);
  const item=fixture.anchors.find(x=>x.id===anchorId);
  if(!item)throw new Error("Unknown anchor");
  return Object.freeze({
    id:item.id,label:item.label,state,
    stage_description:stage.description,
    today:item.today,proposed:item.proposed,
    included:item.included??"UNCONFIRMED",
    supplier:item.supplier??"TBD",
    warranty:item.warranty??"TBD",
    evidence_ref:item.evidence_ref??"Not supplied",
    evidence_status:item.evidence_status,
    evidence_verified:false,
    specification_verified:false
  });
}
export function getDoorPreview(fixture,{state="TODAY",anchor=null,locale="en"}={}){
  getStateProjection(fixture,state);
  if(anchor!==null&&!fixture.anchors.some(x=>x.id===anchor))
    throw new Error("Unknown anchor");
  // The reserved example.invalid host deliberately does NOT resolve to a real buyer Door.
  const url=buildPublicDoorLink("https://example.invalid",{
    place:"belgaum",asset:fixture.asset_id,state,anchor,locale
  });
  const interpretation=interpretUntrustedDoorUrl(url);
  if(interpretation.effective_disclosure!=="GUEST"||interpretation.admitted)
    throw new Error("Untrusted links must not grant access");
  return Object.freeze({url,simulation:true,active_destination:false,requested_state:interpretation.requested_state,requested_anchor:interpretation.requested_anchor,effective_disclosure:interpretation.effective_disclosure,evidence_verified:false,booking_confirmed:false});
}
