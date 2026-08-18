import { REPLICA_HEADERS, type EventRow } from "./domain";
import { nowIso } from "./util";

interface OutboxRow { outbox_id:number; event_id:string; attempt_count:number; }
interface GoogleToken { access_token?:string; expires_in?:number; error?:string; }

async function googleAccessToken(env:Env):Promise<string>{
  const body=new URLSearchParams({client_id:env.GOOGLE_OAUTH_CLIENT_ID,client_secret:env.GOOGLE_OAUTH_CLIENT_SECRET,refresh_token:env.GOOGLE_OAUTH_REFRESH_TOKEN,grant_type:"refresh_token"});
  const r=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body});
  const j=await r.json<GoogleToken>();if(!r.ok||!j.access_token)throw new Error(`GOOGLE_OAUTH:${j.error??r.status}`);return j.access_token;
}

function authHeaders(token:string,extra:HeadersInit={}):HeadersInit{return{authorization:`Bearer ${token}`,...extra};}
function a1(name:string,range:string):string{return `'${name.replace(/'/g,"''")}'!${range}`;}

async function ensureReplicaSheet(env:Env,token:string):Promise<void>{
  const id=env.GOOGLE_STAGING_SHEET_ID;
  const meta=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}?fields=sheets.properties(sheetId,title,hidden)`,{headers:authHeaders(token)});
  if(!meta.ok)throw new Error(`GOOGLE_META:${meta.status}`);
  const m=await meta.json<{sheets?:Array<{properties?:{sheetId?:number;title?:string;hidden?:boolean}}>}>();
  let p=m.sheets?.map(x=>x.properties).find(x=>x?.title==="__M1_SERVICE_REPLICA");
  if(!p){
    const create=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}:batchUpdate`,{method:"POST",headers:authHeaders(token,{"content-type":"application/json"}),body:JSON.stringify({requests:[{addSheet:{properties:{title:"__M1_SERVICE_REPLICA",hidden:true}}}]})});
    if(!create.ok)throw new Error(`GOOGLE_CREATE_REPLICA:${create.status}`);
  }else if(!p.hidden&&p.sheetId!==undefined){
    const hide=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}:batchUpdate`,{method:"POST",headers:authHeaders(token,{"content-type":"application/json"}),body:JSON.stringify({requests:[{updateSheetProperties:{properties:{sheetId:p.sheetId,hidden:true},fields:"hidden"}}]})});
    if(!hide.ok)throw new Error(`GOOGLE_HIDE_REPLICA:${hide.status}`);
  }
  const headerUrl=`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}/values/${encodeURIComponent(a1("__M1_SERVICE_REPLICA","A1:T1"))}?valueInputOption=RAW`;
  const put=await fetch(headerUrl,{method:"PUT",headers:authHeaders(token,{"content-type":"application/json"}),body:JSON.stringify({range:a1("__M1_SERVICE_REPLICA","A1:T1"),majorDimension:"ROWS",values:[[...REPLICA_HEADERS]]})});
  if(!put.ok)throw new Error(`GOOGLE_HEADER:${put.status}`);
}

function eventValues(e:EventRow):unknown[]{return[e.event_id,e.event_type,e.entity_type,e.entity_id,e.business_date,e.authority_epoch,e.authority_seq,e.service_generation,e.base_version,e.new_version,e.actor_id,e.actor_role,e.device_id,e.occurred_at,e.committed_at,e.idempotency_key,e.origin,e.schema_version,e.checksum,e.payload_json];}

async function existingEventIds(env:Env,token:string):Promise<Set<string>>{
  const url=`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(env.GOOGLE_STAGING_SHEET_ID)}/values/${encodeURIComponent(a1("__M1_SERVICE_REPLICA","A2:A"))}?majorDimension=COLUMNS`;
  const r=await fetch(url,{headers:authHeaders(token)});if(!r.ok)throw new Error(`GOOGLE_REPLICA_IDS:${r.status}`);
  const j=await r.json<{values?:unknown[][]}>();return new Set((j.values?.[0]??[]).map(String));
}

async function appendRows(env:Env,token:string,events:EventRow[]):Promise<string>{
  if(!events.length)return"NOOP";
  const range=a1("__M1_SERVICE_REPLICA","A:T");
  const url=`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(env.GOOGLE_STAGING_SHEET_ID)}/values/${encodeURIComponent(range)}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`;
  const r=await fetch(url,{method:"POST",headers:authHeaders(token,{"content-type":"application/json"}),body:JSON.stringify({range,majorDimension:"ROWS",values:events.map(eventValues)})});
  if(!r.ok){const txt=await r.text();throw new Error(`GOOGLE_APPEND:${r.status}:${txt.slice(0,240)}`);}
  const j=await r.json<{updates?:{updatedRange?:string}}>();return j.updates?.updatedRange??"APPENDED";
}

function retryDelaySeconds(attempt:number):number{return Math.min(900,Math.max(5,Math.pow(2,Math.min(8,attempt))*5));}

export async function replicatePending(db:D1Database,env:Env,limit=50):Promise<{ok:boolean;processed:number;appended:number;pending:number;checkpoint?:string;error?:string}>{
  const rows=await db.prepare("SELECT outbox_id,event_id,attempt_count FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY') AND next_attempt_at<=?1 ORDER BY outbox_id LIMIT ?2").bind(nowIso(),Math.max(1,Math.min(limit,100))).all<OutboxRow>();
  const due=rows.results??[];
  if(!due.length){const p=await db.prepare("SELECT COUNT(*) n FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')").first<{n:number}>();return{ok:true,processed:0,appended:0,pending:p?.n??0};}
  const ids=due.map(x=>x.event_id),marks=ids.map(()=>"?").join(",");
  try{
    const claim=crypto.randomUUID(),at=nowIso();
    await db.batch(due.map(x=>db.prepare("UPDATE sheet_replication_outbox SET status='INFLIGHT',claim_token=?1,claimed_at=?2,attempt_count=attempt_count+1,last_error_class=NULL,last_error=NULL WHERE outbox_id=?3 AND status IN ('PENDING','RETRY')").bind(claim,at,x.outbox_id)));
    const token=await googleAccessToken(env);await ensureReplicaSheet(env,token);const present=await existingEventIds(env,token);
    const eventsResult=await db.prepare(`SELECT * FROM events WHERE event_id IN (${marks}) ORDER BY authority_epoch,authority_seq`).bind(...ids).all<EventRow>();
    const events=(eventsResult.results??[]).filter(e=>!present.has(e.event_id));const checkpoint=await appendRows(env,token,events);const doneAt=nowIso();
    await db.batch(due.map(x=>db.prepare("UPDATE sheet_replication_outbox SET status='SYNCED',claim_token=NULL,claimed_at=NULL,replicated_at=?1,google_checkpoint=?2,last_error_class=NULL,last_error=NULL WHERE outbox_id=?3").bind(doneAt,checkpoint,x.outbox_id)));
    const pending=await db.prepare("SELECT COUNT(*) n FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')").first<{n:number}>();
    await db.prepare("UPDATE replication_status SET target_identity=?1,state='HEALTHY',checkpoint=?2,pending_count=?3,last_attempt_at=?4,last_success_at=?4,last_error_class=NULL,last_error=NULL,updated_at=?4 WHERE singleton_id=1").bind(env.GOOGLE_STAGING_SHEET_ID,checkpoint,pending?.n??0,doneAt).run();
    return{ok:true,processed:due.length,appended:events.length,pending:pending?.n??0,checkpoint};
  }catch(e){
    const msg=String(e).slice(0,700),at=nowIso();
    await db.batch(due.map(x=>{const sec=retryDelaySeconds(x.attempt_count+1),next=new Date(Date.now()+sec*1000).toISOString();return db.prepare("UPDATE sheet_replication_outbox SET status='RETRY',claim_token=NULL,claimed_at=NULL,next_attempt_at=?1,last_error_class='TRANSIENT',last_error=?2 WHERE outbox_id=?3").bind(next,msg,x.outbox_id);}));
    const pending=await db.prepare("SELECT COUNT(*) n FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')").first<{n:number}>();
    await db.prepare("UPDATE replication_status SET state='DEGRADED',pending_count=?1,retry_count=retry_count+1,last_attempt_at=?2,last_error_class='TRANSIENT',last_error=?3,updated_at=?2 WHERE singleton_id=1").bind(pending?.n??0,at,msg).run();
    return{ok:false,processed:due.length,appended:0,pending:pending?.n??0,error:msg};
  }
}

export async function replicationHealth(db:D1Database):Promise<Record<string,unknown>>{
  const row=await db.prepare("SELECT target_kind,target_identity,schema_version,state,checkpoint,pending_count,retry_count,last_attempt_at,last_success_at,last_error_class,last_error,updated_at FROM replication_status WHERE singleton_id=1").first<Record<string,unknown>>();
  const actual=await db.prepare("SELECT COUNT(*) n FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')").first<{n:number}>();
  return{...(row??{}),pending_count:actual?.n??0};
}
