import assert from "node:assert/strict";
import {generateKeyPairSync,sign} from "node:crypto";
import {createServiceFederation} from "../service/federation.mjs";
import {createFederatedAdapters} from "../service/adapters.mjs";
import {createFederationTransport} from "../service/transport.mjs";
import {DoorError,AUDIENCE} from "../service/resolver.mjs";

const now=Date.now(),nowSeconds=Math.floor(now/1000);
const fixed=()=>now;
const names=["Genesis","DigitalMe","Warden","River","Quantum"];
const keys=Object.fromEntries(names.map(name=>[name,generateKeyPairSync("ed25519")]));
const publicKeys=Object.fromEntries(names.map(name=>[name,keys[name].publicKey]));
const signMessage=(issuer,data)=>{
 const payload={iss:issuer,aud:AUDIENCE,iat:nowSeconds-4,exp:nowSeconds+180,...data};
 return {payload,signature:sign(null,Buffer.from(JSON.stringify(payload)),keys[issuer].privateKey).toString("base64url")};
};
const origins=Object.fromEntries(names.map(n=>[n,"https://"+n.toLowerCase()+".example.test"]));
const tokens=[];
const getServiceToken=async name=>{tokens.push(name);return "Bearer test-service-credential-123456789";};
const asset={
 asset_ref:"LAB-0001",door_ref:"VSR:LAB:0001:DOOR",room_ref:"VSR:LAB:0001:ROOM",
 resource_ref:"LAB:ROOM:0001",status:"VERIFIED_ACTIVE",live_enabled:true,
 max_disclosure:"GUEST",states:["TODAY","FINISHED"],anchors:["FLOOR_01"]
};
const input={
 contract_version:"bmp.door-resolve.v0.1",asset_ref:"LAB-0001",
 door_ref:asset.door_ref,requested_state:"FINISHED",anchor_ref:"FLOOR_01"
};
const auth="Bearer test-digitalme-credential-123456789";
const requested_slot=new Date(Math.ceil((now+3600000)/60000)*60000).toISOString().replace(".000Z","Z");
const used=new Set();
const nonceStore={async consume(value){if(used.has(value))return false;used.add(value);return true;}};
async function fails(fn,code){await assert.rejects(fn,e=>e instanceof DoorError&&e.code===code);}
assert.throws(()=>createFederationTransport({origins:{...origins,Genesis:"http://genesis.example.test"},getServiceToken}),e=>e.code==="FEDERATION_ENDPOINT_REJECTED");
assert.throws(()=>createFederationTransport({origins:{...origins,Genesis:"https://127.0.0.1"},getServiceToken}),e=>e.code==="FEDERATION_ENDPOINT_REJECTED");
assert.throws(()=>createFederatedAdapters({origins,publicKeys,getServiceToken}),e=>e.code==="FEDERATION_NOT_CONFIGURED");
const sequence=[];
let nonceIndex=0;
function mockFetch(url,options={}){
 const u=new URL(url), name=names.find(n=>u.hostname===n.toLowerCase()+".example.test");
 if(!name)throw Error("unexpected host");
 if(options.redirect!=="manual")throw Error("redirect not prohibited");
 if(options.headers.authorization!=="Bearer test-service-credential-123456789")throw Error("missing service token");
 const body=options.body?JSON.parse(options.body):null;
 sequence.push({name,path:u.pathname,body,method:options.method});
 let payload;
 switch(name){
  case "Genesis":
   assert.equal(options.method,"GET");
   assert.equal(u.pathname,"/v1/assets/LAB-0001");
   payload=signMessage(name,{asset_ref:"LAB-0001",resource:asset});break;
  case "DigitalMe":
   assert.equal(u.pathname,"/v1/assertions/resolve");
   assert.equal(body.authorization,auth);
   payload=signMessage(name,{principal_ref:"lab:guest",identity_class:"GUEST",
     jti:"lab:assertion:"+ ++nonceIndex});break;
  case "Warden":
   assert.equal(u.pathname,"/v1/admissions/evaluate");
   if(body.action==="door.enter"){
    payload=signMessage(name,{allowed:true,decision_id:"lab:decision:door",policy_version:"lab:policy",
      principal_ref:body.principal_ref,correlation_id:body.correlation_id,
      asset_ref:body.asset_ref,door_ref:body.door_ref,resource_ref:body.resource_ref,
      anchor_ref:body.anchor_ref,allowed_states:["FINISHED"],
      disclosure:"GUEST",action:body.action});
   }else{
    assert.equal(body.action,"quantum.session.request");
    payload=signMessage(name,{allowed:true,decision_id:"lab:decision:quantum",
      action:body.action,correlation_id:body.correlation_id,
      room_ref:body.room_ref,requested_slot:body.requested_slot,
      session_request_ref:body.session_request_ref,door_decision_ref:body.door_decision_ref});
   }
   break;
  case "River":
   assert.equal(u.pathname,"/v1/evidence/ingest");
   assert.equal(body.event_digest.length,64);
   payload=signMessage(name,{verified:true,receipt_id:"lab:receipt:"+body.event.event_type,
     correlation_id:body.event.correlation_id,decision_id:body.event.warden_decision_ref,
     event_digest:body.event_digest});break;
  case "Quantum":
   assert.equal(u.pathname,"/v1/sessions/request");
   payload=signMessage(name,{status:"PENDING",correlation_id:body.correlation_id,
     room_ref:body.room_ref,decision_id:body.decision_id,
     requested_slot:body.requested_slot,session_ref:"lab:session:pending"});break;
  default:throw Error("unknown role");
 }
 return Promise.resolve(new Response(JSON.stringify(payload),{
  status:200,headers:{"content-type":"application/json"}
 }));
}
const base={origins,publicKeys,getServiceToken,nonceStore,allowedAssets:["LAB-0001","A-1204"],
 fetchImpl:mockFetch,clock:fixed};
const federation=createServiceFederation(base);
const admit=await federation.resolver(input,{authorization:auth});
assert.equal(admit.admission_status,"ADMITTED");
assert.equal(admit.disclosure,"GUEST");
assert.equal(admit.monetary_values,"DEPICTION_ONLY");
assert.equal(admit.transaction_enabled,false);
assert.equal(admit.evidence_receipt_ref,"lab:receipt:DOOR_ADMISSION");
assert.deepEqual(sequence.slice(0,4).map(x=>x.name),["Genesis","DigitalMe","Warden","River"]);
assert.ok(tokens.length>=4);
const pending=await federation.requestQuantumSession(admit,{requested_slot});
assert.equal(pending.status,"PENDING");
assert.equal(pending.booking_confirmed,false);
assert.equal(pending.monetary_values,"DEPICTION_ONLY");
assert.equal(pending.evidence_receipt_ref,"lab:receipt:QUANTUM_SESSION_REQUEST");
assert.deepEqual(sequence.slice(4).map(x=>x.name),["Warden","Quantum","River"]);
await fails(()=>federation.requestQuantumSession({...admit},{requested_slot}),"DOOR_ADMISSION_REQUIRED");
await fails(()=>federation.requestQuantumSession(admit,{requested_slot:"2020-01-01T00:00:00Z"}),"INVALID_SESSION_REQUEST");
await fails(()=>federation.requestQuantumSession(admit,{requested_slot:"2035-01-01T00:00:00Z"}),"INVALID_SESSION_REQUEST");
await fails(()=>federation.resolver({...input,asset_ref:"A-1204",door_ref:"VSR:BELGAUM:A-1204:DOOR",requested_state:"TODAY"},{authorization:auth}),"RESOURCE_NOT_ADMITTED");
await fails(()=>federation.resolver({...input,asset_ref:"OTHER-001"},{authorization:auth}),"RESOURCE_NOT_ADMITTED");
const before=sequence.length;
assert.equal((await federation.requestQuantumSession(admit,{requested_slot})).status,"PENDING");
assert.equal(sequence.length,before+3);
const expired=createServiceFederation({...base,clock:()=>now+3600000});
await fails(()=>expired.requestQuantumSession(admit,{requested_slot}),"DOOR_ADMISSION_REQUIRED");
const inactive=await createFederatedAdapters(base);
const draft=await inactive.registry.get("A-1204");
assert.equal(draft.status,"DRAFT_UNVERIFIED");
assert.equal(draft.live_enabled,false);
const transport=createFederationTransport({
 origins,getServiceToken,fetchImpl:async()=>new Response(JSON.stringify({okay:true}),{status:307,headers:{"content-type":"application/json"}})
});
await fails(()=>transport.invoke("Genesis","/v1/status"),"FEDERATION_UNAVAILABLE");
const wrongType=createFederationTransport({
 origins,getServiceToken,fetchImpl:async()=>new Response("hello",{status:200,headers:{"content-type":"text/plain"}})
});
await fails(()=>wrongType.invoke("Genesis","/v1/status"),"FEDERATION_BAD_RESPONSE");
const tooBig=createFederationTransport({
 origins,getServiceToken,fetchImpl:async()=>new Response(JSON.stringify({payload:"x".repeat(70000)}),{status:200,headers:{"content-type":"application/json"}})
});
await fails(()=>tooBig.invoke("Genesis","/v1/status"),"FEDERATION_BAD_RESPONSE");
await fails(()=>transport.invoke("Genesis","https://bad.example.test"),"FEDERATION_REQUEST_REJECTED");
assert.equal(sequence.filter(x=>x.name==="Genesis").length,1);

// R0.7 adverse cross-service behavior: an upstream "success" without correct signature
// and request binding is never a verified operation.
async function intercepted(name,predicate,change){
 return async(url,opts)=>{
  const raw=await mockFetch(url,opts);
  const service=names.find(n=>new URL(url).hostname===n.toLowerCase()+".example.test");
  if(service!==name||!predicate(opts))return raw;
  const packet=await raw.json();
  const modified=change(packet,opts);
  return new Response(JSON.stringify(modified),{status:200,headers:{"content-type":"application/json"}});
 };
}
const genesisSpoof=await intercepted("Genesis",()=>true,packet=>
 signMessage("Genesis",{...packet.payload,asset_ref:"LAB-OTHER"}));
await fails(()=>createServiceFederation({...base,fetchImpl:genesisSpoof}).resolver(input,{authorization:auth}),"GENESIS_BINDING_INVALID");
const genesisTamper=await intercepted("Genesis",()=>true,packet=>{
 packet.payload.asset_ref="LAB-OTHER";return packet;
});
await fails(()=>createServiceFederation({...base,fetchImpl:genesisTamper}).resolver(input,{authorization:auth}),"SIGNATURE_INVALID");
const quantumConfirm=await intercepted("Quantum",()=>true,packet=>
 signMessage("Quantum",{...packet.payload,status:"CONFIRMED"}));
const confirmFed=createServiceFederation({...base,fetchImpl:quantumConfirm});
const confirmAdmission=await confirmFed.resolver(input,{authorization:auth});
await fails(()=>confirmFed.requestQuantumSession(confirmAdmission,{requested_slot}),"QUANTUM_RESPONSE_UNVERIFIED");
const quantumWrongDecision=await intercepted("Quantum",()=>true,packet=>
 signMessage("Quantum",{...packet.payload,decision_id:"lab:foreign-decision"}));
const wrongQuantumFed=createServiceFederation({...base,fetchImpl:quantumWrongDecision});
const wrongQuantumAdmission=await wrongQuantumFed.resolver(input,{authorization:auth});
await fails(()=>wrongQuantumFed.requestQuantumSession(wrongQuantumAdmission,{requested_slot}),"QUANTUM_RESPONSE_UNVERIFIED");
const sessionDeny=await intercepted("Warden",opts=>JSON.parse(opts.body).action==="quantum.session.request",packet=>
 signMessage("Warden",{...packet.payload,allowed:false}));
const deniedFed=createServiceFederation({...base,fetchImpl:sessionDeny});
const deniedAdmission=await deniedFed.resolver(input,{authorization:auth});
await fails(()=>deniedFed.requestQuantumSession(deniedAdmission,{requested_slot}),"WARDEN_SESSION_DENIED");
const riverMismatch=await intercepted("River",opts=>JSON.parse(opts.body).event.event_type==="QUANTUM_SESSION_REQUEST",packet=>
 signMessage("River",{...packet.payload,event_digest:"0".repeat(64)}));
const mismatchFed=createServiceFederation({...base,fetchImpl:riverMismatch});
const mismatchAdmission=await mismatchFed.resolver(input,{authorization:auth});
await fails(()=>mismatchFed.requestQuantumSession(mismatchAdmission,{requested_slot}),"EVIDENCE_UNAVAILABLE");
let advancingClock=now;
const expiryFed=createServiceFederation({...base,clock:()=>advancingClock});
const expiringAdmission=await expiryFed.resolver(input,{authorization:auth});
advancingClock=now+200000;
await fails(()=>expiryFed.requestQuantumSession(expiringAdmission,{requested_slot}),"DOOR_ADMISSION_EXPIRED");
// Full local HTTP stack: request -> registry -> DigitalMe -> Warden -> River -> response.
// Transport is completely substituted; no external host, secret or live QR is touched.
const {createDoorHttpServer}=await import("../service/http.mjs");
const bound=createDoorHttpServer({resolver:federation.resolver});
await new Promise(resolve=>bound.listen(0,"127.0.0.1",resolve));
try{
 const url="http://127.0.0.1:"+bound.address().port+"/v1/door/resolve";
 const goodHttp=await fetch(url,{
   method:"POST",headers:{"content-type":"application/json","authorization":auth},
   body:JSON.stringify(input)
 });
 assert.equal(goodHttp.status,200);
 const body=await goodHttp.json();
 assert.equal(body.admission_status,"ADMITTED");
 assert.equal(body.monetary_values,"DEPICTION_ONLY");
 const blocked=await fetch(url,{
   method:"POST",headers:{"content-type":"application/json","authorization":auth},
   body:JSON.stringify({...input,asset_ref:"A-1204",door_ref:"VSR:BELGAUM:A-1204:DOOR",requested_state:"TODAY"})
 });
 assert.equal(blocked.status,403);
 assert.equal((await blocked.json()).error,"RESOURCE_NOT_ADMITTED");
}finally{await new Promise((done,fail)=>bound.close(e=>e?fail(e):done()));}

console.log("PASS: R0.7 five-provider signed lab federation, Quantum pending-only, hard A-1204 deny, no forged admissions, HTTP end-to-end, adversarial federation restrictions and depiction-only guard.");
