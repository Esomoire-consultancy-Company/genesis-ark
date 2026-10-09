import assert from "node:assert/strict";
import {generateKeyPairSync,sign} from "node:crypto";
import {createDoorResolver,validateRequest,verifySigned,DoorError,AUDIENCE,digest} from "../service/resolver.mjs";
import {createDoorHttpServer} from "../service/http.mjs";
import {a1204DraftRegistry} from "../service/registry.mjs";

const now=Date.now();
const s=Math.floor(now/1000);
const clock=()=>now;
const keys=Object.fromEntries(["DigitalMe","Warden","River"].map(name=>{
 const {privateKey,publicKey}=generateKeyPairSync("ed25519");
 return [name,{privateKey,publicKey}];
}));
const publicKeys={digitalMe:keys.DigitalMe.publicKey,warden:keys.Warden.publicKey,river:keys.River.publicKey};
const signed=(issuer,payload)=>{
 const complete={iss:issuer,aud:AUDIENCE,iat:s-5,exp:s+120,...payload};
 return {payload:complete,signature:sign(null,Buffer.from(JSON.stringify(complete)),keys[issuer].privateKey).toString("base64url")};
};
const resource={
 asset_ref:"LAB-0001",resource_ref:"LAB:ROOM:0001",door_ref:"VSR:LAB:0001:DOOR",
 room_ref:"VSR:LAB:0001:ROOM",status:"VERIFIED_ACTIVE",live_enabled:true,
 max_disclosure:"GUEST",states:["TODAY","FINISHED"],anchors:["FLOOR_01"]
};
const input={contract_version:"bmp.door-resolve.v0.1",asset_ref:"LAB-0001",
 door_ref:resource.door_ref,requested_state:"FINISHED",anchor_ref:"FLOOR_01"};
const attempts=[];
function adapters({asset=resource,identity=null,decision=null,receipt=null,keysOverride=null,throwNonce=false}={}){
 const used=new Set();
 const state={wardenCalls:0,riverCalls:0,identityCalls:0};
 const registry={async get(assetId){return assetId===asset.asset_ref?asset:null;}};
 const digitalMe={async resolve(){
   state.identityCalls++;
   return identity??signed("DigitalMe",{principal_ref:"principal:lab-guest",identity_class:"GUEST",
     jti:"unique:"+String(state.identityCalls)+"-"+String(attempts.length)});
 }};
 const warden={async decide(call){
   state.wardenCalls++;
   return decision?.(call)??signed("Warden",{
     allowed:true,decision_id:"warden:demo-001",policy_version:"lab:v1",
     principal_ref:call.principal_ref,correlation_id:call.correlation_id,
     asset_ref:call.asset_ref,door_ref:call.door_ref,
     resource_ref:call.resource_ref,anchor_ref:call.anchor_ref,
     action:call.action,allowed_states:["FINISHED"],disclosure:"GUEST"
   });
 }};
 const river={async record({event,digest:eventDigest}){
   state.riverCalls++;
   return receipt?.({event,digest:eventDigest})??signed("River",{
     verified:true,receipt_id:"lab:receipt-001",correlation_id:event.correlation_id,
     decision_id:event.warden_decision_ref,event_digest:eventDigest
   });
 }};
 const nonceStore={async consume(jti){if(throwNonce)throw Error("durable store offline");
   if(used.has(jti))return false;used.add(jti);return true;}};
 const resolver=createDoorResolver({registry,digitalMe,warden,river,nonceStore,
  publicKeys:keysOverride??publicKeys,clock});
 attempts.push(state);
 return {resolver,state};
}
const auth="Bearer test-lab-token-123456789";
async function rejection(handler,{code,status=null}){
 await assert.rejects(handler,err=>err instanceof DoorError && err.code===code &&
   (status===null||err.status===status));
}
// Strict request source: no client-supplied principal, policy, monetary or River authority.
assert.deepEqual(validateRequest(input),{
 asset_ref:"LAB-0001",door_ref:resource.door_ref,requested_state:"FINISHED",
 anchor_ref:"FLOOR_01",locale_hint:"en"
});
for(const field of ["buyer","disclosure","role","river","principal_ref","policy_decision_ref",
  "money","invitation_token","rights","auth"]){
 await rejection(async()=>validateRequest({...input,[field]:"OWNER"}),{code:"INVALID_DOOR_REQUEST",status:400});
}
await rejection(async()=>validateRequest({...input,requested_state:"OWNER"}),
 {code:"INVALID_DOOR_REQUEST",status:400});
await rejection(async()=>validateRequest({...input,locale_hint:"../../passwd"}),
 {code:"INVALID_DOOR_REQUEST",status:400});
const first=adapters();
const good=await first.resolver(input,{authorization:auth});
assert.equal(good.admission_status,"ADMITTED");
assert.equal(good.disclosure,"GUEST");
assert.equal(good.monetary_values,"DEPICTION_ONLY");
assert.equal(good.transaction_enabled,false);
assert.equal(good.policy_decision_ref,"warden:demo-001");
assert.equal(good.evidence_receipt_ref,"lab:receipt-001");
assert.equal(first.state.riverCalls,1);
const noIdentity=adapters();
await rejection(()=>noIdentity.resolver(input,{}),{code:"IDENTITY_REQUIRED",status:401});
assert.equal(noIdentity.state.wardenCalls,0);
const noAdapters=()=>createDoorResolver({});
await rejection(async()=>noAdapters(),{code:"INTEGRATION_UNAVAILABLE",status:503});
const unavailable=adapters({asset:{...resource,status:"DRAFT_UNVERIFIED"}});
await rejection(()=>unavailable.resolver(input,{authorization:auth}),{code:"RESOURCE_NOT_ADMITTED"});
assert.equal(unavailable.state.identityCalls,0);
const inactive=adapters({asset:{...resource,live_enabled:false}});
await rejection(()=>inactive.resolver(input,{authorization:auth}),{code:"RESOURCE_NOT_ADMITTED"});
const closed=adapters({asset:await a1204DraftRegistry.get("A-1204")});
const realInput={contract_version:"bmp.door-resolve.v0.1",asset_ref:"A-1204",
 door_ref:"VSR:BELGAUM:A-1204:DOOR",requested_state:"TODAY",anchor_ref:"FLOOR_01"};
await rejection(()=>closed.resolver(realInput,{authorization:auth}),{code:"RESOURCE_NOT_ADMITTED"});
assert.equal(closed.state.wardenCalls,0);
const tamperedIdentity=signed("DigitalMe",{principal_ref:"principal:lab-guest",identity_class:"GUEST",jti:"unique:tamper"});
tamperedIdentity.payload.principal_ref="principal:attacker";
await rejection(()=>adapters({identity:tamperedIdentity}).resolver(input,{authorization:auth}),{code:"SIGNATURE_INVALID"});
const expired=signed("DigitalMe",{principal_ref:"principal:lab-guest",identity_class:"GUEST",jti:"unique:expired",iat:s-300,exp:s-1});
await rejection(()=>adapters({identity:expired}).resolver(input,{authorization:auth}),{code:"ASSERTION_EXPIRED"});
const reused=signed("DigitalMe",{principal_ref:"principal:lab-guest",identity_class:"GUEST",jti:"unique:replay"});
const replay=adapters({identity:reused});
await replay.resolver(input,{authorization:auth});
await rejection(()=>replay.resolver(input,{authorization:auth}),{code:"ASSERTION_REPLAY",status:409});
await rejection(()=>adapters({throwNonce:true}).resolver(input,{authorization:auth}),{code:"NONCE_STORE_UNAVAILABLE",status:503});
const hostileDecisions=[
  p=>({...p,principal_ref:"principal:attacker"}),
  p=>({...p,correlation_id:"wrong"}),
  p=>({...p,resource_ref:"LAB:OTHER"}),
  p=>({...p,asset_ref:"LAB-OTHER"}),
  p=>({...p,door_ref:"VSR:OTHER"}),
  p=>({...p,anchor_ref:"ARCH_01"}),
  p=>({...p,allowed_states:["TODAY"]}),
  p=>({...p,disclosure:"QUALIFIED"}),
  p=>({...p,allowed:false}),
  p=>({...p,action:"ownership.transfer"})
];
for(const mutate of hostileDecisions){
 const instance=adapters({decision:call=>{
   const signedDecision=signed("Warden",{allowed:true,decision_id:"warden:attack",policy_version:"lab:v1",
     principal_ref:call.principal_ref,correlation_id:call.correlation_id,
     asset_ref:call.asset_ref,door_ref:call.door_ref,resource_ref:call.resource_ref,
     anchor_ref:call.anchor_ref,allowed_states:["FINISHED"],disclosure:"GUEST",
     action:"door.enter"});
   const p=mutate(signedDecision.payload);
   return signed("Warden",Object.fromEntries(Object.entries(p).filter(([k])=>!["iss","aud","iat","exp"].includes(k))));
 }});
 await rejection(()=>instance.resolver(input,{authorization:auth}),{code:"WARDEN_DENIED"});
 assert.equal(instance.state.riverCalls,0);
}
const badRiver=[
 p=>({...p,event_digest:"0".repeat(64)}),
 p=>({...p,verified:false}),
 p=>({...p,correlation_id:"wrong"}),
 p=>({...p,decision_id:"another"}),
 p=>({...p,receipt_id:null})
];
for(const mutate of badRiver){
 const instance=adapters({receipt:({event,digest:eventDigest})=>
   signed("River",mutate({verified:true,receipt_id:"lab:receipt",correlation_id:event.correlation_id,
    decision_id:event.warden_decision_ref,event_digest:eventDigest}))});
 await rejection(()=>instance.resolver(input,{authorization:auth}),{code:"EVIDENCE_UNAVAILABLE"});
}
const server=createDoorHttpServer();
await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
try{
 const port=server.address().port;
 const endpoint="http://127.0.0.1:"+port;
 const health=await fetch(endpoint+"/healthz");
 assert.equal(health.status,503);
 assert.equal((await health.json()).adapters_configured,false);
 const unavailableResponse=await fetch(endpoint+"/v1/door/resolve",{
   method:"POST",headers:{"content-type":"application/json","authorization":auth},body:JSON.stringify(realInput)
 });
 assert.equal(unavailableResponse.status,503);
 assert.equal((await unavailableResponse.json()).error,"INTEGRATION_UNAVAILABLE");
 const wrongMethod=await fetch(endpoint+"/v1/door/resolve");
 assert.equal(wrongMethod.status,405);
 const absent=await fetch(endpoint+"/unknown");
 assert.equal(absent.status,404);
}finally{await new Promise((resolve,reject)=>server.close(err=>err?reject(err):resolve()));}
console.log("PASS: R0.6 signed lab admission, A-1204 closed, authority spoofing, replay, expiry, Warden/River binding and loopback HTTP deny-by-default.");
