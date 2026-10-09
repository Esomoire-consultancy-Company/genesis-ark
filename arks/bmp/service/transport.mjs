import {isIP} from "node:net";
import {DoorError} from "./resolver.mjs";

const serviceNames = Object.freeze(["Genesis","DigitalMe","Warden","River","Quantum"]);
const responseLimit=65536;
const requestLimit=16384;
const safeRef=/^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$/;
function endpoint(value,name){
 if(typeof value!=="string")throw new DoorError("FEDERATION_NOT_CONFIGURED",503);
 let u;
 try{u=new URL(value);}catch{throw new DoorError("FEDERATION_NOT_CONFIGURED",503);}
 if(u.protocol!=="https:"||u.username||u.password||u.search||u.hash||u.pathname!=="/"||
    !u.hostname.includes(".")||isIP(u.hostname)||u.hostname==="localhost"||u.port)
   throw new DoorError("FEDERATION_ENDPOINT_REJECTED",503);
 return u.origin;
}
async function readSmallJson(response){
 if(!response||response.status!==200||response.redirected===true)
   throw new DoorError("FEDERATION_UNAVAILABLE",503);
 const contentType=response.headers?.get("content-type")??"";
 if(!/^application\/json(?:;|$)/i.test(contentType))
   throw new DoorError("FEDERATION_BAD_RESPONSE",503);
 if(!response.body?.getReader)throw new DoorError("FEDERATION_BAD_RESPONSE",503);
 const reader=response.body.getReader();
 let count=0,parts=[];
 try{
  while(true){
   const part=await reader.read();
   if(part.done)break;
   count+=part.value.byteLength;
   if(count>responseLimit)throw new DoorError("FEDERATION_BAD_RESPONSE",503);
   parts.push(part.value);
  }
 }catch(err){
  try{await reader.cancel();}catch{}
  if(err instanceof DoorError)throw err;
  throw new DoorError("FEDERATION_UNAVAILABLE",503);
 }
 try{
  const text=Buffer.concat(parts.map(x=>Buffer.from(x))).toString("utf8");
  if(!text)throw Error("empty");
  const data=JSON.parse(text);
  if(!data||typeof data!=="object"||Array.isArray(data))throw Error("not object");
  return data;
 }catch{throw new DoorError("FEDERATION_BAD_RESPONSE",503);}
}
export function createFederationTransport({origins,getServiceToken,fetchImpl=globalThis.fetch,timeoutMs=2500}={}){
 if(!origins||typeof getServiceToken!=="function"||typeof fetchImpl!=="function"||
    !Number.isInteger(timeoutMs)||timeoutMs<100||timeoutMs>10000)
    throw new DoorError("FEDERATION_NOT_CONFIGURED",503);
 const hosts=Object.freeze(Object.fromEntries(serviceNames.map(name=>[name,endpoint(origins[name],name)])));
 async function invoke(name,path,payload=null){
  if(!serviceNames.includes(name)||typeof path!=="string"||!path.startsWith("/v1/")||path.includes("?")||path.includes("#"))
    throw new DoorError("FEDERATION_REQUEST_REJECTED",503);
  const token=await getServiceToken(name);
  if(typeof token!=="string"||!/^Bearer [A-Za-z0-9._~-]{8,4096}$/.test(token))
    throw new DoorError("FEDERATION_NOT_CONFIGURED",503);
  if(payload!==null&&Buffer.byteLength(JSON.stringify(payload),"utf8")>requestLimit)
    throw new DoorError("FEDERATION_REQUEST_REJECTED",413);
  let reply;
  try{
   reply=await fetchImpl(hosts[name]+path,{
    method:payload===null?"GET":"POST",
    redirect:"manual",signal:AbortSignal.timeout(timeoutMs),
    headers:{"accept":"application/json",
      "authorization":token,
      ...(payload===null?{}:{"content-type":"application/json"})},
    ...(payload===null?{}:{body:JSON.stringify(payload)})
   });
  }catch{throw new DoorError("FEDERATION_UNAVAILABLE",503);}
  return readSmallJson(reply);
 }
 return Object.freeze({invoke,configuredServices:Object.freeze([...serviceNames])});
}
export function validateAssetId(ref){
 if(typeof ref!=="string"||!safeRef.test(ref))throw new DoorError("INVALID_ASSET_REFERENCE",400);
 return ref;
}
