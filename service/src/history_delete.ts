import { authenticate } from "./auth";
import { currentAuthority } from "./core";
import type { EventRow } from "./domain";
import { enqueueInvalidation } from "./push";
import { apiError, json, nowIso, readJsonBody, sha256Hex } from "./util";

type DeleteBody={event_ids?:string[];idempotency_key?:string;reason?:string};
type Target={event_id:string;event_type:string;business_date:string;entity_type:string;entity_id:string};
const INSERT_EVENT=`INSERT INTO events(event_id,event_type,entity_type,entity_id,business_date,authority_epoch,authority_seq,service_generation,base_version,new_version,actor_id,actor_role,device_id,occurred_at,committed_at,payload_json,idempotency_key,origin,schema_version,checksum) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20)`;

export async function historyDelete(request:Request,env:Env):Promise<Response>{
  const auth=await authenticate(env.DB,env,request);
  if(!auth)return apiError("UNAUTHORIZED","AUTH",401);
  if(auth.role!=="SUPERADMIN")return apiError("SUPERADMIN_REQUIRED","PERMISSION",403);
  const body=await readJsonBody<DeleteBody>(request);
  const ids=[...new Set((body.event_ids??[]).map(v=>String(v||"").trim()).filter(Boolean))];
  const idem=String(body.idempotency_key||"").trim();
  const reason=String(body.reason||"").trim().slice(0,500);
  if(ids.length<1||ids.length>100||!idem)return apiError("HISTORY_DELETE_FIELDS_REQUIRED","VALIDATION",400);
  const authority=await currentAuthority(env.DB);
  if(authority.mode!=="SERVICE_PRIMARY")return apiError("SERVICE_NOT_WRITE_AUTHORITY","CONFLICT",409,true);

  const targets:Target[]=[];
  for(const id of ids){
    const row=await env.DB.prepare("SELECT event_id,event_type,business_date,entity_type,entity_id FROM events WHERE event_id=?1").bind(id).first<Target>();
    if(!row)return apiError("HISTORY_DELETE_TARGET_NOT_FOUND","VALIDATION",404,false,id);
    if(row.event_type==="HISTORY_DELETE")return apiError("HISTORY_DELETE_AUDIT_PROTECTED","PERMISSION",403,false,id);
    targets.push(row);
  }

  const byDate=new Map<string,Target[]>();
  for(const row of targets){const date=String(row.business_date||"").trim();if(!date)return apiError("HISTORY_DELETE_DATE_MISSING","INTEGRITY",409,false,row.event_id);const list=byDate.get(date)??[];list.push(row);byDate.set(date,list);}
  const dates=[...byDate.keys()].sort();
  const prior:EventRow[]=[];
  for(const date of dates){const key=`history-delete:${idem}:${date}`;const e=await env.DB.prepare("SELECT * FROM events WHERE idempotency_key=?1").bind(key).first<EventRow>();if(e)prior.push(e);}
  if(prior.length){if(prior.length===dates.length)return json({ok:true,duplicate:true,deleted_count:ids.length,target_event_ids:ids,tombstones:prior});return apiError("HISTORY_DELETE_PARTIAL_IDEMPOTENCY","INTEGRITY",409);}

  const committed=nowIso(),clientSource=auth.session_kind==="WEB"?"WEB":"PDA";
  const tombstones:EventRow[]=[];
  let seq=authority.authority_seq;
  for(const date of dates){
    const rows=byDate.get(date)??[];seq+=1;
    const summaries=rows.map(x=>({event_id:x.event_id,event_type:x.event_type,entity_type:x.entity_type,entity_id:x.entity_id}));
    const detail=`Đã xóa ${rows.length} mục: ${rows.map(x=>`${x.event_type} • ${x.entity_type}:${x.entity_id}`).join(", ")}`.slice(0,900);
    const payload={logical_delete:true,target_event_ids:rows.map(x=>x.event_id),target_summaries:summaries,deleted_count:rows.length,detail,reason,source:clientSource,actor_login_id:auth.login_id,actor_role:auth.role,original_events_immutable:true};
    const base={event_id:crypto.randomUUID(),event_type:"HISTORY_DELETE",entity_type:"HISTORY",entity_id:`history-delete:${date}:${crypto.randomUUID()}`,business_date:date,authority_epoch:authority.authority_epoch,authority_seq:seq,service_generation:authority.service_generation,base_version:0,new_version:1,actor_id:auth.login_id,actor_role:auth.role,device_id:auth.device_id,occurred_at:committed,committed_at:committed,payload_json:JSON.stringify(payload),idempotency_key:`history-delete:${idem}:${date}`,origin:clientSource==="WEB"?"WEB_HISTORY_DELETE":"PDA_HISTORY_DELETE",schema_version:1};
    tombstones.push({...base,checksum:await sha256Hex(JSON.stringify(base))});
  }

  const statements=[env.DB.prepare("UPDATE authority_state SET authority_seq=?1,updated_at=?2 WHERE singleton_id=1 AND authority_epoch=?3 AND authority_seq=?4").bind(seq,committed,authority.authority_epoch,authority.authority_seq)];
  for(const event of tombstones){
    statements.push(env.DB.prepare(INSERT_EVENT).bind(event.event_id,event.event_type,event.entity_type,event.entity_id,event.business_date,event.authority_epoch,event.authority_seq,event.service_generation,event.base_version,event.new_version,event.actor_id,event.actor_role,event.device_id,event.occurred_at,event.committed_at,event.payload_json,event.idempotency_key,event.origin,event.schema_version,event.checksum));
    statements.push(env.DB.prepare("INSERT INTO sheet_replication_outbox(event_id,status,next_attempt_at) VALUES(?1,'PENDING',?2)").bind(event.event_id,committed));
  }
  try{await env.DB.batch(statements);}catch(e){return apiError("HISTORY_DELETE_CONFLICT","TRANSIENT",409,true,String(e).slice(0,160));}

  for(const event of tombstones){
    await enqueueInvalidation(env.DB,"day",event.authority_seq,event.business_date);
    try{const hub=env.REALTIME_HUB.getByName(`business:${event.business_date}`) as unknown as {invalidate(message:Record<string,unknown>):Promise<number>};await hub.invalidate({type:"DAY_CHANGED",business_date:event.business_date,day_revision:event.authority_seq,authority_epoch:event.authority_epoch,authority_seq:event.authority_seq});}catch{}
  }
  return json({ok:true,duplicate:false,deleted_count:ids.length,target_event_ids:ids,tombstones},201);
}
