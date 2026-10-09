import {randomUUID} from "node:crypto";
import {DoorError,verifySigned,digest,createDoorResolver} from "./resolver.mjs";
import {createFederatedAdapters} from "./adapters.mjs";

const slotRe=/^20\d\d-(0[1-9]|1[0-2])-([012]\d|3[01])T([01]\d|2[0-3]):[0-5]\d:00Z$/;
export function createServiceFederation(config={}){
 const deps=createFederatedAdapters(config);
 const core=createDoorResolver(deps);
 // The private WeakMap is an internal capability token: client JSON cannot forge it.
 const issued=new WeakMap();
 async function resolve(request,context){
  const granted=await core(request,context);
  issued.set(granted,true);
  return granted;
 }
 async function requestQuantumSession(admission,{requested_slot}={}){
  if(!admission||!issued.has(admission)||admission.admission_status!=="ADMITTED")
   throw new DoorError("DOOR_ADMISSION_REQUIRED",403);
  if(!Number.isSafeInteger(admission.expires_at)||admission.expires_at<=Math.floor(deps.clock()/1000))
   throw new DoorError("DOOR_ADMISSION_EXPIRED",403);
  if(typeof requested_slot!=="string"||!slotRe.test(requested_slot)||
     !Number.isFinite(Date.parse(requested_slot))||
     Date.parse(requested_slot)<deps.clock()+60_000||
     Date.parse(requested_slot)>deps.clock()+30*86400_000)
   throw new DoorError("INVALID_SESSION_REQUEST",400);
  const ref="session:"+randomUUID();
  const request={
   action:"quantum.session.request",
   correlation_id:admission.correlation_id,
   room_ref:admission.room_ref,
   requested_slot,
   session_request_ref:ref,
   door_decision_ref:admission.policy_decision_ref
  };
  const w=await deps.warden.decide(request);
  const decision=verifySigned(w,{issuer:"Warden",key:deps.publicKeys.warden,now:deps.clock});
  if(decision.allowed!==true||decision.action!==request.action||
     decision.correlation_id!==request.correlation_id||
     decision.room_ref!==request.room_ref||decision.requested_slot!==requested_slot||
     decision.session_request_ref!==ref||
     decision.door_decision_ref!==admission.policy_decision_ref||
     typeof decision.decision_id!=="string"||
     !/^[A-Za-z0-9:_./-]{3,128}$/.test(decision.decision_id))
     throw new DoorError("WARDEN_SESSION_DENIED",403);
  const response=await deps.quantum.request({
   correlation_id:admission.correlation_id,room_ref:admission.room_ref,
   decision_id:decision.decision_id,requested_slot
  });
  const quantum=verifySigned(response,{issuer:"Quantum",key:deps.publicKeys.quantum,now:deps.clock});
  // R0.7 only permits request-accepted/pending responses. Confirmation is a separate lifecycle.
  if(quantum.status!=="PENDING"||quantum.correlation_id!==admission.correlation_id||
     quantum.room_ref!==admission.room_ref||quantum.decision_id!==decision.decision_id||
     quantum.requested_slot!==requested_slot||typeof quantum.session_ref!=="string"||
     !/^[A-Za-z0-9:_./-]{3,128}$/.test(quantum.session_ref))
     throw new DoorError("QUANTUM_RESPONSE_UNVERIFIED",503);
  const event={
   event_type:"QUANTUM_SESSION_REQUEST",
   correlation_id:admission.correlation_id,asset_ref:admission.asset_ref,
   room_ref:admission.room_ref,
   session_ref:quantum.session_ref,requested_slot,
   warden_decision_ref:decision.decision_id,
   state:"PENDING",
   recorded_at:new Date(deps.clock()).toISOString()
  };
  const proof=await deps.river.record({event,digest:digest(event)});
  const receipt=verifySigned(proof,{issuer:"River",key:deps.publicKeys.river,now:deps.clock});
  if(receipt.verified!==true||receipt.correlation_id!==admission.correlation_id||
     receipt.decision_id!==decision.decision_id||receipt.event_digest!==digest(event)||
     typeof receipt.receipt_id!=="string"||
     !/^[A-Za-z0-9:_./-]{3,128}$/.test(receipt.receipt_id))
     throw new DoorError("EVIDENCE_UNAVAILABLE",503);
  return Object.freeze({
   status:"PENDING",session_ref:quantum.session_ref,
   correlation_id:admission.correlation_id,requested_slot,
   decision_ref:decision.decision_id,evidence_receipt_ref:receipt.receipt_id,
   booking_confirmed:false,monetary_values:"DEPICTION_ONLY"
  });
 }
 return Object.freeze({resolver:resolve,requestQuantumSession,mode:"FEDERATION_CONTRACT_R0.7"});
}
