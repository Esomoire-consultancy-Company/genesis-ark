import {createHash,randomUUID,verify as verifySignature} from "node:crypto";
import {releasePlanDigest} from "./release-assurance.mjs";

const object=v=>v!==null&&typeof v==="object"&&!Array.isArray(v);
const identifier=v=>typeof v==="string"&&v.length>=3&&v.length<=128&&/^[A-Za-z0-9:_./-]+$/.test(v);
const hex40=v=>typeof v==="string"&&/^[a-f0-9]{40}$/.test(v);
const hash=v=>createHash("sha256").update(JSON.stringify(v)).digest("hex");
const LAB=Symbol("isolated-lab-driver");
const ACTION="APPROVE_LAB_CANARY";
const AUD="bmp-lab-execution";
const APPROVERS=["Warden","ReleaseOwner"];

export class ExecutionError extends Error{
 constructor(code){super(code);this.name="ExecutionError";this.code=code;}
}
export function createInMemoryLabDriver({failHealth=false,failRollback=false}={}){
 let latest={phase:"IDLE",run_ref:null,artifact:null,events:[]};
 const event=(type,data={})=>{latest.events.push(Object.freeze({type,...data}));};
 return Object.freeze({
  [LAB]:true,
  async canary({run_ref,release_sha,artifact_sha256,initial_percent}){
   if(latest.phase!=="IDLE")throw new ExecutionError("LAB_DRIVER_ALREADY_USED");
   latest.phase="CANARY_SIMULATED";
   latest.run_ref=run_ref;latest.artifact=artifact_sha256;
   event("CANARY_APPLIED_SIMULATED",{release_sha,initial_percent});
   return {status:"SIMULATED",run_ref,artifact_sha256};
  },
  async health({run_ref}){
   if(latest.phase!=="CANARY_SIMULATED"||run_ref!==latest.run_ref)
    throw new ExecutionError("LAB_HEALTH_OUT_OF_SEQUENCE");
   const healthy=!failHealth;
   event("HEALTH_CHECK_SIMULATED",{healthy});
   if(healthy)latest.phase="CANARY_HEALTHY_SIMULATED";
   return {healthy,source:"LAB_SIMULATOR",run_ref};
  },
  async rollback({run_ref,rollback_artifact_sha256}){
   if(run_ref!==latest.run_ref||!["CANARY_SIMULATED","CANARY_HEALTHY_SIMULATED"].includes(latest.phase))
    throw new ExecutionError("LAB_ROLLBACK_OUT_OF_SEQUENCE");
   if(failRollback){latest.phase="ESCALATION_REQUIRED_SIMULATED";
    event("ROLLBACK_FAILED_SIMULATED");throw new ExecutionError("LAB_ROLLBACK_FAILED");}
   latest.phase="ROLLED_BACK_SIMULATED";latest.artifact=rollback_artifact_sha256;
   event("ROLLBACK_APPLIED_SIMULATED",{rollback_artifact_sha256});
   return {status:"SIMULATED",run_ref,rollback_artifact_sha256};
  },
  snapshot(){
   return Object.freeze({phase:latest.phase,run_ref:latest.run_ref,artifact:latest.artifact,
    events:Object.freeze(latest.events.map(x=>({...x})))});
  }
 });
}
export function createInMemoryLabNonceStore(){
 const used=new Set();
 return Object.freeze({
  async consume(k){if(used.has(k))return false;used.add(k);return true;}
 });
}
function signedGrant(envelope,root,issuer,expected,seconds){
 if(!object(envelope)||!object(envelope.payload)||!object(root)||!root.key||
    !identifier(root.kid)||typeof envelope.signature!=="string"||
    !/^[-_A-Za-z0-9]{86}$/.test(envelope.signature))return false;
 const p=envelope.payload;
 if(p.iss!==issuer||p.kid!==root.kid||p.aud!==AUD||p.decision!==ACTION||
    !Number.isSafeInteger(p.iat)||!Number.isSafeInteger(p.exp)||p.iat>seconds+30||
    p.exp<=seconds||p.exp<=p.iat||p.exp-p.iat>120)return false;
 if(Object.entries(expected).some(([k,v])=>p[k]!==v))return false;
 try{
  const sig=Buffer.from(envelope.signature,"base64url");
  return sig.length===64&&verifySignature(null,Buffer.from(JSON.stringify(p)),root.key,sig);
 }catch{return false;}
}
export function createLabDeploymentExecutor({releaseGate,publicKeys={},nonceStore,labDriver,now=()=>Date.now()}={}){
 if(typeof releaseGate?.assess!=="function"||
    !nonceStore||typeof nonceStore.consume!=="function"||
    !labDriver||labDriver[LAB]!==true||typeof now!=="function")
   throw new ExecutionError("LAB_EXECUTOR_NOT_CONFIGURED");
 let inFlight=false;
 async function execute({packet,approvals,operator_ref,nonce}={}){
  if(inFlight)throw new ExecutionError("LAB_EXECUTOR_BUSY");
  if(!object(packet)||packet.environment!=="lab"||packet.asset_ref==="A-1204"||
     !hex40(packet.release_sha)||!identifier(operator_ref)||!identifier(nonce)||
     !object(approvals)||!object(packet.plan)||
     !identifier(packet.plan.deployment_ref)||
     !/^[a-f0-9]{64}$/.test(packet.plan.artifact_sha256??"")||
     !/^[a-f0-9]{64}$/.test(packet.plan.rollback_artifact_sha256??""))
   throw new ExecutionError("LAB_SCOPE_REJECTED");
  inFlight=true;
  try{
   const review=await releaseGate.assess(packet);
   const plan_digest=releasePlanDigest(packet);
   if(review?.status!=="RELEASE_REVIEW_READY"||
      review.plan_digest!==plan_digest||review.provider_status!=="REVIEW_READY"||
      review.operations_enabled!==false||review.public_qr_enabled!==false||
      review.deployment_activated!==false)
    throw new ExecutionError("RELEASE_REVIEW_REQUIRED");
   const grant={
    release_sha:packet.release_sha,asset_ref:packet.asset_ref,
    environment:"lab",tenant_ref:packet.tenant_ref,
    deployment_ref:packet.plan.deployment_ref,plan_digest,operator_ref,nonce
   };
   const seconds=Math.floor(now()/1000);
   for(const name of APPROVERS)
    if(!signedGrant(approvals[name],publicKeys[name],name,grant,seconds))
     throw new ExecutionError("EXECUTION_AUTHORITY_REQUIRED");
   // Caller must provide a durable atomic store for any future non-lab executor.
   // This specific in-memory store exists exclusively for ephemeral CI tests.
   let acquired=false;
   try{acquired=await nonceStore.consume("bmp-lab:"+packet.tenant_ref+":"+nonce,Math.min(
     approvals.Warden.payload.exp,approvals.ReleaseOwner.payload.exp));}
   catch{throw new ExecutionError("EXECUTION_LEASE_UNAVAILABLE");}
   if(acquired!==true)throw new ExecutionError("EXECUTION_REPLAY_REJECTED");
   const run_ref="lab:"+randomUUID();
   const entry={run_ref,release_sha:packet.release_sha,artifact_sha256:packet.plan.artifact_sha256,
    initial_percent:packet.plan.initial_percent};
   let applied=false,rollback_attempted=false,health=null,reason=null;
   try{
    const result=await labDriver.canary(entry);
    if(result?.status!=="SIMULATED"||result.run_ref!==run_ref||
       result.artifact_sha256!==entry.artifact_sha256)
     throw new ExecutionError("CANARY_RESULT_INVALID");
    applied=true;
    health=await labDriver.health({run_ref});
    if(health?.source!=="LAB_SIMULATOR"||health.run_ref!==run_ref||health.healthy!==true)
     throw new ExecutionError("POST_CANARY_HEALTH_FAILED");
   }catch(e){
    reason=e instanceof ExecutionError?e.code:"CANARY_SIMULATION_FAILED";
    // Even a possibly-applied canary is rolled back on any canary or probe exception.
    // Any uncertain rollback state demands independent operator escalation.
    rollback_attempted=true;
    try{
     const rb=await labDriver.rollback({run_ref,
      rollback_artifact_sha256:packet.plan.rollback_artifact_sha256});
     if(rb?.status!=="SIMULATED"||rb.run_ref!==run_ref)
      throw new ExecutionError("ROLLBACK_RESULT_INVALID");
     return Object.freeze({status:"ROLLED_BACK_SIMULATED",run_ref,reason,
      rollback_attempted,operations_enabled:false,public_qr_enabled:false,
      deployment_activated:false,evidence_status:"LAB_EVENTS_ONLY",monetary_values:"DEPICTION_ONLY"});
    }catch{
     return Object.freeze({status:"ESCALATION_REQUIRED_SIMULATED",run_ref,reason,
      rollback_attempted,operations_enabled:false,public_qr_enabled:false,
      deployment_activated:false,evidence_status:"LAB_EVENTS_ONLY",monetary_values:"DEPICTION_ONLY"});
    }
   }
   return Object.freeze({status:"CANARY_HEALTHY_SIMULATED",run_ref,
    rollback_attempted:false,operations_enabled:false,public_qr_enabled:false,
    deployment_activated:false,evidence_status:"LAB_EVENTS_ONLY",
    health_observed:"LAB_ONLY",monetary_values:"DEPICTION_ONLY"});
  }finally{inFlight=false;}
 }
 return Object.freeze({execute,mode:"LAB_ONLY_R0.10"});
}
