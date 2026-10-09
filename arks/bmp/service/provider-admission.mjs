import {createHash,verify as verifySignature} from "node:crypto";
import {isIP} from "node:net";
const PROVIDERS=Object.freeze(["Genesis","DigitalMe","Warden","River","Quantum"]);
const CONTROLS=Object.freeze(["operator_authority","domain_tls","egress_policy","durable_replay_store","tenant_isolation","rate_limits","key_rotation","river_custody","rollback_test"]);
const ALLOWED_ENV=Object.freeze(["lab","staging","production"]);
const isObj=v=>v!==null&&typeof v==="object"&&!Array.isArray(v);
const sha=v=>createHash("sha256").update(JSON.stringify(v)).digest("hex");
const ref=v=>typeof v==="string"&&v.length>=12&&v.length<=240&&/^river:\/\/[A-Za-z0-9_./:-]+$/.test(v);
const id=v=>typeof v==="string"&&v.length>1&&v.length<=128&&/^[A-Za-z0-9:_./-]+$/.test(v);
const sha40=v=>typeof v==="string"&&/^[a-f0-9]{40}$/.test(v);
function endpoint(v){
 if(typeof v!=="string")return false;
 try{
  const u=new URL(v);
  return u.protocol==="https:"&&u.pathname==="/"&&!u.search&&!u.hash&&
   !u.username&&!u.password&&!u.port&&u.hostname.includes(".")&&!isIP(u.hostname)&&
   u.hostname!=="localhost"&&u.origin===v.replace(/\/$/,"");
 }catch{return false;}
}
function checkSignature(e,root,issuer,now,expected){
 if(!isObj(e)||!isObj(e.payload)||!root||!root.key||!id(root.kid)||
    typeof e.signature!=="string"||!/^[-_A-Za-z0-9]{86}$/.test(e.signature))return false;
 const p=e.payload;
 if(p.iss!==issuer||p.kid!==root.kid||p.aud!=="bmp-provider-admission"||
   !Number.isSafeInteger(p.iat)||!Number.isSafeInteger(p.exp)||
   p.exp<=now||p.iat>now+30||p.exp<=p.iat||p.exp-p.iat>900)return false;
 for(const [k,v] of Object.entries(expected))if(p[k]!==v)return false;
 try{
  const signature=Buffer.from(e.signature,"base64url");
  return signature.length===64&&verifySignature(null,Buffer.from(JSON.stringify(p)),root.key,signature);
 }catch{return false;}
}
export function admissionDigest(manifest){
 const {approvals,...unsigned}=manifest;
 return sha(unsigned);
}
export function createProviderAdmissionGate({
 trustRoots={},approvedOrigins={},verifyEvidence,expectedEnvironment,expectedReleaseSha,
 now=()=>Date.now()
}={}){
 if(typeof now!=="function")throw new Error("Clock function required");
 async function assess(packet){
  const reasons=[];
  const fail=(code,detail="")=>{if(!reasons.some(x=>x.code===code&&x.detail===detail))reasons.push({code,detail});};
  if(!isObj(packet)){fail("PACKET_MISSING");return Object.freeze({status:"BLOCKED",reasons,operations_enabled:false,public_qr_enabled:false,deployment_activated:false});}
  if(packet.version!=="bmp.provider-admission.v0.1"||!ALLOWED_ENV.includes(packet.environment)||
     !sha40(packet.release_sha)||!id(packet.tenant_ref)||!id(packet.asset_ref)||
     !Number.isSafeInteger(packet.submitted_at)||!Number.isSafeInteger(packet.expires_at)||
     packet.submitted_at>Math.floor(now()/1000)+30||packet.expires_at<=Math.floor(now()/1000)||
     packet.expires_at-packet.submitted_at>900)fail("MANIFEST_INVALID");
  if(packet.asset_ref==="A-1204")fail("PILOT_ASSET_NOT_ADMISSIBLE");
  if(!expectedEnvironment||packet.environment!==expectedEnvironment||
     !expectedReleaseSha||packet.release_sha!==expectedReleaseSha)fail("RELEASE_BINDING_INVALID");
  const expectedFields={environment:packet.environment,release_sha:packet.release_sha,asset_ref:packet.asset_ref,tenant_ref:packet.tenant_ref};
  if(!Array.isArray(packet.provider_attestations)||packet.provider_attestations.length!==PROVIDERS.length)
    fail("PROVIDER_SET_INCOMPLETE");
  const providers=Array.isArray(packet.provider_attestations)?packet.provider_attestations:[];
  const providerNames=providers.map(x=>x?.payload?.name);
  if(new Set(providerNames).size!==PROVIDERS.length||
     !PROVIDERS.every(x=>providerNames.includes(x)))fail("PROVIDER_SET_INVALID");
  const refs=[];
  const current=Math.floor(now()/1000);
  for(const name of PROVIDERS){
   const e=providers.find(x=>x?.payload?.name===name),p=e?.payload;
   if(!isObj(p)||!id(p.operator_ref)||!endpoint(p.origin)||
      !endpoint(approvedOrigins?.[name])||p.origin!==approvedOrigins[name]||
      !Array.isArray(p.evidence_refs)||p.evidence_refs.length===0||
      p.evidence_refs.some(x=>!ref(x))||
      !checkSignature(e,trustRoots?.providers?.[name],name,current,{...expectedFields,name}))
     fail("PROVIDER_NOT_ADMITTED",name);
   else refs.push(...p.evidence_refs);
  }
  if(!Array.isArray(packet.control_evidence)||packet.control_evidence.length!==CONTROLS.length)
    fail("ASSURANCE_CONTROLS_INCOMPLETE");
  const controls=Array.isArray(packet.control_evidence)?packet.control_evidence:[];
  if(new Set(controls.map(x=>x?.control)).size!==CONTROLS.length||
     !CONTROLS.every(x=>controls.some(e=>e?.control===x&&ref(e.evidence_ref))))
    fail("ASSURANCE_CONTROLS_INVALID");
  else refs.push(...controls.map(x=>x.evidence_ref));
  const signedDigest=admissionDigest(packet);
  for(const name of ["Warden","BNR"]){
   const p=packet.approvals?.[name]?.payload;
   if(!isObj(p)||p.decision!=="APPROVE_FOR_REVIEW"||!id(p.policy_ref)||
      !checkSignature(packet.approvals[name],trustRoots?.reviewers?.[name],name,current,{
       ...expectedFields,manifest_digest:signedDigest
      }))fail("REVIEW_NOT_ATTESTED",name);
  }
  if(typeof verifyEvidence!=="function")fail("EVIDENCE_VERIFIER_UNAVAILABLE");
  else if(!reasons.length){
   for(const evidenceRef of new Set(refs)){
    let valid=false;
    try{valid=await verifyEvidence(evidenceRef,{tenant_ref:packet.tenant_ref,asset_ref:packet.asset_ref,release_sha:packet.release_sha});}
    catch{valid=false;}
    if(valid!==true)fail("EVIDENCE_NOT_VERIFIED",evidenceRef);
   }
  }
  return Object.freeze({
    status:reasons.length?"BLOCKED":"REVIEW_READY",
    reasons:Object.freeze(reasons.map(x=>Object.freeze(x))),
    manifest_digest:signedDigest,
    provider_count:reasons.length?0:PROVIDERS.length,
    evidence_count:reasons.length?0:new Set(refs).size,
    environment:packet.environment,
    operations_enabled:false,
    public_qr_enabled:false,
    deployment_activated:false,
    commercial_mode:"DEPICTION_ONLY"
  });
 }
 return Object.freeze({assess});
}
export const assuranceRequirements=Object.freeze({providers:PROVIDERS,controls:CONTROLS});
