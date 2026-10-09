import assert from "node:assert/strict";
import {generateKeyPairSync,sign} from "node:crypto";
import {createProviderAdmissionGate,admissionDigest,assuranceRequirements} from "../service/provider-admission.mjs";
import {createReleaseAssuranceGate,releasePlanDigest,releaseAssuranceRequirements} from "../service/release-assurance.mjs";
import {createLabDeploymentExecutor,createInMemoryLabDriver,createInMemoryLabNonceStore,ExecutionError} from "../service/lab-deployment.mjs";

const now=Date.now(),sec=Math.floor(now/1000),clock=()=>now;
const sha40="b".repeat(40),scope={release_sha:sha40,environment:"lab",tenant_ref:"LAB:TENANT:01",asset_ref:"LAB-0001"};
const names=[...new Set([...assuranceRequirements.providers,...releaseAssuranceRequirements.stages,...releaseAssuranceRequirements.reviewers,"BNR"])];
const keys=Object.fromEntries(names.map(name=>[name,generateKeyPairSync("ed25519")]));
const root=name=>({kid:"lab-key-2026",key:keys[name].publicKey});
const signed=(name,aud,data,expiry=sec+100)=>{const payload={
 iss:name,kid:"lab-key-2026",aud,iat:sec-5,exp:expiry,...data
 };return {payload,signature:sign(null,Buffer.from(JSON.stringify(payload)),keys[name].privateKey).toString("base64url")};};
const r08="bmp-provider-admission",r09="bmp-release-assurance",r10="bmp-lab-execution";
const origins=Object.fromEntries(assuranceRequirements.providers.map(n=>[n,"https://"+n.toLowerCase()+".example.test"]));
const providers=assuranceRequirements.providers.map(name=>{
 return signed(name,r08,{...scope,name,operator_ref:"LAB:OPERATOR:"+name.toUpperCase(),origin:origins[name],evidence_refs:["river://lab/r08/"+name.toLowerCase()]});
});
const controls=assuranceRequirements.controls.map(control=>({control,evidence_ref:"river://lab/r08/control/"+control}));
const providerPacket={version:"bmp.provider-admission.v0.1",...scope,submitted_at:sec-10,expires_at:sec+150,
 provider_attestations:providers,control_evidence:controls,approvals:{}};
const providerDigest=admissionDigest(providerPacket);
for(const name of ["Warden","BNR"]){
 providerPacket.approvals[name]=signed(name,r08,{...scope,manifest_digest:providerDigest,decision:"APPROVE_FOR_REVIEW",policy_ref:"lab:policy"});
}
const providerGate=createProviderAdmissionGate({
 trustRoots:{providers:Object.fromEntries(assuranceRequirements.providers.map(x=>[x,root(x)])),reviewers:{Warden:root("Warden"),BNR:root("BNR")}},
 approvedOrigins:origins,expectedEnvironment:"lab",expectedReleaseSha:sha40,now:clock,
 verifyEvidence:async(ref)=>ref.startsWith("river://lab/r08/")
});
const providerResult=await providerGate.assess(providerPacket);
assert.equal(providerResult.status,"REVIEW_READY",JSON.stringify(providerResult.reasons));
const plan={deployment_ref:"LAB:DEPLOY:01",artifact_sha256:"c".repeat(64),
 rollback_artifact_sha256:"d".repeat(64),rollout_strategy:"CANARY",initial_percent:5,
 rollback_owner_ref:"LAB:ROLLBACK",runtime_ref:"LAB:RUNTIME:01",runbook_ref:"LAB:RUNBOOK",
 release_provenance_ref:"river://lab/r09/release",rollback_plan_ref:"river://lab/r09/rollback"};
const packet={version:"bmp.release-assurance.v0.1",...scope,submitted_at:sec-10,expires_at:sec+120,
 provider_packet:providerPacket,plan,attestations:{},approvals:{}};
const planDigest=releasePlanDigest(packet);
const releaseBinding={...scope,deployment_ref:plan.deployment_ref,manifest_digest:planDigest};
const r09Attestation=(name,data)=>signed(name,r09,{...releaseBinding,
 observed_at:sec-4,evidence_ref:"river://lab/r09/"+name.toLowerCase(),...data});
packet.attestations.RuntimeProbe=r09Attestation("RuntimeProbe",{
 status:"HEALTHY",runtime_ref:plan.runtime_ref,checks:[...releaseAssuranceRequirements.checks]});
packet.attestations.RollbackOperator=r09Attestation("RollbackOperator",{
 status:"DRILL_PASSED",rollback_artifact_sha256:plan.rollback_artifact_sha256,rollback_owner_ref:plan.rollback_owner_ref});
packet.attestations.Monitor=r09Attestation("Monitor",{
 status:"ACTIVE",runtime_ref:plan.runtime_ref,alert_route_tested:true,error_budget_guard_enabled:true});
for(const name of releaseAssuranceRequirements.reviewers){
 packet.approvals[name]=signed(name,r09,{...releaseBinding,decision:"APPROVE_FOR_REVIEW",policy_ref:"lab:policy"});
}
const releaseGate=createReleaseAssuranceGate({
 providerGate,trustRoots:{
  attestors:Object.fromEntries(releaseAssuranceRequirements.stages.map(x=>[x,root(x)])),
  reviewers:Object.fromEntries(releaseAssuranceRequirements.reviewers.map(x=>[x,root(x)]))
 },expectedEnvironment:"lab",expectedReleaseSha:sha40,now:clock,
 verifyEvidence:async(ref)=>ref.startsWith("river://lab/r09/")
});
const releaseReview=await releaseGate.assess(packet);
assert.equal(releaseReview.status,"RELEASE_REVIEW_READY",JSON.stringify(releaseReview.reasons));
assert.equal(releaseReview.deployment_activated,false);
const grantKeys={Warden:root("Warden"),ReleaseOwner:root("ReleaseOwner")};
const actor="LAB:OPERATOR:01";
function makeGrants(nonce,mutate={}){
 const common={...scope,deployment_ref:plan.deployment_ref,plan_digest:planDigest,
 operator_ref:actor,nonce,decision:"APPROVE_LAB_CANARY"};
 return Object.fromEntries(["Warden","ReleaseOwner"].map(name=>[
  name,signed(name,r10,{...common,...(mutate[name]??{})})
 ]));
}
async function rejection(fn,code){
 await assert.rejects(fn,err=>err instanceof ExecutionError&&err.code===code);
}
const store=createInMemoryLabNonceStore(),driver=createInMemoryLabDriver();
const executor=createLabDeploymentExecutor({releaseGate,publicKeys:grantKeys,nonceStore:store,labDriver:driver,now:clock});
const granted=makeGrants("LAB:nonce:01");
const good=await executor.execute({packet,approvals:granted,operator_ref:actor,nonce:"LAB:nonce:01"});
assert.equal(good.status,"CANARY_HEALTHY_SIMULATED");
assert.equal(good.deployment_activated,false);
assert.equal(good.operations_enabled,false);
assert.equal(good.public_qr_enabled,false);
assert.equal(good.evidence_status,"LAB_EVENTS_ONLY");
assert.equal(good.monetary_values,"DEPICTION_ONLY");
assert.equal(driver.snapshot().phase,"CANARY_HEALTHY_SIMULATED");
assert.deepEqual(driver.snapshot().events.map(x=>x.type),["CANARY_APPLIED_SIMULATED","HEALTH_CHECK_SIMULATED"]);
await rejection(()=>executor.execute({packet,approvals:granted,operator_ref:actor,nonce:"LAB:nonce:01"}),"EXECUTION_REPLAY_REJECTED");
const build=(opts={})=>createLabDeploymentExecutor({releaseGate,publicKeys:grantKeys,
 nonceStore:createInMemoryLabNonceStore(),labDriver:createInMemoryLabDriver(opts),now:clock});
const none=makeGrants("LAB:nonce:02");delete none.ReleaseOwner;
await rejection(()=>build().execute({packet,approvals:none,operator_ref:actor,nonce:"LAB:nonce:02"}),"EXECUTION_AUTHORITY_REQUIRED");
const tampered=makeGrants("LAB:nonce:03");tampered.Warden.payload.operator_ref="LAB:INTRUDER";
await rejection(()=>build().execute({packet,approvals:tampered,operator_ref:actor,nonce:"LAB:nonce:03"}),"EXECUTION_AUTHORITY_REQUIRED");
const alteredDigest=makeGrants("LAB:nonce:04",{ReleaseOwner:{plan_digest:"0".repeat(64)}});
await rejection(()=>build().execute({packet,approvals:alteredDigest,operator_ref:actor,nonce:"LAB:nonce:04"}),"EXECUTION_AUTHORITY_REQUIRED");
const wrongActor=makeGrants("LAB:nonce:05");
await rejection(()=>build().execute({packet,approvals:wrongActor,operator_ref:"LAB:OTHER",nonce:"LAB:nonce:05"}),"EXECUTION_AUTHORITY_REQUIRED");
const expired=makeGrants("LAB:nonce:06");expired.Warden=signed("Warden",r10,{
 ...scope,deployment_ref:plan.deployment_ref,plan_digest:planDigest,operator_ref:actor,
 nonce:"LAB:nonce:06",decision:"APPROVE_LAB_CANARY"},sec-1);
await rejection(()=>build().execute({packet,approvals:expired,operator_ref:actor,nonce:"LAB:nonce:06"}),"EXECUTION_AUTHORITY_REQUIRED");
const unapproved=makeGrants("LAB:nonce:07",{Warden:{decision:"APPROVE_DEPLOY"}});
await rejection(()=>build().execute({packet,approvals:unapproved,operator_ref:actor,nonce:"LAB:nonce:07"}),"EXECUTION_AUTHORITY_REQUIRED");
const nonLab={...packet,environment:"production"};
await rejection(()=>build().execute({packet:nonLab,approvals:makeGrants("LAB:nonce:08"),operator_ref:actor,nonce:"LAB:nonce:08"}),"LAB_SCOPE_REJECTED");
const pilot={...packet,asset_ref:"A-1204"};
await rejection(()=>build().execute({packet:pilot,approvals:makeGrants("LAB:nonce:09"),operator_ref:actor,nonce:"LAB:nonce:09"}),"LAB_SCOPE_REJECTED");
const brokenGate={async assess(){return {status:"BLOCKED"};}};
const refuses=createLabDeploymentExecutor({releaseGate:brokenGate,publicKeys:grantKeys,
 nonceStore:createInMemoryLabNonceStore(),labDriver:createInMemoryLabDriver(),now:clock});
await rejection(()=>refuses.execute({packet,approvals:makeGrants("LAB:nonce:10"),operator_ref:actor,nonce:"LAB:nonce:10"}),"RELEASE_REVIEW_REQUIRED");
const fakeReady={async assess(){return {status:"RELEASE_REVIEW_READY",plan_digest:planDigest,provider_status:"REVIEW_READY",
 operations_enabled:true,public_qr_enabled:false,deployment_activated:false};}};
const fake=createLabDeploymentExecutor({releaseGate:fakeReady,publicKeys:grantKeys,
 nonceStore:createInMemoryLabNonceStore(),labDriver:createInMemoryLabDriver(),now:clock});
await rejection(()=>fake.execute({packet,approvals:makeGrants("LAB:nonce:11"),operator_ref:actor,nonce:"LAB:nonce:11"}),"RELEASE_REVIEW_REQUIRED");
const offlineStore={async consume(){throw Error("offline");}};
const disconnected=createLabDeploymentExecutor({releaseGate,publicKeys:grantKeys,
 nonceStore:offlineStore,labDriver:createInMemoryLabDriver(),now:clock});
await rejection(()=>disconnected.execute({packet,approvals:makeGrants("LAB:nonce:12"),operator_ref:actor,nonce:"LAB:nonce:12"}),"EXECUTION_LEASE_UNAVAILABLE");
const alreadyUsed={async consume(){return false;}};
const replayStore=createLabDeploymentExecutor({releaseGate,publicKeys:grantKeys,
 nonceStore:alreadyUsed,labDriver:createInMemoryLabDriver(),now:clock});
await rejection(()=>replayStore.execute({packet,approvals:makeGrants("LAB:nonce:13"),operator_ref:actor,nonce:"LAB:nonce:13"}),"EXECUTION_REPLAY_REJECTED");
const rollbackDriver=createInMemoryLabDriver({failHealth:true});
const fallback=createLabDeploymentExecutor({releaseGate,publicKeys:grantKeys,
 nonceStore:createInMemoryLabNonceStore(),labDriver:rollbackDriver,now:clock});
const rolled=await fallback.execute({packet,approvals:makeGrants("LAB:nonce:14"),
 operator_ref:actor,nonce:"LAB:nonce:14"});
assert.equal(rolled.status,"ROLLED_BACK_SIMULATED");
assert.equal(rolled.rollback_attempted,true);
assert.equal(rollbackDriver.snapshot().phase,"ROLLED_BACK_SIMULATED");
const failDriver=createInMemoryLabDriver({failHealth:true,failRollback:true});
const fail=createLabDeploymentExecutor({releaseGate,publicKeys:grantKeys,
 nonceStore:createInMemoryLabNonceStore(),labDriver:failDriver,now:clock});
const escalated=await fail.execute({packet,approvals:makeGrants("LAB:nonce:15"),
 operator_ref:actor,nonce:"LAB:nonce:15"});
assert.equal(escalated.status,"ESCALATION_REQUIRED_SIMULATED");
assert.equal(escalated.deployment_activated,false);
assert.equal(failDriver.snapshot().phase,"ESCALATION_REQUIRED_SIMULATED");
assert.throws(()=>createLabDeploymentExecutor({releaseGate,publicKeys:grantKeys,
 nonceStore:createInMemoryLabNonceStore(),labDriver:{}}),e=>e.code==="LAB_EXECUTOR_NOT_CONFIGURED");
console.log("PASS: R0.10 R0.8→R0.9→lab-execution signed review, dual-authority, replay guard, deny-by-default, canary health, rollback and escalation.");
