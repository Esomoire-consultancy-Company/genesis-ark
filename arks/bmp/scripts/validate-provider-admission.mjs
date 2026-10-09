import assert from "node:assert/strict";
import {generateKeyPairSync,sign} from "node:crypto";
import {readFileSync} from "node:fs";
import {createProviderAdmissionGate,admissionDigest,assuranceRequirements} from "../service/provider-admission.mjs";

const nowMs=Date.now(),nowSec=Math.floor(nowMs/1000);
const environment="staging",asset_ref="LAB-0001",tenant_ref="LAB:TENANT:01";
const release_sha="f87ace816d8a01e4b0c2154084d4b3e9d19d2f43";
const names=[...assuranceRequirements.providers];
const controls=[...assuranceRequirements.controls];
const issuers=[...names,"BNR"];
const keys=Object.fromEntries(issuers.map(name=>[name,generateKeyPairSync("ed25519")]));
const roots=Object.fromEntries(issuers.map(name=>[name,{kid:"lab-key-20261010",key:keys[name].publicKey}]));
const trustRoots={providers:Object.fromEntries(names.map(x=>[x,roots[x]])),reviewers:{Warden:roots.Warden,BNR:roots.BNR}};
const approvedOrigins=Object.fromEntries(names.map(x=>[x,"https://"+x.toLowerCase()+".example.test"]));
const binding={environment,release_sha,tenant_ref,asset_ref};
const makeEnvelope=(issuer,data,{iat=nowSec-5,exp=nowSec+300}={})=>{
  const payload={iss:issuer,kid:"lab-key-20261010",aud:"bmp-provider-admission",iat,exp,...data};
  return {payload,signature:sign(null,Buffer.from(JSON.stringify(payload)),keys[issuer].privateKey).toString("base64url")};
};
const evidenceRefs=new Set();
const packet={
 version:"bmp.provider-admission.v0.1",
 ...binding,submitted_at:nowSec-15,expires_at:nowSec+300,
 provider_attestations:names.map(name=>{
   const evidence_ref="river://lab/provider/"+name.toLowerCase();
   evidenceRefs.add(evidence_ref);
   return makeEnvelope(name,{...binding,name,operator_ref:"LAB:OPERATOR:"+name.toUpperCase(),origin:approvedOrigins[name],evidence_refs:[evidence_ref]});
 }),
 control_evidence:controls.map(control=>{
   const evidence_ref="river://lab/control/"+control;
   evidenceRefs.add(evidence_ref);
   return {control,evidence_ref};
 }),
 approvals:{}
};
const digest=admissionDigest(packet);
for(const name of ["Warden","BNR"]){
 packet.approvals[name]=makeEnvelope(name,{...binding,manifest_digest:digest,decision:"APPROVE_FOR_REVIEW",policy_ref:"lab:policy:v1"});
}
const verificationCalls=[];
const config={
 trustRoots,approvedOrigins,expectedEnvironment:environment,expectedReleaseSha:release_sha,
 now:()=>nowMs,
 verifyEvidence:async(ref,scope)=>{
   verificationCalls.push(ref);
   assert.equal(scope.tenant_ref,tenant_ref);
   assert.equal(scope.asset_ref,asset_ref);
   assert.equal(scope.release_sha,release_sha);
   return evidenceRefs.has(ref);
 }
};
const gate=createProviderAdmissionGate(config);
const assessed=await gate.assess(packet);
assert.equal(assessed.status,"REVIEW_READY",JSON.stringify(assessed.reasons));
assert.deepEqual(assessed.reasons,[]);
assert.equal(assessed.provider_count,5);
assert.equal(assessed.evidence_count,14);
assert.equal(assessed.manifest_digest,digest);
assert.equal(verificationCalls.length,14);
for(const control of ["operations_enabled","public_qr_enabled","deployment_activated"])
 assert.equal(assessed[control],false);
assert.equal(assessed.commercial_mode,"DEPICTION_ONLY");
const copy=()=>structuredClone(packet);
async function blocked(p,code,{options={}}={}){
 const result=await createProviderAdmissionGate({...config,...options}).assess(p);
 assert.equal(result.status,"BLOCKED");
 assert.ok(result.reasons.some(x=>x.code===code),JSON.stringify(result.reasons));
 for(const control of ["operations_enabled","public_qr_enabled","deployment_activated"])
  assert.equal(result[control],false);
 return result;
}
// Even perfectly signed provider attestations cannot grant access to the A-1204 pilot.
const pilot=copy();pilot.asset_ref="A-1204";
await blocked(pilot,"PILOT_ASSET_NOT_ADMISSIBLE");
const wrongTenant=copy();wrongTenant.tenant_ref="LAB:OTHER";
await blocked(wrongTenant,"PROVIDER_NOT_ADMITTED");
const wrongRelease=copy();wrongRelease.release_sha="0".repeat(40);
await blocked(wrongRelease,"RELEASE_BINDING_INVALID");
const wrongEnv=copy();wrongEnv.environment="production";
await blocked(wrongEnv,"RELEASE_BINDING_INVALID");
const stale=copy();stale.expires_at=nowSec-2;
await blocked(stale,"MANIFEST_INVALID");
const missing=copy();missing.provider_attestations.pop();
await blocked(missing,"PROVIDER_SET_INCOMPLETE");
const duplicate=copy();duplicate.provider_attestations[1]=duplicate.provider_attestations[0];
await blocked(duplicate,"PROVIDER_SET_INVALID");
const altered=copy();altered.provider_attestations[0].payload.origin="https://attacker.example.test";
await blocked(altered,"PROVIDER_NOT_ADMITTED");
const alteredKey=copy();alteredKey.provider_attestations[0].payload.kid="wrong-key";
await blocked(alteredKey,"PROVIDER_NOT_ADMITTED");
const untrustedDomain=copy();
untrustedDomain.provider_attestations[0]=makeEnvelope("Genesis",{...binding,name:"Genesis",operator_ref:"LAB:OPERATOR:GENESIS",origin:"https://192.168.1.1",evidence_refs:["river://lab/provider/genesis"]});
await blocked(untrustedDomain,"PROVIDER_NOT_ADMITTED");
const noControl=copy();noControl.control_evidence.pop();
await blocked(noControl,"ASSURANCE_CONTROLS_INCOMPLETE");
const badControl=copy();badControl.control_evidence[1]={control:"unknown",evidence_ref:"river://lab/control/fake"};
await blocked(badControl,"ASSURANCE_CONTROLS_INVALID");
const forgedReview=copy();forgedReview.approvals.BNR.payload.manifest_digest="0".repeat(64);
await blocked(forgedReview,"REVIEW_NOT_ATTESTED");
const revokedReview=copy();delete revokedReview.approvals.Warden;
await blocked(revokedReview,"REVIEW_NOT_ATTESTED");
const maliciousReview=copy();maliciousReview.approvals.Warden=makeEnvelope("Warden",{...binding,manifest_digest:digest,decision:"APPROVE_DEPLOY",policy_ref:"lab:policy:v1"});
await blocked(maliciousReview,"REVIEW_NOT_ATTESTED");
const tamperedControls=copy();tamperedControls.control_evidence[0].evidence_ref="river://lab/control/forged";
await blocked(tamperedControls,"REVIEW_NOT_ATTESTED");
const disconnected=await blocked(copy(),"EVIDENCE_VERIFIER_UNAVAILABLE",{options:{verifyEvidence:undefined}});
const badReceipt=await blocked(copy(),"EVIDENCE_NOT_VERIFIED",{options:{verifyEvidence:async()=>false}});
await blocked(copy(),"EVIDENCE_NOT_VERIFIED",{options:{verifyEvidence:async()=>{throw Error("offline");}}});
const sample=JSON.parse(readFileSync(new URL("../configs/provider-admission.sample.json",import.meta.url),"utf8"));
await blocked(sample,"PILOT_ASSET_NOT_ADMISSIBLE",{options:{verifyEvidence:undefined}});
const absent=await gate.assess(null);
assert.equal(absent.status,"BLOCKED");
assert.equal(absent.operations_enabled,false);
console.log("PASS: R0.8 signed provider/reviewer checks, evidence callback, nine controls, 20 denial variants, A-1204 hard-deny and zero automatic activation.");
