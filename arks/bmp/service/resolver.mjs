import {createHash, verify as verifySignature, createPublicKey, randomUUID} from "node:crypto";

export class DoorError extends Error{
  constructor(code,status=403){super(code);this.name="DoorError";this.code=code;this.status=status;}
}
export const AUDIENCE="bmp-door-resolver";
const MAX_SECONDS=300;
const isObject=x=>x!==null && typeof x==="object" && !Array.isArray(x);
const safeString=(s,max=128)=>typeof s==="string" && s.length>0 && s.length<=max && /^[A-Za-z0-9:_./-]+$/.test(s);
export function digest(value){return createHash("sha256").update(JSON.stringify(value)).digest("hex");}
export function verifySigned(envelope,{issuer,key,now=()=>Date.now()}){
  if(!isObject(envelope)||!isObject(envelope.payload)||typeof envelope.signature!=="string"||!key)
    throw new DoorError("SIGNATURE_REQUIRED",503);
  const p=envelope.payload;
  if(p.iss!==issuer||p.aud!==AUDIENCE)throw new DoorError("UNTRUSTED_ISSUER");
  if(!Number.isSafeInteger(p.iat)||!Number.isSafeInteger(p.exp)||
    p.exp<=p.iat||p.exp-p.iat>MAX_SECONDS||
    p.iat>Math.floor(now()/1000)+30 || p.exp<=Math.floor(now()/1000))
    throw new DoorError("ASSERTION_EXPIRED");
  let signed;
  try{
    const bytes=Buffer.from(envelope.signature,"base64url");
    if(bytes.length!==64)throw new Error("Bad signature length");
    signed=verifySignature(null,Buffer.from(JSON.stringify(p),"utf8"),createPublicKey(key),bytes);
  }catch{throw new DoorError("SIGNATURE_INVALID");}
  if(!signed)throw new DoorError("SIGNATURE_INVALID");
  return p;
}
export function validateRequest(body){
  const allowed=["contract_version","asset_ref","door_ref","requested_state","anchor_ref","locale_hint"];
  if(!isObject(body)||Object.keys(body).some(k=>!allowed.includes(k))||
     body.contract_version!=="bmp.door-resolve.v0.1"||
     !safeString(body.asset_ref,64)||!safeString(body.door_ref,128)||
     typeof body.requested_state!=="string"||
     !["TODAY","PLANNED","FINISHED","CONFIGURED","DELIVERED"].includes(body.requested_state)||
     !(body.anchor_ref===null||body.anchor_ref===undefined||safeString(body.anchor_ref,64))||
     !(body.locale_hint===undefined||["en","en-IN","en-AE","ar","ar-AE"].includes(body.locale_hint)))
     throw new DoorError("INVALID_DOOR_REQUEST",400);
  return Object.freeze({
    asset_ref:body.asset_ref,door_ref:body.door_ref,
    requested_state:body.requested_state,
    anchor_ref:body.anchor_ref??null,
    locale_hint:body.locale_hint??"en"
  });
}
export function createDoorResolver({registry,digitalMe,warden,river,nonceStore,publicKeys,clock=()=>Date.now()}={}){
  if(!registry?.get||!digitalMe?.resolve||!warden?.decide||!river?.record||!nonceStore?.consume||
     !publicKeys?.digitalMe||!publicKeys?.warden||!publicKeys?.river)
     throw new DoorError("INTEGRATION_UNAVAILABLE",503);
  return async function resolve(request,{authorization}={}){
    const input=validateRequest(request);
    if(typeof authorization!=="string"||!/^Bearer [A-Za-z0-9._~-]{8,4096}$/.test(authorization))
      throw new DoorError("IDENTITY_REQUIRED",401);
    const resource=await registry.get(input.asset_ref);
    if(!isObject(resource)||resource.asset_ref!==input.asset_ref||
       resource.door_ref!==input.door_ref||resource.status!=="VERIFIED_ACTIVE"||
       resource.live_enabled!==true||
       !safeString(resource.resource_ref,128)||!safeString(resource.room_ref,128)||
       !["GUEST","REGISTERED"].includes(resource.max_disclosure)||
       !Array.isArray(resource.states)||!resource.states.includes(input.requested_state)||
       !Array.isArray(resource.anchors)|| (input.anchor_ref!==null&&!resource.anchors.includes(input.anchor_ref)))
      throw new DoorError("RESOURCE_NOT_ADMITTED",403);
    const signedIdentity=await digitalMe.resolve({authorization,asset_ref:input.asset_ref});
    const principal=verifySigned(signedIdentity,{issuer:"DigitalMe",key:publicKeys.digitalMe,now:clock});
    if(!safeString(principal.principal_ref,128)||!safeString(principal.jti,128)||
       !["GUEST","REGISTERED"].includes(principal.identity_class))
      throw new DoorError("IDENTITY_INVALID",401);
    // Atomic, durable nonce consumption MUST be provided by the deployment.
    let fresh=false;
    try{fresh=await nonceStore.consume("digitalme:"+principal.jti,principal.exp);}
    catch{throw new DoorError("NONCE_STORE_UNAVAILABLE",503);}
    if(fresh!==true)throw new DoorError("ASSERTION_REPLAY",409);
    const correlation_id=randomUUID();
    const decisionEnvelope=await warden.decide({
      principal_ref:principal.principal_ref,
      identity_class:principal.identity_class,
      resource_ref:resource.resource_ref,
      asset_ref:input.asset_ref,door_ref:input.door_ref,
      action:"door.enter",requested_state:input.requested_state,
      anchor_ref:input.anchor_ref,correlation_id
    });
    const d=verifySigned(decisionEnvelope,{issuer:"Warden",key:publicKeys.warden,now:clock});
    if(d.allowed!==true||d.action!=="door.enter"||
       !safeString(d.decision_id,128)||!safeString(d.policy_version,128)||
       d.principal_ref!==principal.principal_ref||
       d.correlation_id!==correlation_id||
       d.asset_ref!==resource.asset_ref||d.door_ref!==resource.door_ref||
       (d.anchor_ref??null)!==input.anchor_ref||
       d.resource_ref!==resource.resource_ref||
       !Array.isArray(d.allowed_states)||!d.allowed_states.includes(input.requested_state)||
       !["GUEST","REGISTERED"].includes(d.disclosure)||
       (principal.identity_class==="GUEST"&&d.disclosure!=="GUEST")||
       (resource.max_disclosure==="GUEST"&&d.disclosure!=="GUEST"))
      throw new DoorError("WARDEN_DENIED",403);
    const event=Object.freeze({
      event_type:"DOOR_ADMISSION",
      correlation_id,asset_ref:resource.asset_ref,door_ref:resource.door_ref,
      room_ref:resource.room_ref,requested_state:input.requested_state,
      anchor_ref:input.anchor_ref,
      principal_digest:digest(principal.principal_ref),warden_decision_ref:d.decision_id,
      recorded_at:new Date(clock()).toISOString()
    });
    const receiptEnvelope=await river.record({event,digest:digest(event)});
    const receipt=verifySigned(receiptEnvelope,{issuer:"River",key:publicKeys.river,now:clock});
    if(!safeString(receipt.receipt_id,128)||receipt.correlation_id!==correlation_id||
       receipt.decision_id!==d.decision_id||receipt.event_digest!==digest(event)||
       receipt.verified!==true)
       throw new DoorError("EVIDENCE_UNAVAILABLE",503);
    return Object.freeze({
      admission_status:"ADMITTED",correlation_id,
      asset_ref:resource.asset_ref,room_ref:resource.room_ref,door_ref:resource.door_ref,
      state:input.requested_state,anchor_ref:input.anchor_ref,
      disclosure:d.disclosure,policy_decision_ref:d.decision_id,
      evidence_receipt_ref:receipt.receipt_id,
      expires_at:Math.min(principal.exp,d.exp),
      monetary_values:"DEPICTION_ONLY",
      transaction_enabled:false
    });
  };
}
