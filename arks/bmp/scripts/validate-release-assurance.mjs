import assert from "node:assert/strict";
import {generateKeyPairSync,sign} from "node:crypto";
import {admissionDigest} from "../service/provider-admission.mjs";
import {createReleaseAssuranceGate,releasePlanDigest,releaseAssuranceRequirements} from "../service/release-assurance.mjs";
const time=Date.now(),seconds=Math.floor(time/1000),now=()=>time;
const release_sha="edcdc6128ccab39559a02004d3a790f10451125b";
const binding={environment:"staging",tenant_ref:"LAB:TENANT:01",asset_ref:"LAB-0001",release_sha};
const stages=[...releaseAssuranceRequirements.stages],reviewers=[...releaseAssuranceRequirements.reviewers];
const keys=Object.fromEntries([...stages,...reviewers].map(k=>[k,generateKeyPairSync("ed25519")]));
const roots=Object.fromEntries(Object.entries(keys).map(([k,v])=>[k,{kid:"lab-key-20261010",key:v.publicKey}]));
const trustRoots={attestors:Object.fromEntries(stages.map(x=>[x,roots[x]])),
 reviewers:Object.fromEntries(reviewers.map(x=>[x,roots[x]]))};
const signEnvelope=(issuer,fields)=>{
 const payload={iss:issuer,kid:"lab-key-20261010",aud:"bmp-release-assurance",
  iat:seconds-5,exp:seconds+180,...fields};
 return {payload,signature:sign(null,Buffer.from(JSON.stringify(payload)),keys[issuer].privateKey).toString("base64url")};
};
const providerPacket={version:"bmp.provider-admission.v0.1",...binding,
 submitted_at:seconds-20,expires_at:seconds+300,
 provider_attestations:[],control_evidence:[],approvals:{}};
const plan={deployment_ref:"LAB:DEPLOYMENT:01",artifact_sha256:"a".repeat(64),
 rollback_artifact_sha256:"b".repeat(64),rollout_strategy:"CANARY",initial_percent:5,
 rollback_owner_ref:"LAB:ROLLBACK:OP",runtime_ref:"LAB:RUNTIME:01",runbook_ref:"LAB:RUNBOOK:01",
 release_provenance_ref:"river://lab/release/provenance",rollback_plan_ref:"river://lab/release/rollback"};
const packet={version:"bmp.release-assurance.v0.1",...binding,
 submitted_at:seconds-20,expires_at:seconds+180,provider_packet:providerPacket,
 plan,attestations:{},approvals:{}};
const digest=releasePlanDigest(packet),scope={...binding,deployment_ref:plan.deployment_ref,manifest_digest:digest};
const evidenceRefs=new Set([plan.release_provenance_ref,plan.rollback_plan_ref]);
function attestation(issuer,values){
 const evidence_ref="river://lab/assurance/"+issuer.toLowerCase();evidenceRefs.add(evidence_ref);
 return signEnvelope(issuer,{...scope,observed_at:seconds-10,evidence_ref,...values});
}
packet.attestations.RuntimeProbe=attestation("RuntimeProbe",{
 status:"HEALTHY",runtime_ref:plan.runtime_ref,checks:[...releaseAssuranceRequirements.checks]});
packet.attestations.RollbackOperator=attestation("RollbackOperator",{
 status:"DRILL_PASSED",rollback_artifact_sha256:plan.rollback_artifact_sha256,rollback_owner_ref:plan.rollback_owner_ref});
packet.attestations.Monitor=attestation("Monitor",{
 status:"ACTIVE",runtime_ref:plan.runtime_ref,alert_route_tested:true,error_budget_guard_enabled:true});
for(const issuer of reviewers)packet.approvals[issuer]=signEnvelope(issuer,{...scope,decision:"APPROVE_FOR_REVIEW",policy_ref:"lab:policy:v1"});
// Trusted R0.8 dependency is substituted ONLY inside this test process.
// Actual deployment must inject the real independently verified R0.8 gate.
const providerGate={async assess(p){return p===providerPacket?{
 status:"REVIEW_READY",manifest_digest:admissionDigest(p),operations_enabled:false,
 public_qr_enabled:false,deployment_activated:false}:{status:"BLOCKED"};}};
const seen=[];
const config={providerGate,trustRoots,expectedEnvironment:"staging",expectedReleaseSha:release_sha,now,
 verifyEvidence:async(ref,ctx)=>{
  assert.equal(ctx.tenant_ref,binding.tenant_ref);
  assert.equal(ctx.release_sha,release_sha);
  assert.equal(ctx.deployment_ref,plan.deployment_ref);
  seen.push(ref);return evidenceRefs.has(ref);
 }};
const result=await createReleaseAssuranceGate(config).assess(packet);
assert.equal(result.status,"RELEASE_REVIEW_READY",JSON.stringify(result.reasons));
assert.equal(result.plan_digest,digest);
assert.equal(result.provider_status,"REVIEW_READY");
assert.equal(result.live_health_observed_by_this_gate,false);
assert.equal(seen.length,5);
for(const x of ["operations_enabled","public_qr_enabled","deployment_activated","booking_confirmed"])
 assert.equal(result[x],false);
assert.equal(result.monetary_values,"DEPICTION_ONLY");
const copy=()=>structuredClone(packet);
async function blocked(p,code,overrides={}){
 const r=await createReleaseAssuranceGate({...config,...overrides}).assess(p);
 assert.equal(r.status,"BLOCKED");
 assert.ok(r.reasons.some(x=>x.code===code),JSON.stringify(r.reasons));
 assert.equal(r.deployment_activated,false);
 assert.equal(r.public_qr_enabled,false);
}
const pilot=copy();pilot.asset_ref="A-1204";
await blocked(pilot,"PILOT_ASSET_HARD_DENY");
const badRelease=copy();badRelease.release_sha="0".repeat(40);
await blocked(badRelease,"EXPECTED_RELEASE_MISMATCH");
const badEnvironment=copy();badEnvironment.environment="production";
await blocked(badEnvironment,"EXPECTED_RELEASE_MISMATCH");
const expired=copy();expired.expires_at=seconds-1;
await blocked(expired,"RELEASE_PACKET_INVALID");
const missingProvider=copy();delete missingProvider.provider_packet;
await blocked(missingProvider,"PROVIDER_RELEASE_MISMATCH");
await blocked(packet,"PROVIDER_REVIEW_NOT_READY",{providerGate:{async assess(){return {status:"REVIEW_READY",manifest_digest:"0".repeat(64)};}}});
await blocked(packet,"PROVIDER_REVIEW_NOT_READY",{providerGate:{async assess(){throw Error("offline");}}});
const wrongRollback=copy();wrongRollback.plan.rollback_artifact_sha256=wrongRollback.plan.artifact_sha256;
await blocked(wrongRollback,"RELEASE_PLAN_INVALID");
const noCanary=copy();noCanary.plan.initial_percent=100;
await blocked(noCanary,"RELEASE_PLAN_INVALID");
const noBNR=copy();delete noBNR.approvals.BNR;
await blocked(noBNR,"RELEASE_REVIEW_NOT_ATTESTED");
const wrongDecision=copy();wrongDecision.approvals.ReleaseOwner.payload.decision="APPROVE_DEPLOY";
await blocked(wrongDecision,"RELEASE_REVIEW_NOT_ATTESTED");
const altered=copy();altered.attestations.RuntimeProbe.payload.status="HEALTHY_FAKE";
await blocked(altered,"RUNTIME_ATTESTATION_INVALID");
const sick=copy();sick.attestations.RuntimeProbe=signEnvelope("RuntimeProbe",{
 ...scope,observed_at:seconds-10,evidence_ref:"river://lab/assurance/runtimeprobe",
 status:"DEGRADED",runtime_ref:plan.runtime_ref,checks:[...releaseAssuranceRequirements.checks]});
await blocked(sick,"RUNTIME_HEALTH_NOT_ATTESTED");
const noAlarm=copy();noAlarm.attestations.Monitor=signEnvelope("Monitor",{
 ...scope,observed_at:seconds-10,evidence_ref:"river://lab/assurance/monitor",
 status:"ACTIVE",runtime_ref:plan.runtime_ref,alert_route_tested:false,error_budget_guard_enabled:true});
await blocked(noAlarm,"MONITORING_NOT_ATTESTED");
const noRollback=copy();noRollback.attestations.RollbackOperator=signEnvelope("RollbackOperator",{
 ...scope,observed_at:seconds-10,evidence_ref:"river://lab/assurance/rollbackoperator",
 status:"DRILL_FAILED",rollback_artifact_sha256:plan.rollback_artifact_sha256,rollback_owner_ref:plan.rollback_owner_ref});
await blocked(noRollback,"ROLLBACK_NOT_ATTESTED");
const oldMonitor=copy();oldMonitor.attestations.Monitor=signEnvelope("Monitor",{
 ...scope,observed_at:seconds-1000,evidence_ref:"river://lab/assurance/monitor",
 status:"ACTIVE",runtime_ref:plan.runtime_ref,alert_route_tested:true,error_budget_guard_enabled:true});
await blocked(oldMonitor,"RUNTIME_ATTESTATION_INVALID");
await blocked(packet,"RELEASE_EVIDENCE_VERIFIER_MISSING",{verifyEvidence:undefined});
await blocked(packet,"RELEASE_EVIDENCE_UNVERIFIED",{verifyEvidence:async()=>false});
await blocked(packet,"RELEASE_EVIDENCE_UNVERIFIED",{verifyEvidence:async()=>{throw Error("offline");}});
await blocked(null,"RELEASE_PACKET_MISSING");
console.log("PASS: R0.9 signed release review, 19 deny cases, A-1204 hard deny, no automatic activation.");
