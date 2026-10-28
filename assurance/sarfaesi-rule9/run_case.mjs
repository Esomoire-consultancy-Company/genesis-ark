import fs from 'node:fs';
import {reviewAuction} from './rule9_guard.mjs';
const file = process.argv[2];
if (!file) { console.error('Usage: node run_case.mjs <case.json>'); process.exitCode = 2; }
else {
  try {
    const {caseRef, sourceClassification, ...input} = JSON.parse(fs.readFileSync(file, 'utf8'));
    console.log(JSON.stringify({caseRef, sourceClassification, review:reviewAuction(input)}, null, 2));
  } catch(e) { console.error(e.message); process.exitCode = 1; }
}
