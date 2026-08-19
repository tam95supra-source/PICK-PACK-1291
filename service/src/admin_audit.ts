import type { AuthContext, EventRow } from "./domain";
import { CoreError, currentAuthority, sanitizeSensitive } from "./core";
import { nowIso, sha256Hex } from "./util";

export interface AdminAuditInput {
  action:string;
  event_id?:string;
  target_type?:string;
  target_id?:string;
  target_label?:string;
  result?:string;
  detail?:string;
  device_id?:string;
  occurred_at?:string;
}

const ALLOWED=new Set(["staff_upsert","staff_delete","account_upsert","account_status","change_email","change_password","staff_import","account_login","account_logout","settings_change"]);
const TYPE:Record<string,string>={
  staff_upsert:"MASTER_STAFF_UPSERT",staff_delete:"MASTER_STAFF_DELETE",account_upsert:"ACCOUNT_UPSERT",account_status:"ACCOUNT_STATUS",change_email:"ACCOUNT_EMAIL",change_password:"ACCOUNT_PASSWORD",staff_import:"MASTER_STAFF_IMPORT",account_login:"ACCOUNT_LOGIN",account_logout:"ACCOUNT_LOGOUT",settings_change:"SETTINGS_CHANGE"
};
function text(v:unknown,max=240):string{return String(v??"").trim().slice(0,max);}

export async function commitAdminAudit(db:D1Database,auth:AuthContext,input:AdminAuditInput):Promise<{ok:true;duplicate:boolean;event:EventRow}>{
  const action=text(input.action,80);if(!ALLOWED.has(action))throw new CoreError("ADMIN_AUDIT_ACTION_INVALID","VALIDATION",400);
  const eventId=text(input.event_id,180)||crypto.randomUUID();
  const existing=await db.prepare("SELECT * FROM events WHERE event_id=?1").bind(eventId).first<EventRow>();if(existing)return{ok:true,duplicate:true,event:existing};
  const a=await currentAuthority(db);if(a.mode!=="SERVICE_PRIMARY"||a.scope!=="PRODUCTION")throw new CoreError("ADMIN_AUDIT_REQUIRES_SERVICE_PRIMARY","AUTHORITY",409,true);
  const seq=a.authority_seq+1,at=nowIso(),targetId=text(input.target_id,180)||auth.login_id,targetType=text(input.target_type,80)||"ADMIN_ACTION";
  const payload=sanitizeSensitive({action,target_type:targetType,target_id:targetId,target_label:text(input.target_label,240),result:text(input.result,80)||"OK",detail:text(input.detail,500)}) as Record<string,unknown>;
  const base={event_id:eventId,event_type:TYPE[action]||"ADMIN_AUDIT",entity_type:targetType,entity_id:targetId,business_date:"MASTER",authority_epoch:a.authority_epoch,authority_seq:seq,service_generation:a.service_generation,base_version:0,new_version:0,actor_id:auth.login_id,actor_role:auth.role,device_id:text(input.device_id,180)||auth.device_id,occurred_at:text(input.occurred_at,80)||at,committed_at:at,payload_json:JSON.stringify(payload),idempotency_key:`admin-audit:${eventId}`,origin:"ADMIN_AUDIT",schema_version:1};
  const checksum=await sha256Hex(JSON.stringify(base));
  const e:EventRow={...base,checksum};
  await db.batch([
    db.prepare("UPDATE authority_state SET authority_seq=?1,updated_at=?2 WHERE singleton_id=1 AND authority_epoch=?3 AND authority_seq=?4 AND mode='SERVICE_PRIMARY' AND scope='PRODUCTION'").bind(seq,at,a.authority_epoch,a.authority_seq),
    db.prepare(`INSERT INTO events(event_id,event_type,entity_type,entity_id,business_date,authority_epoch,authority_seq,service_generation,base_version,new_version,actor_id,actor_role,device_id,occurred_at,committed_at,payload_json,idempotency_key,origin,schema_version,checksum) VALUES(?1,?2,?3,?4,'MASTER',?5,?6,?7,0,0,?8,?9,?10,?11,?12,?13,?14,'ADMIN_AUDIT',1,?15)`).bind(e.event_id,e.event_type,e.entity_type,e.entity_id,e.authority_epoch,e.authority_seq,e.service_generation,e.actor_id,e.actor_role,e.device_id,e.occurred_at,e.committed_at,e.payload_json,e.idempotency_key,e.checksum),
    db.prepare("INSERT INTO sheet_replication_outbox(event_id,status,attempt_count,next_attempt_at,created_at) VALUES(?1,'PENDING',0,?2,?2)").bind(e.event_id,at),
  ]);
  return{ok:true,duplicate:false,event:e};
}
