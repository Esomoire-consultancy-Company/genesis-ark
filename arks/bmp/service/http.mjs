import http from "node:http";
import {DoorError} from "./resolver.mjs";
const MAX_BODY=4096;
const json=(res,status,body)=>{
  const bytes=Buffer.from(JSON.stringify(body)+"\n");
  res.writeHead(status,{"content-type":"application/json; charset=utf-8",
    "cache-control":"no-store","x-content-type-options":"nosniff",
    "content-security-policy":"default-src 'none'","content-length":bytes.length});
  res.end(bytes);
};
function readBody(req){
 return new Promise((resolve,reject)=>{
  let size=0,parts=[],done=false;
  req.on("data",chunk=>{
    if(done)return;
    size+=chunk.length;
    if(size>MAX_BODY){done=true;reject(new DoorError("REQUEST_TOO_LARGE",413));req.resume();return;}
    parts.push(chunk);
  });
  req.on("end",()=>{
    if(done)return;
    try{resolve(JSON.parse(Buffer.concat(parts).toString("utf8")));}
    catch{reject(new DoorError("INVALID_JSON",400));}
  });
  req.on("error",()=>{if(!done)reject(new DoorError("REQUEST_INTERRUPTED",400));});
 });
}
export function createDoorHttpServer({resolver=null}={}){
 return http.createServer(async(req,res)=>{
   try{
     const pathname=new URL(req.url,"http://localhost").pathname;
     if(pathname==="/healthz"&&req.method==="GET")
       return json(res,resolver?200:503,{service:"bmp-door-resolver",mode:"R0.6",adapters_configured:Boolean(resolver)});
     if(pathname!=="/v1/door/resolve")return json(res,404,{error:"NOT_FOUND"});
     if(req.method!=="POST")return json(res,405,{error:"METHOD_NOT_ALLOWED"});
     if(!req.headers["content-type"]?.toLowerCase().startsWith("application/json"))
       return json(res,415,{error:"JSON_REQUIRED"});
     if(!resolver)return json(res,503,{error:"INTEGRATION_UNAVAILABLE"});
     const body=await readBody(req);
     const result=await resolver(body,{authorization:req.headers.authorization});
     return json(res,200,result);
   }catch(err){
     const status=err instanceof DoorError?err.status:503;
     const code=err instanceof DoorError?err.code:"INTEGRATION_UNAVAILABLE";
     return json(res,status,{error:code});
   }
 });
}
// Standalone server is non-admitting and loopback-only. Real adapters are injected in a governed host.
if(process.argv[1]&&import.meta.url===new URL("file://"+process.argv[1]).href){
 const port=Number(process.env.BMP_DOOR_PORT||8786);
 if(!Number.isInteger(port)||port<1024||port>65535)throw new Error("Unsafe port");
 createDoorHttpServer().listen(port,"127.0.0.1",()=>{process.stdout.write("R0.6 loopback service listening: adapters unavailable; all admissions denied.\n");});
}
