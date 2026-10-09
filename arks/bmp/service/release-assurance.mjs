import {createHash,verify as verifySignature} from "node:crypto";
import {admissionDigest} from "./provider-admission.mjs";
const STAGES=Object.freeze(["RuntimeProbe","RollbackOperator","Monitor"]);
const REVIEWERS=Object.freeze(["Warden","BNR","ReleaseOwner"]);
const CHECKS=Object.freeze(["readiness","denial_behavior","health","error_budget","telemetry_stream"]);
const obj=v=>v!==null&&typeof v==="object"&&!Array.isArray(v);
const hash=v=>createHash("sha256").update(JSON.stringify(v)).digest("hex");
const hex=(v,n)=>typeof v==="string"&&new RegExp("^[a-f0-9]{"+n+"}$").test(v);
const id=v=>typeof v==="string"&&v.length>=3&&v.length<=128&&/^[A-Za-z0-9:_./-]+$/.test(v);
const evidence=v=>typeof v==="string"&&v.length>=12&&v.length<=240&&/^river:\/\/[A-Za-z0-9_./:-]+$/.test(v);
export const releaseAssuranceRequirements=Object.freeze({stages:STAGES,reviewers:REVIEWERS,checks:CHECKS});
export function releasePlanDigest(p){
 if(!obj(p))throw new TypeError("Release packet required");
 return hash({version:p.version,environment:p.environment,release_sha:p.release_sha,
  asset_ref:p.asset_ref,tenant_ref:p.tenant_ref,submitted_at:p.submitted_at,
  expires_at:p.expires_at,
  provider_manifest_digest:obj(p.provider_packet)?admissionDigest(p.provider_packet):null,
  plan:p.plan});
}
function signed(e,root,issuer,expected,seconds){
 if(!obj(e)||!obj(e.payload)||!obj(root)||!root.key||!id(root.kid)||
    typeof e.signature!=="string"||!/^[-_A-Za-z0-9]{86}$/.test(e.signature))return false;
 const p=e.payload;
 if(p.iss!==issuer||p.kid!==root.kid||p.aud!=="bmp-release-assurance"||
    !Number.isSafeInteger(p.iat)||!Number.isSafeInteger(p.exp)||
    p.exp<=seconds||p.iat>seconds+30||p.exp<=p.iat||p.exp-p.iat>600)return false;
 for(const [key,value] of Object.entries(expected))if(p[key]!==value)return false;
 try{
  const bytes=Buffer.from(e.signature,"base64url");
  return bytes.length===64&&verifySignature(null,Buffer.from(JSON.stringify(p)),root.key,bytes);
 }catch{return false;}
}
const recent=(t,seconds)=>Number.isSafeInteger(t)&&t<=seconds+30&&t>=seconds-90;
export function createReleaseAssuranceGate({providerGate,trustRoots={},verifyEvidence,
 expectedEnvironment,expectedReleaseSha,now=()=>Date.now()}={}){
 if(typeof providerGate?.assess!=="function"||typeof now!=="function")throw new Error("Provider gate and clock required");
 async function assess(packet){
  const reasons=[],fail=(code,detail="")=>{
   if(!reasons.some(x=>x.code===code&&x.detail===detail))reasons.push({code,detail});
  };
  let provider_status="UNAVAILABLE";
  const report=()=>Object.freeze({
   status:reasons.length?"BLOCKED":"RELEASE_REVIEW_READY",
   reasons:Object.freeze(reasons.map(x=>Object.freeze(x))),
   plan_digest:obj(packet)?releasePlanDigest(packet):null,
   provider_status,signed_assertions_accepted:reasons.length===0,
   live_health_observed_by_this_gate:false,
   operations_enabled:false,public_qr_enabled:false,
   deployment_activated:false,booking_confirmed:false,monetary_values:"DEPICTION_ONLY"
  });
  if(!obj(packet)){fail("RELEASE_PACKET_MISSING");return report();}
  const current=Math.floor(now()/1000),plan=packet.plan,provider=packet.provider_packet;
  if(packet.version!=="bmp.release-assurance.v0.1"||
     !["lab","staging","production"].includes(packet.environment)||
     !hex(packet.release_sha,40)||!id(packet.asset_ref)||!id(packet.tenant_ref)||
     !Number.isSafeInteger(packet.submitted_at)||!Number.isSafeInteger(packet.expires_at)||
     packet.submitted_at>current+30||packet.expires_at<=current||
     packet.expires_at<=packet.submitted_at||packet.expires_at-packet.submitted_at>600)
    fail("RELEASE_PACKET_INVALID");
  if(packet.asset_ref==="A-1204")fail("PILOT_ASSET_HARD_DENY");
  if(!expectedEnvironment||packet.environment!==expectedEnvironment||
     !expectedReleaseSha||packet.release_sha!==expectedReleaseSha)fail("EXPECTED_RELEASE_MISMATCH");
  if(!obj(plan)||!id(plan.deployment_ref)||!hex(plan.artifact_sha256,64)||
     !hex(plan.rollback_artifact_sha256,64)||plan.artifact_sha256===plan.rollback_artifact_sha256||
     plan.rollout_strategy!=="CANARY"||!Number.isSafeInteger(plan.initial_percent)||
     plan.initial_percent<1||plan.initial_percent>10||
     !id(plan.rollback_owner_ref)||!id(plan.runtime_ref)||!id(plan.runbook_ref)||
     !evidence(plan.release_provenance_ref)||!evidence(plan.rollback_plan_ref))
    fail("RELEASE_PLAN_INVALID");
  if(!obj(provider)||provider.release_sha!==packet.release_sha||
     provider.asset_ref!==packet.asset_ref||provider.tenant_ref!==packet.tenant_ref||
     provider.environment!==packet.environment)fail("PROVIDER_RELEASE_MISMATCH");
  // Re-evaluate signed R0.8 packet. A client-provided status is not provider approval.
  try{
   const checked=await providerGate.assess(provider);
   provider_status=checked?.status??"UNAVAILABLE";
   if(checked?.status!=="REVIEW_READY"||checked?.manifest_digest!==admissionDigest(provider)||
      checked?.operations_enabled!==false||checked?.public_qr_enabled!==false||
      checked?.deployment_activated!==false)fail("PROVIDER_REVIEW_NOT_READY");
  }catch{fail("PROVIDER_REVIEW_NOT_READY");}
  const planDigest=releasePlanDigest(packet);
  const binding={release_sha:packet.release_sha,environment:packet.environment,
   asset_ref:packet.asset_ref,tenant_ref:packet.tenant_ref,
   deployment_ref:plan?.deployment_ref,manifest_digest:planDigest};
  const refs=[];
  for(const issuer of STAGES){
   const env=packet.attestations?.[issuer],p=env?.payload;
   if(!signed(env,trustRoots?.attestors?.[issuer],issuer,binding,current)||
      !recent(p?.observed_at,current)||!evidence(p?.evidence_ref)){
    fail("RUNTIME_ATTESTATION_INVALID",issuer);continue;
   }
   if(issuer==="RuntimeProbe"&&(p.status!=="HEALTHY"||p.runtime_ref!==plan.runtime_ref||
      !Array.isArray(p.checks)||p.checks.length!==CHECKS.length||
      new Set(p.checks).size!==CHECKS.length||!CHECKS.every(x=>p.checks.includes(x)))){
    fail("RUNTIME_HEALTH_NOT_ATTESTED");continue;
   }
   if(issuer==="RollbackOperator"&&(p.status!=="DRILL_PASSED"||
      p.rollback_artifact_sha256!==plan.rollback_artifact_sha256||
      p.rollback_owner_ref!==plan.rollback_owner_ref)){
    fail("ROLLBACK_NOT_ATTESTED");continue;
   }
   if(issuer==="Monitor"&&(p.status!=="ACTIVE"||p.runtime_ref!==plan.runtime_ref||
      p.alert_route_tested!==true||p.error_budget_guard_enabled!==true)){
    fail("MONITORING_NOT_ATTESTED");continue;
   }
   refs.push(p.evidence_ref);
  }
  for(const reviewer of REVIEWERS){
   const env=packet.approvals?.[reviewer],p=env?.payload;
   if(!signed(env,trustRoots?.reviewers?.[reviewer],reviewer,binding,current)||
      p?.decision!=="APPROVE_FOR_REVIEW"||!id(p.policy_ref))
    fail("RELEASE_REVIEW_NOT_ATTESTED",reviewer);
  }
  if(evidence(plan?.release_provenance_ref))refs.push(plan.release_provenance_ref);
  if(evidence(plan?.rollback_plan_ref))refs.push(plan.rollback_plan_ref);
  if(typeof verifyEvidence!=="function")fail("RELEASE_EVIDENCE_VERIFIER_MISSING");
  else if(!reasons.length){
   for(const reference of new Set(refs)){
    let valid=false;
    try{
     valid=(await verifyEvidence(reference,{release_sha:packet.release_sha,
      environment:packet.environment,asset_ref:packet.asset_ref,
      tenant_ref:packet.tenant_ref,deployment_ref:plan.deployment_ref,
      manifest_digest:planDigest}))===true;
    }catch{valid=false;}
    if(!valid)fail("RELEASE_EVIDENCE_UNVERIFIED",reference);
   }
  }
  return report();
 }
 return Object.freeze({assess});
}
