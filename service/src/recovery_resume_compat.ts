import type { AuthContext } from "./domain";
import { currentAuthority } from "./core";
import { ensureCurrentBangkokBusinessDate } from "./business_date";
import { commitLegacyMutation, type LegacyMutationInput } from "./legacy";
import { nowIso, sha256Hex } from "./util";

interface InboxRow { event_id:string;authority_epoch:number;authority_seq:number;service_generation:string;event_json:string;checksum:string;ingest_status:string; }
interface FallbackEnvelope { action:LegacyMutationInput["action"];business_date:string;actor:string;role:"SUPERADMIN"|"ADMIN"|"USER";device_id:string;occurred_at:string;payload_json:string; }

function parseEnvelope(raw:string):FallbackEnvelope{
  const x=JSON.parse(raw) as Partial<FallbackEnvelope>;
  if(!x.action||!x.business_date||!x.actor||!x.role||!x.payload_json)throw new Error("FALLBACK_EVENT_SHAPE_INVALID");
  if(!["enter","exit","resource_change","labor_start","labor_finish"].includes(x.action))throw new Error("FALLBACK_ACTION_INVALID");
  if(!["SUPERADMIN","ADMIN","USER"].includes(x.role))throw new Error("FALLBACK_ROLE_INVALID");
  return x as FallbackEnvelope;
}

async function verifyRow(row:InboxRow,e:FallbackEnvelope):Promise<void>{
  const raw=[row.event_id,row.authority_epoch,row.authority_seq,row.service_generation,e.action,e.business_date,e.actor,e.role,e.device_id||"",e.occurred_at||"",e.payload_json].join("|");
  const digest=await sha256Hex(raw);
  if(digest!==row.checksum)throw new Error(`FALLBACK_CHECKSUM_MISMATCH:${row.event_id}`);
}

async function loadInbox(db:D1Database,epoch:number):Promise<InboxRow[]>{
  const rows=(await db.prepare("SELECT event_id,authority_epoch,authority_seq,service_generation,event_json,checksum,ingest_status FROM fallback_event_inbox WHERE authority_epoch=?1 ORDER BY authority_seq").bind(epoch).all<InboxRow>()).results??[];
  if(!rows.length)throw new Error("FAILBACK_INBOX_EMPTY");
  for(let i=0;i<rows.length;i++)if(rows[i]!.authority_seq!==i+1)throw new Error(`FAILBACK_SEQUENCE_GAP:${i+1}`);
  const generation=rows[0]!.service_generation;
  if(rows.some(r=>r.service_generation!==generation))throw new Error("FAILBACK_GENERATION_MIXED");
  return rows;
}

async function locked(db:D1Database):Promise<boolean>{
  const r=await db.prepare("SELECT value FROM system_meta WHERE key='m2_reconciling'").first<{value:string}>();
  return r?.value==="1";
}

async function setLock(db:D1Database,value:boolean):Promise<void>{
  await db.prepare("INSERT INTO system_meta(key,value,updated_at) VALUES('m2_reconciling',?1,?2) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at").bind(value?"1":"0",nowIso()).run();
}

async function activeAttendanceShift(db:D1Database,businessDate:string,mnv:string):Promise<string>{
  if(!mnv)return "";
  const row=await db.prepare("SELECT shift FROM attendance_sessions WHERE business_date=?1 AND mnv=?2 AND state='ACTIVE'").bind(businessDate,mnv).first<{shift:string}>();
  return String(row?.shift||"").trim();
}

async function hydrateLegacyPackUser(db:D1Database,e:FallbackEnvelope,payload:Record<string,unknown>):Promise<void>{
  if(e.action!=="enter"&&e.action!=="resource_change")return;
  const table=String(payload.pack_table||"").trim(),existing=String(payload.user_pack||"").trim();
  if(!table||existing)return;
  const work=String(payload.work_choice||"").trim();
  if(work&&work!=="PACK")return;
  let shift=String(payload.shift||"").trim();
  if(!shift)shift=await activeAttendanceShift(db,e.business_date,String(payload.mnv||"").trim());
  if(!shift)throw new Error(`FAILBACK_PACK_SHIFT_MISSING:${table}`);
  const rows=(await db.prepare("SELECT user_pack FROM resource_pack_map WHERE pack_table=?1 AND shift=?2 AND available=1 ORDER BY user_pack LIMIT 2").bind(table,shift).all<{user_pack:string}>()).results??[];
  if(rows.length===0)throw new Error(`FAILBACK_PACK_USER_MISSING:${table}:${shift}`);
  if(rows.length!==1)throw new Error(`FAILBACK_PACK_USER_AMBIGUOUS:${table}:${shift}:${rows.length}`);
  const user=String(rows[0]!.user_pack||"").trim();
  if(!user)throw new Error(`FAILBACK_PACK_USER_EMPTY:${table}:${shift}`);
  payload.user_pack=user;
}

async function hydrateLegacyLaborShift(db:D1Database,e:FallbackEnvelope,payload:Record<string,unknown>):Promise<void>{
  if(e.action!=="labor_start"||String(payload.shift||"").trim())return;
  const shift=await activeAttendanceShift(db,e.business_date,String(payload.mnv||"").trim());
  if(!shift)throw new Error(`FAILBACK_LABOR_SHIFT_MISSING:${e.business_date}`);
  payload.shift=shift;
}

async function replayRow(db:D1Database,env:Env,row:InboxRow):Promise<void>{
  const e=parseEnvelope(row.event_json);
  await verifyRow(row,e);
  await ensureCurrentBangkokBusinessDate(db,e.business_date);
  const payload=JSON.parse(e.payload_json) as Record<string,unknown>;
  await hydrateLegacyPackUser(db,e,payload);
  await hydrateLegacyLaborShift(db,e,payload);
  payload.timestamp=e.occurred_at;payload._device_id=e.device_id;
  const auth:AuthContext={login_id:e.actor,role:e.role,display_name:e.actor,device_id:e.device_id||"gas-fallback",session_id:"M2_FALLBACK_REPLAY",verifier_hash:"M2_FALLBACK_REPLAY"};
  const mutation:LegacyMutationInput={action:e.action,payload,event_id:row.event_id,business_date:e.business_date,device_id:e.device_id||"gas-fallback"};
  const result=await commitLegacyMutation(db,env,auth,mutation),event=result.event as {authority_epoch:number;authority_seq:number};
  if(event.authority_epoch!==row.authority_epoch||event.authority_seq!==row.authority_seq)throw new Error(`FAILBACK_SEQUENCE_DIVERGENCE:${row.event_id}:${event.authority_epoch}/${event.authority_seq}`);
  await db.prepare("UPDATE fallback_event_inbox SET ingest_status='APPLIED',applied_at=?1,last_error=NULL WHERE event_id=?2").bind(nowIso(),row.event_id).run();
}

export async function resumeFailbackWithLegacyCompat(db:D1Database,env:Env,input:{fallback_epoch:number;confirmation:string;initiated_by?:string}):Promise<Record<string,unknown>>{
  if(input.confirmation!=="OWNER_LOCKED_M2_FAILBACK_RESUME")throw new Error("FAILBACK_RESUME_CONFIRMATION_REQUIRED");
  const before=await currentAuthority(db);
  if(before.mode!=="RECONCILING"||before.authority_epoch!==input.fallback_epoch)throw new Error(`FAILBACK_RESUME_STATE_INVALID:${before.mode}:${before.authority_epoch}`);
  if(!await locked(db))throw new Error("FAILBACK_RESUME_LOCK_MISSING");
  const rows=await loadInbox(db,input.fallback_epoch),generation=rows[0]!.service_generation;
  if(before.authority_seq<0||before.authority_seq>rows.length)throw new Error(`FAILBACK_RESUME_SEQ_INVALID:${before.authority_seq}`);
  for(const row of rows){const e=parseEnvelope(row.event_json);await verifyRow(row,e);await ensureCurrentBangkokBusinessDate(db,e.business_date);}
  for(let seq=1;seq<=before.authority_seq;seq++){
    const row=rows[seq-1]!;
    const ev=await db.prepare("SELECT event_id FROM events WHERE authority_epoch=?1 AND authority_seq=?2").bind(input.fallback_epoch,seq).first<{event_id:string}>();
    if(!ev||ev.event_id!==row.event_id)throw new Error(`FAILBACK_RESUME_EVENT_PREFIX_MISMATCH:${seq}`);
    if(row.ingest_status!=="APPLIED")await db.prepare("UPDATE fallback_event_inbox SET ingest_status='APPLIED',applied_at=COALESCE(applied_at,?1),last_error=NULL WHERE event_id=?2").bind(nowIso(),row.event_id).run();
  }
  const recoveryId=crypto.randomUUID(),started=nowIso();
  await db.prepare("INSERT INTO recovery_runs(recovery_id,recovery_type,from_generation,to_generation,source_authority_epoch,source_authority_seq,target_authority_epoch,status,started_at,validation_json) VALUES(?1,'FAILBACK',?2,?3,?4,?5,?6,'RUNNING',?7,?8)").bind(recoveryId,generation,env.SERVICE_GENERATION,input.fallback_epoch,rows.length,input.fallback_epoch+1,started,JSON.stringify({resume:true,legacy_pack_compat:true,legacy_labor_shift_compat:true,resume_from_seq:before.authority_seq})).run();
  try{
    await db.prepare("UPDATE authority_state SET mode='SERVICE_PRIMARY',service_generation=?1,updated_at=?2 WHERE singleton_id=1 AND authority_epoch=?3 AND authority_seq=?4 AND mode='RECONCILING'").bind(generation,nowIso(),input.fallback_epoch,before.authority_seq).run();
    let applied=before.authority_seq;
    for(let i=before.authority_seq;i<rows.length;i++){await replayRow(db,env,rows[i]!);applied++;}
    const checkpoint=await currentAuthority(db);
    if(checkpoint.authority_epoch!==input.fallback_epoch||checkpoint.authority_seq!==rows.length)throw new Error(`FAILBACK_RESUME_CHECKPOINT_DIVERGENCE:${checkpoint.authority_epoch}/${checkpoint.authority_seq}`);
    const eventCount=await db.prepare("SELECT COUNT(*) n FROM events WHERE authority_epoch=?1").bind(input.fallback_epoch).first<{n:number}>();
    if((eventCount?.n??0)<rows.length)throw new Error("FAILBACK_RESUME_EVENT_COUNT_MISMATCH");
    const at=nowIso();
    await db.prepare("UPDATE authority_state SET authority_epoch=?1,authority_seq=0,mode='SERVICE_PRIMARY',service_generation=?2,updated_at=?3 WHERE singleton_id=1 AND authority_epoch=?4 AND authority_seq=?5").bind(input.fallback_epoch+1,env.SERVICE_GENERATION,at,input.fallback_epoch,rows.length).run();
    await db.prepare("INSERT INTO authority_transitions(from_epoch,to_epoch,from_mode,to_mode,from_generation,to_generation,reason,initiated_by,checkpoint_epoch,checkpoint_seq,validation_json,created_at) VALUES(?1,?2,'RECONCILING','SERVICE_PRIMARY',?3,?4,'FAILBACK_RESUME_COMPLETE',?5,?1,?6,?7,?8)").bind(input.fallback_epoch,input.fallback_epoch+1,generation,env.SERVICE_GENERATION,String(input.initiated_by||"M2_RECOVERY_RESUME").slice(0,180),rows.length,JSON.stringify({resume:true,legacy_pack_compat:true,legacy_labor_shift_compat:true,applied,event_count:eventCount?.n??0,checksum_verified:true}),at).run();
    await setLock(db,false);
    const after=await currentAuthority(db),validation={resume:true,legacy_pack_compat:true,legacy_labor_shift_compat:true,inbox_count:rows.length,applied,event_count:eventCount?.n??0,checksum_verified:true,contiguous_sequence:true,final_epoch:after.authority_epoch};
    await db.prepare("UPDATE recovery_runs SET status='COMPLETE',completed_at=?1,validation_json=?2 WHERE recovery_id=?3").bind(at,JSON.stringify(validation),recoveryId).run();
    return{ok:true,recovery_id:recoveryId,validation,authority:after};
  }catch(e){
    await db.prepare("UPDATE authority_state SET mode='RECONCILING',updated_at=?1 WHERE singleton_id=1").bind(nowIso()).run().catch(()=>undefined);
    await db.prepare("UPDATE recovery_runs SET status='FAILED',completed_at=?1,error=?2 WHERE recovery_id=?3").bind(nowIso(),String(e).slice(0,1000),recoveryId).run().catch(()=>undefined);
    throw e;
  }
}
