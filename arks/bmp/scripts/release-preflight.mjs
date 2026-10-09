import {readFileSync} from "node:fs";
import {createReleaseAssuranceGate} from "../service/release-assurance.mjs";
const packet=JSON.parse(readFileSync(new URL("../configs/release-assurance.sample.json",import.meta.url),"utf8"));
const providerGate={async assess(){return {status:"BLOCKED"};}};
const report=await createReleaseAssuranceGate({providerGate}).assess(packet);
console.log(JSON.stringify({tool:"bmp-release-preflight",mode:"READ_ONLY_OFFLINE",status:report.status,
 reasons:report.reasons,operations_enabled:false,public_qr_enabled:false,
 deployment_activated:false,monetary_values:"DEPICTION_ONLY"},null,2));
if(process.argv.includes("--require-ready")&&report.status!=="RELEASE_REVIEW_READY")process.exitCode=2;
