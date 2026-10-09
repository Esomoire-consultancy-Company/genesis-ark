import {DoorError,verifySigned} from "./resolver.mjs";
import {createFederationTransport,validateAssetId} from "./transport.mjs";
import {a1204DraftRegistry} from "./registry.mjs";

const issuers=Object.freeze(["Genesis","DigitalMe","Warden","River","Quantum"]);
const isObject=v=>v!==null && typeof v==="object" && !Array.isArray(v);
function mustObject(v){if(!isObject(v))throw new DoorError("FEDERATION_BAD_RESPONSE",503);return v;}
export function createFederatedAdapters({
 origins,publicKeys,getServiceToken,nonceStore,
 allowedAssets=[],fetchImpl=globalThis.fetch,clock=()=>Date.now(),timeoutMs=2500
}={}){
 if(!publicKeys||issuers.some(x=>!publicKeys[x])||
    !Array.isArray(allowedAssets)||allowedAssets.some(x=>typeof x!=="string"||!/^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$/.test(x))||
    !nonceStore||typeof nonceStore.consume!=="function")
    throw new DoorError("FEDERATION_NOT_CONFIGURED",503);
 // Only registered, explicitly approved assets may cross this boundary.
 const allow=new Set(allowedAssets.filter(x=>x!=="A-1204"));
 const transport=createFederationTransport({origins,getServiceToken,fetchImpl,timeoutMs});
 async function signed(service,path,payload=null){
  const raw=await transport.invoke(service,path,payload);
  return mustObject(raw);
 }
 const registry=Object.freeze({
  async get(assetRef){
   validateAssetId(assetRef);
   // Absolute hard-deny for the published A-1204 demonstration until a new governed revision.
   if(assetRef==="A-1204")return a1204DraftRegistry.get("A-1204");
   if(!allow.has(assetRef))return null;
   const envelope=await signed("Genesis","/v1/assets/"+encodeURIComponent(assetRef));
   const p=verifySigned(envelope,{issuer:"Genesis",key:publicKeys.Genesis,now:clock});
   if(p.asset_ref!==assetRef||!isObject(p.resource)||p.resource.asset_ref!==assetRef)
      throw new DoorError("GENESIS_BINDING_INVALID",503);
   return p.resource;
  }
 });
 const digitalMe=Object.freeze({
  async resolve({authorization,asset_ref}){
   return signed("DigitalMe","/v1/assertions/resolve",{contract_version:"digitalme.session-proof.v0.1",asset_ref,authorization});
  }
 });
 const warden=Object.freeze({
  async decide(request){
   return signed("Warden","/v1/admissions/evaluate",{contract_version:"warden.policy-decision.v0.1",...request});
  }
 });
 const river=Object.freeze({
  async record({event,digest}){
   return signed("River","/v1/evidence/ingest",{contract_version:"river.evidence-ingest.v0.1",event,event_digest:digest});
  }
 });
 const quantum=Object.freeze({
  async request({correlation_id,room_ref,decision_id,requested_slot}){
   return signed("Quantum","/v1/sessions/request",{
    contract_version:"quantum.session-request.v0.1",correlation_id,room_ref,decision_id,requested_slot
   });
  }
 });
 return Object.freeze({registry,digitalMe,warden,river,quantum,publicKeys:Object.freeze({
  digitalMe:publicKeys.DigitalMe,warden:publicKeys.Warden,river:publicKeys.River,genesis:publicKeys.Genesis,quantum:publicKeys.Quantum
 }),nonceStore,clock});
}
