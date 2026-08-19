import { authenticate } from "./auth";
import { currentAuthority } from "./core";
import { apiError, json, nowIso, readJsonBody } from "./util";

type PushEnv=Env&{FCM_PROJECT_ID?:string;FCM_CLIENT_EMAIL?:string;FCM_PRIVATE_KEY?:string};
interface TokenCache{token:string;expires:number}
let tokenCache:TokenCache|null=null;

function b64u(input:string|ArrayBuffer):string{const bytes=typeof input==="string"?new TextEncoder().encode(input):new Uint8Array(input);let s="";for(const b of bytes)s+=String.fromCharCode(b);return btoa(s).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/g,"");}
function pemBytes(pem:string):ArrayBuffer{const raw=pem.replace(/\\n/g,"\n").replace(/-----[^-]+-----/g,"").replace(/\s/g,"");const bin=atob(raw),out=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)out[i]=bin.charCodeAt(i);return out.buffer;}
async function fcmAccessToken(env:PushEnv):Promise<string|null>{
  if(!env.FCM_PROJECT_ID||!env.FCM_CLIENT_EMAIL||!env.FCM_PRIVATE_KEY)return null;
  if(tokenCache&&tokenCache.expires>Date.now()+60_000)return tokenCache.token;
  const now=Math.floor(Date.now()/1000),header=b64u(JSON.stringify({alg:"RS256",typ:"JWT"})),claims=b64u(JSON.stringify({iss:env.FCM_CLIENT_EMAIL,scope:"https://www.googleapis.com/auth/firebase.messaging",aud:"https://oauth2.googleapis.com/token",iat:now,exp:now+3600})),unsigned=`${header}.${claims}`;
  const key=await crypto.subtle.importKey("pkcs8",pemBytes(env.FCM_PRIVATE_KEY),{name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["sign"]),sig=await crypto.subtle.sign("RSASSA-PKCS1-v1_5",key,new TextEncoder().encode(unsigned)),assertion=`${unsigned}.${b64u(sig)}`;
  const r=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body:new URLSearchParams({grant_type:"urn:ietf:params:grant-type:jwt-bearer",assertion})});
  if(!r.ok)throw new Error(`FCM_OAUTH_${r.status}`);const j=await r.json<{access_token?:string;expires_in?:number}>();if(!j.access_token)throw new Error("FCM_OAUTH_TOKEN_MISSING");tokenCache={token:j.access_token,expires:Date.now()+Math.max(300,Number(j.expires_in||3600))*1000};return j.access_token;
}

export async function registerPushDevice(request:Request,env:Env):Promise<Response>{
  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);
  const b=await readJsonBody<{fcm_token:string;app_version?:string;channel?:string}>(request),token=String(b.fcm_token||"").trim();if(token.length<32||token.length>4096)return apiError("FCM_TOKEN_INVALID","VALIDATION",400);
  const at=nowIso();await env.DB.prepare(`INSERT INTO push_devices(device_id,login_id,fcm_token,platform,app_version,channel,status,registered_at,updated_at)
    VALUES(?1,?2,?3,'ANDROID',?4,?5,'ACTIVE',?6,?6) ON CONFLICT(device_id,login_id) DO UPDATE SET fcm_token=excluded.fcm_token,app_version=excluded.app_version,channel=excluded.channel,status='ACTIVE',updated_at=excluded.updated_at,last_error_class=NULL`).bind(auth.device_id,auth.login_id,token,String(b.app_version||"").slice(0,80),String(b.channel||"").slice(0,40),at).run();
  return json({ok:true,device_id:auth.device_id,push:"FCM_WAKE_ONLY"});
}
export async function revokePushDevice(request:Request,env:Env):Promise<Response>{const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);await env.DB.prepare("UPDATE push_devices SET status='REVOKED',updated_at=?1 WHERE device_id=?2 AND login_id=?3").bind(nowIso(),auth.device_id,auth.login_id).run();return json({ok:true});}

export async function enqueueInvalidation(db:D1Database,namespace:string,revision:number|undefined,businessDate?:string):Promise<void>{const a=await currentAuthority(db),at=nowIso(),payload={type:businessDate?"DAY_CHANGED":"MASTER_CHANGED",namespace,revision:revision??null,business_date:businessDate??null,authority_epoch:a.authority_epoch,authority_seq:a.authority_seq};await db.prepare("INSERT INTO push_outbox(push_id,namespace,revision,business_date,authority_epoch,authority_seq,payload_json,status,next_attempt_at,created_at) VALUES(?1,?2,?3,?4,?5,?6,?7,'PENDING',?8,?8)").bind(crypto.randomUUID(),namespace,revision??null,businessDate??null,a.authority_epoch,a.authority_seq,JSON.stringify(payload),at).run();}

/**
 * Canonical business mutations already append durable events transactionally. Stage a deterministic
 * FCM invalidation from that event log so DAY_CHANGED cannot be lost if the request path returns
 * before a separate push enqueue. The one-minute scheduled flush makes this a wake signal only;
 * Android always pulls authoritative state after receiving it.
 */
async function stageRecentDayInvalidations(db:D1Database):Promise<void>{
  const cutoff=new Date(Date.now()-10*60_000).toISOString();
  await db.prepare(`INSERT OR IGNORE INTO push_outbox(push_id,namespace,revision,business_date,authority_epoch,authority_seq,payload_json,status,next_attempt_at,created_at)
    SELECT 'day:'||event_id,'business_day',authority_seq,business_date,authority_epoch,authority_seq,
      json_object('type','DAY_CHANGED','namespace','business_day','revision',authority_seq,'business_date',business_date,'authority_epoch',authority_epoch,'authority_seq',authority_seq),
      'PENDING',committed_at,committed_at
    FROM events
    WHERE business_date<>'MASTER' AND committed_at>=?1`).bind(cutoff).run();
}

export async function flushPushOutbox(db:D1Database,rawEnv:Env,limit=50):Promise<{configured:boolean;sent:number;invalid:number;retry:number;pending:number}>{
  await stageRecentDayInvalidations(db);
  const env=rawEnv as PushEnv,access=await fcmAccessToken(env);if(!access)return{configured:false,sent:0,invalid:0,retry:0,pending:(await db.prepare("SELECT COUNT(*) n FROM push_outbox WHERE status IN ('PENDING','RETRY')").first<{n:number}>())?.n??0};
  const pushes=(await db.prepare("SELECT push_id,payload_json,attempt_count FROM push_outbox WHERE status IN ('PENDING','RETRY') AND next_attempt_at<=?1 ORDER BY created_at LIMIT ?2").bind(nowIso(),Math.max(1,Math.min(100,limit))).all<{push_id:string;payload_json:string;attempt_count:number}>()).results??[],devices=(await db.prepare("SELECT device_id,login_id,fcm_token FROM push_devices WHERE status='ACTIVE'").all<{device_id:string;login_id:string;fcm_token:string}>()).results??[];let sent=0,invalid=0,retry=0;
  for(const p of pushes){let transient=false;for(const d of devices){const data=JSON.parse(p.payload_json) as Record<string,unknown>,stringData=Object.fromEntries(Object.entries(data).map(([k,v])=>[k,v==null?"":String(v)]));const r=await fetch(`https://fcm.googleapis.com/v1/projects/${encodeURIComponent(env.FCM_PROJECT_ID!)}/messages:send`,{method:"POST",headers:{authorization:`Bearer ${access}`,"content-type":"application/json"},body:JSON.stringify({message:{token:d.fcm_token,data:stringData,android:{priority:"high"}}})});if(r.ok){sent++;await db.prepare("UPDATE push_devices SET last_success_at=?1,last_error_class=NULL WHERE fcm_token=?2").bind(nowIso(),d.fcm_token).run();continue;}const text=(await r.text()).slice(0,800);if(r.status===404||/UNREGISTERED|registration-token-not-registered/i.test(text)){invalid++;await db.prepare("UPDATE push_devices SET status='INVALID',last_error_class='UNREGISTERED',updated_at=?1 WHERE fcm_token=?2").bind(nowIso(),d.fcm_token).run();}else if(r.status===429||r.status>=500){transient=true;retry++;}else await db.prepare("UPDATE push_devices SET last_error_class=?1,updated_at=?2 WHERE fcm_token=?3").bind(`FCM_HTTP_${r.status}`,nowIso(),d.fcm_token).run();}
    const attempts=p.attempt_count+1,next=new Date(Date.now()+Math.min(3600_000,Math.pow(2,Math.min(attempts,8))*5000)).toISOString();await db.prepare("UPDATE push_outbox SET status=?1,attempt_count=?2,next_attempt_at=?3,last_error_class=?4 WHERE push_id=?5").bind(transient&&attempts<8?"RETRY":transient?"FAILED":"SENT",attempts,next,transient?"FCM_TRANSIENT":null,p.push_id).run();
  }
  const pending=(await db.prepare("SELECT COUNT(*) n FROM push_outbox WHERE status IN ('PENDING','RETRY')").first<{n:number}>())?.n??0;return{configured:true,sent,invalid,retry,pending};
}
