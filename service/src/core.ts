import type { AuthContext, CanonicalMutationRequest, EventRow } from "./domain";
import { fold, nowIso, sha256Hex, validIsoDate, workChoice } from "./util";

interface AuthorityRow {
  authority_epoch: number;
  authority_seq: number;
  mode: "SERVICE_PRIMARY" | "GOOGLE_FALLBACK" | "OFFLINE_LOCAL" | "RECONCILING";
  scope: "STAGING_SHADOW" | "PRODUCTION";
  service_generation: string;
  updated_at: string;
}

interface AttendanceRow {
  session_id: string;
  mnv: string;
  business_date: string;
  shift: string;
  work_choice: "PICK" | "PACK" | "KHONG";
  state: "NOT_ENTERED" | "ACTIVE" | "ENDED";
  pda_serial: string | null;
  user_pick: string | null;
  pack_table: string | null;
  user_pack: string | null;
  pda_enter_status: string | null;
  pda_exit_status: string | null;
  resource_note: string;
  version: number; // S44_IDEMPOTENT_PDA_SESSION_ATTENDANCE
}

interface LaborRow {
  labor_id: string;
  mnv: string;
  business_date: string;
  state: "OPEN" | "COMPLETED" | "CANCELLED";
  version: number;
}

export class CoreError extends Error {
  constructor(
    public code: string,
    public errorClass: "VALIDATION" | "AUTH" | "PERMISSION" | "CONFLICT" | "RESOURCE" | "TRANSIENT" | "INTEGRITY" | "SCHEMA" | "INTERNAL",
    public status = 400,
    public retryable = false,
    public conflict?: Record<string, unknown>,
  ) {
    super(code);
  }
}

function text(payload: Record<string, unknown>, key: string, max = 240): string {
  return String(payload[key] ?? "").trim().slice(0, max);
}

const SENSITIVE_KEY=/(^|_)(token|password|verifier|secret|authorization|cookie|oauth)(_|$)/i;
export function sanitizeSensitive(value: unknown): unknown {
  if(Array.isArray(value))return value.map(sanitizeSensitive);
  if(value&&typeof value==="object"){const out:Record<string,unknown>={};for(const [k,v] of Object.entries(value as Record<string,unknown>)){if(SENSITIVE_KEY.test(k))continue;out[k]=sanitizeSensitive(v);}return out;}
  return value;
}

async function authority(db: D1Database): Promise<AuthorityRow> {
  const row = await db.prepare("SELECT authority_epoch,authority_seq,mode,scope,service_generation,updated_at FROM authority_state WHERE singleton_id=1").first<AuthorityRow>();
  if (!row) throw new CoreError("AUTHORITY_STATE_MISSING", "INTEGRITY", 503, false);
  return row;
}

async function existingByIdentity(db: D1Database, request: CanonicalMutationRequest): Promise<EventRow | null> {
  return db.prepare("SELECT * FROM events WHERE event_id=?1 OR idempotency_key=?2 ORDER BY committed_at LIMIT 1")
    .bind(request.event_id, request.idempotency_key).first<EventRow>();
}

function normalizeMutation(req: CanonicalMutationRequest): CanonicalMutationRequest {
  const eventId = String(req.event_id ?? "").trim();
  const idem = String(req.idempotency_key ?? "").trim();
  const entityId = String(req.entity_id ?? "").trim();
  const deviceId = String(req.device_id ?? "").trim();
  if (!eventId || eventId.length > 180) throw new CoreError("EVENT_ID_REQUIRED", "VALIDATION", 400);
  if (!idem || idem.length > 220) throw new CoreError("IDEMPOTENCY_KEY_REQUIRED", "VALIDATION", 400);
  if (!entityId || entityId.length > 220) throw new CoreError("ENTITY_ID_REQUIRED", "VALIDATION", 400);
  if (!deviceId || deviceId.length > 180) throw new CoreError("DEVICE_ID_REQUIRED", "VALIDATION", 400);
  if (!validIsoDate(String(req.business_date ?? ""))) throw new CoreError("BUSINESS_DATE_INVALID", "VALIDATION", 400);
  if (!Number.isInteger(req.base_version) || req.base_version < 0) throw new CoreError("BASE_VERSION_INVALID", "VALIDATION", 400);
  if (!["ATTENDANCE_ENTER","ATTENDANCE_EXIT","RESOURCE_CHANGE","LABOR_START","LABOR_FINISH","M1_SHADOW_PROBE"].includes(String(req.event_type))) throw new CoreError("EVENT_TYPE_UNSUPPORTED","VALIDATION",400);
  if (req.schema_version !== 1) throw new CoreError("SCHEMA_VERSION_UNSUPPORTED", "SCHEMA", 409);
  return {
    ...req,
    event_id: eventId,
    idempotency_key: idem,
    entity_id: entityId,
    device_id: deviceId,
    business_date: String(req.business_date),
    timestamp: String(req.timestamp || nowIso()),
    payload: sanitizeSensitive(req.payload && typeof req.payload === "object" ? req.payload : {}) as Record<string,unknown>,
    client_source: req.client_source === "WEB" || req.client_source === "FILE_IMPORT" ? req.client_source : "PDA",
  };
}

function eventStatements(db: D1Database, event: EventRow, expectedSeq: number): D1PreparedStatement[] {
  return [
    db.prepare("UPDATE authority_state SET authority_seq=?1,updated_at=?2 WHERE singleton_id=1 AND authority_seq=?3 AND authority_epoch=?4")
      .bind(event.authority_seq, event.committed_at, expectedSeq, event.authority_epoch),
    db.prepare(`INSERT INTO events(event_id,event_type,entity_type,entity_id,business_date,authority_epoch,authority_seq,service_generation,base_version,new_version,actor_id,actor_role,device_id,occurred_at,committed_at,payload_json,idempotency_key,origin,schema_version,checksum)
      VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20)`)
      .bind(event.event_id,event.event_type,event.entity_type,event.entity_id,event.business_date,event.authority_epoch,event.authority_seq,event.service_generation,event.base_version,event.new_version,event.actor_id,event.actor_role,event.device_id,event.occurred_at,event.committed_at,event.payload_json,event.idempotency_key,event.origin,event.schema_version,event.checksum),
    db.prepare("INSERT INTO sheet_replication_outbox(event_id,status,next_attempt_at) VALUES(?1,'PENDING',?2)").bind(event.event_id,event.committed_at),
    db.prepare("INSERT INTO mutation_assertions(event_id,ok) VALUES(?1,1)").bind(event.event_id),
  ];
}

async function buildEvent(req: CanonicalMutationRequest, auth: AuthContext, a: AuthorityRow, newVersion: number): Promise<EventRow> {
  const committed = nowIso();
  const base = {
    event_id:req.event_id,event_type:req.event_type,entity_type:req.entity_type,entity_id:req.entity_id,business_date:req.business_date,
    authority_epoch:a.authority_epoch,authority_seq:a.authority_seq+1,service_generation:a.service_generation,
    base_version:req.base_version,new_version:newVersion,actor_id:auth.login_id,actor_role:auth.role,device_id:req.device_id,
    occurred_at:req.timestamp,committed_at:committed,payload_json:JSON.stringify(req.payload),idempotency_key:req.idempotency_key,
    origin:"SERVICE",schema_version:1,
  };
  return { ...base, checksum: await sha256Hex(JSON.stringify(base)) };
}

function leaseStatements(db: D1Database, sessionId: string, mnv: string, date: string, eventId: string, at: string, resources: Array<[string,string]>): D1PreparedStatement[] {
  const out: D1PreparedStatement[] = [];
  for (const [type,id] of resources) {
    if (!id) continue;
    out.push(db.prepare("INSERT INTO resource_leases(resource_type,resource_id,session_id,mnv,business_date,acquired_event_id,acquired_at) VALUES(?1,?2,?3,?4,?5,?6,?7)").bind(type,id,sessionId,mnv,date,eventId,at));
    if (type === "USER_PICK" || type === "USER_PACK") {
      out.push(db.prepare("INSERT INTO resource_daily_consumption(business_date,resource_type,resource_id,mnv,first_event_id) VALUES(?1,?2,?3,?4,?5)").bind(date,type,id,mnv,eventId));
    }
  }
  return out;
}

async function commitAttendanceEnter(db: D1Database, auth: AuthContext, req: CanonicalMutationRequest, a: AuthorityRow): Promise<EventRow> {
  const p=req.payload, mnv=text(p,"mnv",80), shift=text(p,"shift",80), choice=workChoice(p.work_choice);
  if(!mnv||!shift) throw new CoreError("ATTENDANCE_FIELDS_REQUIRED","VALIDATION",400);
  const pda=text(p,"pda_serial"), pick=text(p,"user_pick"), table=text(p,"pack_table"), pack=text(p,"user_pack"), pdaEnterStatus=text(p,"pda_enter_status",180), resourceNote=text(p,"resource_note",500);
  const checks=await db.batch([
    db.prepare("SELECT 1 AS x FROM employees WHERE mnv=?1").bind(mnv),
    db.prepare("SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,pda_enter_status,pda_exit_status,resource_note,version FROM attendance_sessions WHERE mnv=?1 AND business_date=?2").bind(mnv,req.business_date),
    db.prepare("SELECT available FROM resources WHERE resource_type='PDA' AND resource_id=?1").bind(pda),
    db.prepare("SELECT available FROM resources WHERE resource_type='USER_PICK' AND resource_id=?1").bind(pick),
    db.prepare("SELECT available FROM resources WHERE resource_type='PACK_TABLE' AND resource_id=?1").bind(table),
    db.prepare("SELECT available FROM resources WHERE resource_type='USER_PACK' AND resource_id=?1").bind(pack),
  ]);
  if(!(checks[0]?.results?.length)) throw new CoreError("EMPLOYEE_NOT_FOUND","VALIDATION",404);
  const current=(checks[1]?.results?.[0]??null) as AttendanceRow|null,currentVersion=current?.version??0;
  if(currentVersion!==req.base_version) throw new CoreError("STALE_BASE_VERSION","CONFLICT",409,false,{current_version:currentVersion});
  if(current?.state==="ACTIVE") throw new CoreError("ATTENDANCE_ALREADY_ACTIVE","CONFLICT",409,false,{session_id:current.session_id});
  if(current?.state==="ENDED") throw new CoreError("ATTENDANCE_ALREADY_ENDED","CONFLICT",409,false,{session_id:current.session_id});
  if(pda&&!Boolean((checks[2]?.results?.[0] as {available?:number}|undefined)?.available)) throw new CoreError("PDA_UNAVAILABLE","RESOURCE",409);
  if(pick&&!Boolean((checks[3]?.results?.[0] as {available?:number}|undefined)?.available)) throw new CoreError("USER_PICK_UNAVAILABLE","RESOURCE",409);
  if(table&&!Boolean((checks[4]?.results?.[0] as {available?:number}|undefined)?.available)) throw new CoreError("PACK_TABLE_UNAVAILABLE","RESOURCE",409);
  if(pack&&!Boolean((checks[5]?.results?.[0] as {available?:number}|undefined)?.available)) throw new CoreError("USER_PACK_UNAVAILABLE","RESOURCE",409);
  if(choice==="PICK"&&!pda) throw new CoreError("PDA_REQUIRED_FOR_PICK","VALIDATION",400);
  if(choice==="PACK"&&(!table||!pack)) throw new CoreError("PACK_RESOURCES_REQUIRED","VALIDATION",400);
  const event=await buildEvent(req,auth,a,currentVersion+1);
  const sessionId=req.entity_id;
  const stmts=eventStatements(db,event,a.authority_seq);
  stmts.push(db.prepare(`INSERT INTO attendance_sessions(session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,enter_at,entered_by,version,updated_at)
    VALUES(?1,?2,?3,?4,?5,'ACTIVE',?6,?7,?8,?9,?10,?11,?12,?13)
    ON CONFLICT(mnv,business_date) DO UPDATE SET session_id=excluded.session_id,shift=excluded.shift,work_choice=excluded.work_choice,state='ACTIVE',pda_serial=excluded.pda_serial,user_pick=excluded.user_pick,pack_table=excluded.pack_table,user_pack=excluded.user_pack,enter_at=excluded.enter_at,entered_by=excluded.entered_by,version=excluded.version,updated_at=excluded.updated_at`)
    .bind(sessionId,mnv,req.business_date,shift,choice,pda||null,pick||null,table||null,pack||null,event.committed_at,auth.login_id,event.new_version,event.committed_at));
  stmts.push(db.prepare("UPDATE attendance_sessions SET pda_enter_status=?1,resource_note=?2 WHERE session_id=?3").bind(pdaEnterStatus||null,resourceNote,sessionId));
  stmts.push(...leaseStatements(db,sessionId,mnv,req.business_date,event.event_id,event.committed_at,[["PDA",pda],["USER_PICK",pick],["PACK_TABLE",table],["USER_PACK",pack]]));
  try { await db.batch(stmts); } catch (e) {
    const msg=String(e);
    if(msg.includes("resource_leases")||msg.includes("resource_daily_consumption")||msg.includes("UNIQUE constraint")) throw new CoreError("EXCLUSIVE_RESOURCE_CONFLICT","RESOURCE",409,false);
    throw e;
  }
  return event;
}

async function commitAttendanceExit(db:D1Database, auth:AuthContext, req:CanonicalMutationRequest, a:AuthorityRow):Promise<EventRow>{
  const p=req.payload,mnv=text(p,"mnv",80);
  const checks=await db.batch([
    db.prepare("SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,pda_enter_status,pda_exit_status,resource_note,version FROM attendance_sessions WHERE mnv=?1 AND business_date=?2").bind(mnv,req.business_date),
    db.prepare("SELECT COUNT(*) AS n FROM labor_sessions WHERE mnv=?1 AND business_date=?2 AND state='OPEN'").bind(mnv,req.business_date),
  ]);
  const current=(checks[0]?.results?.[0]??null) as AttendanceRow|null;
  if(!current||current.state!=="ACTIVE") throw new CoreError("ATTENDANCE_NOT_ACTIVE","CONFLICT",409);
  if(current.version!==req.base_version) throw new CoreError("STALE_BASE_VERSION","CONFLICT",409,false,{current_version:current.version});
  const open=(checks[1]?.results?.[0]??null) as {n?:number}|null;if((open?.n??0)>0) throw new CoreError("OPEN_LABOR_BLOCKS_EXIT","CONFLICT",409);
  const pdaExitStatus=text(p,"pda_exit_status",180);
  const event=await buildEvent(req,auth,a,current.version+1),stmts=eventStatements(db,event,a.authority_seq);
  stmts.push(db.prepare("UPDATE attendance_sessions SET state='ENDED',exit_at=?1,exited_by=?2,version=?3,updated_at=?1 WHERE session_id=?4 AND version=?5 AND state='ACTIVE'").bind(event.committed_at,auth.login_id,event.new_version,current.session_id,current.version));
  stmts.push(db.prepare("UPDATE attendance_sessions SET pda_exit_status=?1 WHERE session_id=?2").bind(pdaExitStatus||null,current.session_id));
  stmts.push(db.prepare("DELETE FROM resource_leases WHERE session_id=?1").bind(current.session_id));
  await db.batch(stmts); return event;
}

async function commitResourceChange(db:D1Database, auth:AuthContext, req:CanonicalMutationRequest, a:AuthorityRow):Promise<EventRow>{
  const p=req.payload,mnv=text(p,"mnv",80);
  const current=await db.prepare("SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,pda_enter_status,pda_exit_status,resource_note,version FROM attendance_sessions WHERE mnv=?1 AND business_date=?2").bind(mnv,req.business_date).first<AttendanceRow>();
  if(!current||current.state!=="ACTIVE") throw new CoreError("ATTENDANCE_NOT_ACTIVE","CONFLICT",409);
  if(current.version!==req.base_version) throw new CoreError("STALE_BASE_VERSION","CONFLICT",409,false,{current_version:current.version});
  const pda=text(p,"pda_serial")||current.pda_serial||"",pick=text(p,"user_pick")||"",table=text(p,"pack_table")||"",pack=text(p,"user_pack")||"";
  const event=await buildEvent(req,auth,a,current.version+1),stmts=eventStatements(db,event,a.authority_seq);
  stmts.push(db.prepare("DELETE FROM resource_leases WHERE session_id=?1").bind(current.session_id));
  stmts.push(db.prepare("UPDATE attendance_sessions SET pda_serial=?1,user_pick=?2,pack_table=?3,user_pack=?4,version=?5,updated_at=?6 WHERE session_id=?7 AND version=?8").bind(pda||null,pick||null,table||null,pack||null,event.new_version,event.committed_at,current.session_id,current.version));
  const resourceNote=text(p,"resource_note",500);
  if(resourceNote)stmts.push(db.prepare("UPDATE attendance_sessions SET resource_note=?1 WHERE session_id=?2").bind(resourceNote,current.session_id));
  stmts.push(...leaseStatements(db,current.session_id,current.mnv,req.business_date,event.event_id,event.committed_at,[["PDA",pda],["USER_PICK",pick],["PACK_TABLE",table],["USER_PACK",pack]]));
  try{await db.batch(stmts);}catch(e){if(String(e).includes("UNIQUE constraint"))throw new CoreError("EXCLUSIVE_RESOURCE_CONFLICT","RESOURCE",409);throw e;} return event;
}

async function commitLaborStart(db:D1Database, auth:AuthContext, req:CanonicalMutationRequest, a:AuthorityRow):Promise<EventRow>{
  if(auth.role==="USER") throw new CoreError("LABOR_ADMIN_REQUIRED","PERMISSION",403);
  const p=req.payload,mnv=text(p,"mnv",80),shift=text(p,"shift",80),laborType=text(p,"labor_type",180),marker=text(p,"time_marker",120);
  if(!mnv||!shift||!laborType||!marker) throw new CoreError("LABOR_FIELDS_REQUIRED","VALIDATION",400);
  const checks=await db.batch([
    db.prepare("SELECT labor_id,mnv,business_date,state,version FROM labor_sessions WHERE labor_id=?1").bind(req.entity_id),
    db.prepare("SELECT state FROM attendance_sessions WHERE mnv=?1 AND business_date=?2").bind(mnv,req.business_date),
  ]);
  const current=(checks[0]?.results?.[0]??null) as LaborRow|null,v=current?.version??0;
  if(v!==req.base_version)throw new CoreError("STALE_BASE_VERSION","CONFLICT",409,false,{current_version:v});if(current?.state==="OPEN")throw new CoreError("LABOR_ALREADY_OPEN","CONFLICT",409);
  const attendance=(checks[1]?.results?.[0]??null) as {state?:string}|null;if(attendance?.state!=="ACTIVE")throw new CoreError("ATTENDANCE_NOT_ACTIVE","CONFLICT",409);
  const event=await buildEvent(req,auth,a,v+1),stmts=eventStatements(db,event,a.authority_seq);
  stmts.push(db.prepare(`INSERT INTO labor_sessions(labor_id,mnv,business_date,shift,labor_type,time_marker,state,start_at,note,deduct_staff,start_event_id,version,updated_at)
    VALUES(?1,?2,?3,?4,?5,?6,'OPEN',?7,?8,?9,?10,?11,?12)`)
    .bind(req.entity_id,mnv,req.business_date,shift,laborType,marker,event.committed_at,text(p,"note",500),fold(p.deduct_staff)==="CO"?1:0,event.event_id,event.new_version,event.committed_at));
  await db.batch(stmts);return event;
}

async function commitLaborFinish(db:D1Database, auth:AuthContext, req:CanonicalMutationRequest, a:AuthorityRow):Promise<EventRow>{
  if(auth.role==="USER") throw new CoreError("LABOR_ADMIN_REQUIRED","PERMISSION",403);
  const current=await db.prepare("SELECT labor_id,mnv,business_date,state,version FROM labor_sessions WHERE labor_id=?1").bind(req.entity_id).first<LaborRow>();
  if(!current||current.state!=="OPEN")throw new CoreError("LABOR_NOT_OPEN","CONFLICT",409);if(current.version!==req.base_version)throw new CoreError("STALE_BASE_VERSION","CONFLICT",409,false,{current_version:current.version});
  const event=await buildEvent(req,auth,a,current.version+1),stmts=eventStatements(db,event,a.authority_seq);
  stmts.push(db.prepare("UPDATE labor_sessions SET state='COMPLETED',end_at=?1,finish_event_id=?2,version=?3,updated_at=?1 WHERE labor_id=?4 AND version=?5 AND state='OPEN'").bind(event.committed_at,event.event_id,event.new_version,current.labor_id,current.version));
  await db.batch(stmts);return event;
}

async function commitProbe(db:D1Database,auth:AuthContext,req:CanonicalMutationRequest,a:AuthorityRow):Promise<EventRow>{const event=await buildEvent(req,auth,a,req.base_version+1);await db.batch(eventStatements(db,event,a.authority_seq));return event;}

export async function commitMutation(db:D1Database,env:Env,auth:AuthContext,input:CanonicalMutationRequest):Promise<{event:EventRow;duplicate:boolean}>{
  const req=normalizeMutation(input);if(req.event_type==="M1_SHADOW_PROBE"&&auth.role!=="SUPERADMIN")throw new CoreError("SHADOW_PROBE_SUPERADMIN_REQUIRED","PERMISSION",403);const preflightStatements:D1PreparedStatement[]=[
    db.prepare("SELECT * FROM events WHERE event_id=?1 OR idempotency_key=?2 ORDER BY committed_at LIMIT 1").bind(req.event_id,req.idempotency_key),
    db.prepare("SELECT authority_epoch,authority_seq,mode,scope,service_generation,updated_at FROM authority_state WHERE singleton_id=1"),
  ];
  const writeWindow=auth.role==="SUPERADMIN"?7:2;
  if(writeWindow)preflightStatements.push(db.prepare("SELECT business_date FROM business_dates ORDER BY sequence_no DESC LIMIT ?1").bind(writeWindow));
  const preflight=await db.batch(preflightStatements),prior=(preflight[0]?.results?.[0]??null) as EventRow|null;if(prior)return{event:prior,duplicate:true};
  const a=(preflight[1]?.results?.[0]??null) as AuthorityRow|null;if(!a)throw new CoreError("AUTHORITY_STATE_MISSING","INTEGRITY",503,false);
  if(a.mode!=="SERVICE_PRIMARY")throw new CoreError("SERVICE_NOT_WRITE_AUTHORITY","CONFLICT",409,true,{mode:a.mode,authority_epoch:a.authority_epoch});
  if(req.authority_epoch!==undefined&&req.authority_epoch!==a.authority_epoch)throw new CoreError("AUTHORITY_EPOCH_STALE","CONFLICT",409,false,{current_epoch:a.authority_epoch});
  if(req.service_generation&&req.service_generation!==a.service_generation)throw new CoreError("SERVICE_GENERATION_STALE","CONFLICT",409,true,{service_generation:a.service_generation});
  if(writeWindow){
    const allowed=new Set((preflight[2]?.results??[]).map(r=>String((r as {business_date?:string}).business_date??"")));if(!allowed.has(req.business_date))throw new CoreError(auth.role==="SUPERADMIN"?"BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW":"BUSINESS_DATE_NOT_N_N_MINUS_1","PERMISSION",403,false,{allowed:[...allowed]});
  }
  try{
    const event= req.event_type==="ATTENDANCE_ENTER"?await commitAttendanceEnter(db,auth,req,a):req.event_type==="ATTENDANCE_EXIT"?await commitAttendanceExit(db,auth,req,a):req.event_type==="RESOURCE_CHANGE"?await commitResourceChange(db,auth,req,a):req.event_type==="LABOR_START"?await commitLaborStart(db,auth,req,a):req.event_type==="LABOR_FINISH"?await commitLaborFinish(db,auth,req,a):await commitProbe(db,auth,req,a);
    return{event,duplicate:false};
  }catch(e){
    if(e instanceof CoreError)throw e;
    const msg=String(e);if(msg.includes("UNIQUE constraint failed: events.authority_epoch, events.authority_seq"))throw new CoreError("AUTHORITY_RACE_RETRY","TRANSIENT",409,true);
    if(msg.includes("events.event_id")||msg.includes("events.idempotency_key")){const again=await existingByIdentity(db,req);if(again)return{event:again,duplicate:true};}
    throw e;
  }
}

export async function delta(db:D1Database,epoch:number,afterSeq:number,limit=500):Promise<{authority:AuthorityRow;events:EventRow[];has_more:boolean}>{
  const cap=Math.max(1,Math.min(500,limit)),results=await db.batch([
    db.prepare("SELECT authority_epoch,authority_seq,mode,scope,service_generation,updated_at FROM authority_state WHERE singleton_id=1"),
    db.prepare("SELECT * FROM events WHERE authority_epoch=?1 AND authority_seq>?2 ORDER BY authority_seq LIMIT ?3").bind(epoch,afterSeq,cap+1),
  ]),a=(results[0]?.results?.[0]??null) as AuthorityRow|null;
  if(!a)throw new CoreError("AUTHORITY_STATE_MISSING","INTEGRITY",503,false);if(epoch!==a.authority_epoch)return{authority:a,events:[],has_more:false};
  const all=(results[1]?.results??[]) as EventRow[];return{authority:a,events:all.slice(0,cap),has_more:all.length>cap};
}

export async function currentAuthority(db:D1Database):Promise<AuthorityRow>{return authority(db);}

export async function transitionAuthority(db:D1Database,input:{expected_epoch:number;mode:AuthorityRow["mode"];scope?:AuthorityRow["scope"];service_generation?:string;increment_epoch?:boolean}):Promise<AuthorityRow>{
  const a=await authority(db);if(a.authority_epoch!==input.expected_epoch)throw new CoreError("AUTHORITY_EPOCH_STALE","CONFLICT",409,false,{current_epoch:a.authority_epoch});
  const nextEpoch=input.increment_epoch?a.authority_epoch+1:a.authority_epoch,nextSeq=input.increment_epoch?0:a.authority_seq,at=nowIso();
  await db.prepare("UPDATE authority_state SET authority_epoch=?1,authority_seq=?2,mode=?3,scope=?4,service_generation=?5,updated_at=?6 WHERE singleton_id=1 AND authority_epoch=?7")
    .bind(nextEpoch,nextSeq,input.mode,input.scope??a.scope,input.service_generation??a.service_generation,at,a.authority_epoch).run();
  return authority(db);
}
