import {readFileSync} from "node:fs";
import {createProviderAdmissionGate} from "../service/provider-admission.mjs";
const draft=JSON.parse(readFileSync(new URL("../configs/provider-admission.sample.json",import.meta.url),"utf8"));
const gate=createProviderAdmissionGate({});
const report=await gate.assess(draft);
console.log(JSON.stringify({tool:"bmp-provider-preflight",mode:"READ_ONLY",status:report.status,blockers:report.reasons,operations_enabled:false,public_qr_enabled:false,deployment_activated:false},null,2));
if(process.argv.includes("--require-ready")&&report.status!=="REVIEW_READY")process.exitCode=2;
