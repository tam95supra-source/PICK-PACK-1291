import { REPLICA_HEADERS, type EventRow } from "./domain";
import { nowIso } from "./util";

interface OutboxRow { outbox_id:number; event_id:string; attempt_count:number; }
interface GoogleToken { access_token?:string; expires_in?:number; error?:string; }
interface EmployeeRow { mnv:string;full_name:string;phone:string;main_position:string;supplier:string;department:string;site:string;warehouse:string; }
interface AttendanceReplicaRow { session_id:string;mnv:string;business_date:string;shift:string;work_choice:string;pda_serial:string|null;user_pick:string|null;pack_table:string|null;user_pack:string|null; }
interface LaborReplicaRow { labor_id:string;mnv:string;business_date:string;shift:string;labor_type:string;time_marker:string;start_at:string;end_at:string|null;note:string;deduct_staff:number;start_event_id:string;finish_event_id:string|null; }

const RA_HEADERS=["Ngày","Ca","Mã nhân viên","Họ và tên","Số điện thoại","Nhà cung cấp","Bộ phận","Site","Kho","Vị trí chính","Vị trí trong ca","Seri PDA","User Pick","Bàn Pack","User Pack","Loại thao tác","Ghi chú","Người cập nhật","Thời gian cập nhật","Event ID","App action","App revision"] as const;
const LABOR_HEADERS=["Ngày","Ca","Mã nhân viên","Họ và tên","Số điện thoại","Nhà cung cấp","Bộ phận","Site","Kho","Vị trí chính","Vị trí trong ca","Thông tin công nhật","Thời gian bắt đầu","Thời gian kết thúc","Mốc thời gian","Trạng thái","Ghi chú","Người cập nhật","Thời gian cập nhật","Event ID","Finish Event ID","App revision","Khấu trừ nhân sự"] as const;
const HISTORY_HEADERS=["Ngày","Session ID","Mã nhân viên","Họ tên","Ca","Loại sự kiện","Nhãn sự kiện","Thời gian","Người xử lý","Chi tiết","Event ID","Phạm vi","App Revision"] as const;

async function googleAccessToken(env:Env):Promise<string>{
  const body=new URLSearchParams({client_id:env.GOOGLE_OAUTH_CLIENT_ID,client_secret:env.GOOGLE_OAUTH_CLIENT_SECRET,refresh_token:env.GOOGLE_OAUTH_REFRESH_TOKEN,grant_type:"refresh_token"});
  const r=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body});
  const j=await r.json<GoogleToken>();if(!r.ok||!j.access_token)throw new Error(`GOOGLE_OAUTH:${j.error??r.status}`);return j.access_token;
}

function authHeaders(token:string,extra:HeadersInit={}):HeadersInit{return{authorization:`Bearer ${token}`,...extra};}
function a1(name:string,range:string):string{return `'${name.replace(/'/g,"''")}'!${range}`;}
function visibleDate(iso:string):string{const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);return m?`${m[3]}/${m[2]}/${m[1]}`:iso;}
function visibleDateTime(iso:string):string{
  const d=new Date(iso);if(Number.isNaN(d.getTime()))return iso;
  return new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Bangkok",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"}).format(d).replace(",","");
}
function workLabel(v:string):string{return v==="PICK"?"Pick":v==="PACK"?"Pack":"Không";}
function payload(e:EventRow):Record<string,unknown>{try{return JSON.parse(e.payload_json) as Record<string,unknown>;}catch{return{};}}
function ptext(p:Record<string,unknown>,key:string):string{return String(p[key]??"").trim();}

async function getValues(sheetId:string,token:string,sheet:string,range:string):Promise<unknown[][]>{
  const url=`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(sheetId)}/values/${encodeURIComponent(a1(sheet,range))}?valueRenderOption=FORMATTED_VALUE`;
  const r=await fetch(url,{headers:authHeaders(token)});if(!r.ok)throw new Error(`GOOGLE_READ:${sheet}:${r.status}`);const j=await r.json<{values?:unknown[][]}>();return j.values??[];
}
async function putValues(sheetId:string,token:string,sheet:string,range:string,values:unknown[][]):Promise<void>{
  const full=a1(sheet,range),url=`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(sheetId)}/values/${encodeURIComponent(full)}?valueInputOption=RAW`;
  const r=await fetch(url,{method:"PUT",headers:authHeaders(token,{"content-type":"application/json"}),body:JSON.stringify({range:full,majorDimension:"ROWS",values})});
  if(!r.ok){const t=await r.text();throw new Error(`GOOGLE_PUT:${sheet}:${r.status}:${t.slice(0,200)}`);}
}
async function appendValues(sheetId:string,token:string,sheet:string,range:string,values:unknown[][]):Promise<string>{
  if(!values.length)return"NOOP";const full=a1(sheet,range),url=`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(sheetId)}/values/${encodeURIComponent(full)}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`;
  const r=await fetch(url,{method:"POST",headers:authHeaders(token,{"content-type":"application/json"}),body:JSON.stringify({range:full,majorDimension:"ROWS",values})});
  if(!r.ok){const t=await r.text();throw new Error(`GOOGLE_APPEND:${sheet}:${r.status}:${t.slice(0,240)}`);}const j=await r.json<{updates?:{updatedRange?:string}}>();return j.updates?.updatedRange??"APPENDED";
}
async function assertHeader(sheetId:string,token:string,sheet:string,headers:readonly string[]):Promise<void>{
  const end=String.fromCharCode(64+headers.length);const values=await getValues(sheetId,token,sheet,`A1:${end}1`),got=(values[0]??[]).map(String);
  if(JSON.stringify(got)!==JSON.stringify([...headers]))throw new Error(`GOOGLE_OPERATIONAL_SCHEMA_DRIFT:${sheet}`);
}

async function ensureReplicaSheet(env:Env,token:string):Promise<void>{
  const id=env.GOOGLE_STAGING_SHEET_ID;
  const meta=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}?fields=sheets.properties(sheetId,title,hidden)`,{headers:authHeaders(token)});
  if(!meta.ok)throw new Error(`GOOGLE_META:${meta.status}`);
  const m=await meta.json<{sheets?:Array<{properties?:{sheetId?:number;title?:string;hidden?:boolean}}>}>();
  const p=m.sheets?.map(x=>x.properties).find(x=>x?.title==="__M1_SERVICE_REPLICA");
  if(!p){
    const create=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}:batchUpdate`,{method:"POST",headers:authHeaders(token,{"content-type":"application/json"}),body:JSON.stringify({requests:[{addSheet:{properties:{title:"__M1_SERVICE_REPLICA",hidden:true}}}]})});
    if(!create.ok)throw new Error(`GOOGLE_CREATE_REPLICA:${create.status}`);
  }else if(!p.hidden&&p.sheetId!==undefined){
    const hide=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}:batchUpdate`,{method:"POST",headers:authHeaders(token,{"content-type":"application/json"}),body:JSON.stringify({requests:[{updateSheetProperties:{properties:{sheetId:p.sheetId,hidden:true},fields:"hidden"}}]})});
    if(!hide.ok)throw new Error(`GOOGLE_HIDE_REPLICA:${hide.status}`);
  }
  await putValues(id,token,"__M1_SERVICE_REPLICA","A1:T1",[[...REPLICA_HEADERS]]);
}

function eventValues(e:EventRow):unknown[]{return[e.event_id,e.event_type,e.entity_type,e.entity_id,e.business_date,e.authority_epoch,e.authority_seq,e.service_generation,e.base_version,e.new_version,e.actor_id,e.actor_role,e.device_id,e.occurred_at,e.committed_at,e.idempotency_key,e.origin,e.schema_version,e.checksum,e.payload_json];}
async function existingEventIds(env:Env,token:string):Promise<Set<string>>{const rows=await getValues(env.GOOGLE_STAGING_SHEET_ID,token,"__M1_SERVICE_REPLICA","A2:A");return new Set(rows.map(r=>String(r[0]??"")).filter(Boolean));}
async function appendTechnicalRows(env:Env,token:string,events:EventRow[]):Promise<string>{return appendValues(env.GOOGLE_STAGING_SHEET_ID,token,"__M1_SERVICE_REPLICA","A:T",events.map(eventValues));}

async function employee(db:D1Database,mnv:string):Promise<EmployeeRow>{const e=await db.prepare("SELECT mnv,full_name,phone,main_position,supplier,department,site,warehouse FROM employees WHERE mnv=?1").bind(mnv).first<EmployeeRow>();if(!e)throw new Error(`REPLICA_EMPLOYEE_MISSING:${mnv}`);return e;}
async function attendance(db:D1Database,entityId:string):Promise<AttendanceReplicaRow>{const s=await db.prepare("SELECT session_id,mnv,business_date,shift,work_choice,pda_serial,user_pick,pack_table,user_pack FROM attendance_sessions WHERE session_id=?1").bind(entityId).first<AttendanceReplicaRow>();if(!s)throw new Error(`REPLICA_ATTENDANCE_MISSING:${entityId}`);return s;}
async function labor(db:D1Database,entityId:string):Promise<LaborReplicaRow>{const s=await db.prepare("SELECT labor_id,mnv,business_date,shift,labor_type,time_marker,start_at,end_at,note,deduct_staff,start_event_id,finish_event_id FROM labor_sessions WHERE labor_id=?1").bind(entityId).first<LaborReplicaRow>();if(!s)throw new Error(`REPLICA_LABOR_MISSING:${entityId}`);return s;}

async function operationalEventPresent(sheetId:string,token:string,sheet:string,column:string,eventId:string):Promise<boolean>{const rows=await getValues(sheetId,token,sheet,`${column}2:${column}`);return rows.some(r=>String(r[0]??"")===eventId);}
async function appendHistory(sheetId:string,token:string,e:EventRow,sessionId:string,mnv:string,name:string,shift:string,label:string,detail:string):Promise<void>{
  if(await operationalEventPresent(sheetId,token,"LỊCH SỬ NGHIỆP VỤ","K",e.event_id))return;
  await appendValues(sheetId,token,"LỊCH SỬ NGHIỆP VỤ","A:M",[[visibleDate(e.business_date),sessionId,mnv,name,shift,e.event_type,label,visibleDateTime(e.occurred_at),e.actor_id,detail,e.event_id,"SERVICE_M2",e.authority_seq]]);
}

async function replicateAttendanceOperational(db:D1Database,sheetId:string,token:string,e:EventRow):Promise<void>{
  if(await operationalEventPresent(sheetId,token,"RA - VÀO TRONG CA","T",e.event_id))return;
  const s=await attendance(db,e.entity_id),emp=await employee(db,s.mnv),p=payload(e);
  const labels:Record<string,[string,string]>={ATTENDANCE_ENTER:["Vào ca","ENTER"],RESOURCE_CHANGE:["Đổi tài nguyên","RESOURCE"],ATTENDANCE_EXIT:["Ra ca","EXIT"]};
  const [label,appAction]=labels[e.event_type]??[e.event_type,e.event_type];const note=ptext(p,"note")||"SERVICE M2";
  await appendValues(sheetId,token,"RA - VÀO TRONG CA","A:V",[[visibleDate(e.business_date),s.shift,s.mnv,emp.full_name,emp.phone,emp.supplier,emp.department,emp.site,emp.warehouse,emp.main_position,workLabel(s.work_choice),s.pda_serial??"",s.user_pick??"",s.pack_table??"",s.user_pack??"",label,note,e.actor_id,visibleDateTime(e.occurred_at),e.event_id,appAction,e.authority_seq]]);
  const detail=[workLabel(s.work_choice),s.pda_serial,s.user_pick,s.pack_table,s.user_pack].filter(Boolean).join(" • ");
  await appendHistory(sheetId,token,e,s.session_id,s.mnv,emp.full_name,s.shift,label,detail);
}

async function replicateLaborStartOperational(db:D1Database,sheetId:string,token:string,e:EventRow):Promise<void>{
  if(await operationalEventPresent(sheetId,token,"CÔNG NHẬT","T",e.event_id))return;
  const l=await labor(db,e.entity_id),emp=await employee(db,l.mnv);const a=await db.prepare("SELECT session_id,work_choice FROM attendance_sessions WHERE mnv=?1 AND business_date=?2").bind(l.mnv,l.business_date).first<{session_id:string;work_choice:string}>();if(!a)throw new Error(`REPLICA_ATTENDANCE_FOR_LABOR_MISSING:${l.mnv}`);
  await appendValues(sheetId,token,"CÔNG NHẬT","A:W",[[visibleDate(e.business_date),l.shift,l.mnv,emp.full_name,emp.phone,emp.supplier,emp.department,emp.site,emp.warehouse,emp.main_position,workLabel(a.work_choice),l.labor_type,visibleDateTime(l.start_at),"",l.time_marker,"Đang làm",l.note||"",e.actor_id,visibleDateTime(e.occurred_at),e.event_id,"",e.authority_seq,l.deduct_staff?"Có":"Không"]]);
  await appendHistory(sheetId,token,e,a.session_id,l.mnv,emp.full_name,l.shift,"Bắt đầu công nhật",`${l.labor_type} • Mốc ${l.time_marker} • Khấu trừ ${l.deduct_staff?"Có":"Không"}`);
}

async function replicateLaborFinishOperational(db:D1Database,sheetId:string,token:string,e:EventRow):Promise<void>{
  if(await operationalEventPresent(sheetId,token,"CÔNG NHẬT","U",e.event_id))return;
  const l=await labor(db,e.entity_id),emp=await employee(db,l.mnv);const ids=await getValues(sheetId,token,"CÔNG NHẬT","T2:T");const idx=ids.findIndex(r=>String(r[0]??"")===l.start_event_id);if(idx<0)throw new Error(`REPLICA_LABOR_START_ROW_MISSING:${l.start_event_id}`);const row=idx+2;
  const oldNote=String((await getValues(sheetId,token,"CÔNG NHẬT",`Q${row}:Q${row}`))[0]?.[0]??"");
  await putValues(sheetId,token,"CÔNG NHẬT",`N${row}:V${row}`,[[visibleDateTime(l.end_at||e.occurred_at),l.time_marker,"Hoàn thành",l.note||oldNote,e.actor_id,visibleDateTime(e.occurred_at),l.start_event_id,e.event_id,e.authority_seq]]);
  const a=await db.prepare("SELECT session_id FROM attendance_sessions WHERE mnv=?1 AND business_date=?2").bind(l.mnv,l.business_date).first<{session_id:string}>();
  await appendHistory(sheetId,token,e,a?.session_id||`${visibleDate(e.business_date)}|${l.mnv}`,l.mnv,emp.full_name,l.shift,"Hoàn thành công nhật",`${l.labor_type} • Mốc ${l.time_marker} • Khấu trừ ${l.deduct_staff?"Có":"Không"}`);
}

async function ensureOperationalSchema(env:Env,token:string):Promise<void>{const id=env.GOOGLE_SOURCE_SHEET_ID;await assertHeader(id,token,"RA - VÀO TRONG CA",RA_HEADERS);await assertHeader(id,token,"CÔNG NHẬT",LABOR_HEADERS);await assertHeader(id,token,"LỊCH SỬ NGHIỆP VỤ",HISTORY_HEADERS);}
async function replicateOperational(db:D1Database,env:Env,token:string,events:EventRow[]):Promise<number>{
  const a=await db.prepare("SELECT scope FROM authority_state WHERE singleton_id=1").first<{scope:string}>();if(a?.scope!=="PRODUCTION")return 0;await ensureOperationalSchema(env,token);let n=0;
  for(const e of events){
    if(["ATTENDANCE_ENTER","RESOURCE_CHANGE","ATTENDANCE_EXIT"].includes(e.event_type))await replicateAttendanceOperational(db,env.GOOGLE_SOURCE_SHEET_ID,token,e);
    else if(e.event_type==="LABOR_START")await replicateLaborStartOperational(db,env.GOOGLE_SOURCE_SHEET_ID,token,e);
    else if(e.event_type==="LABOR_FINISH")await replicateLaborFinishOperational(db,env.GOOGLE_SOURCE_SHEET_ID,token,e);
    else continue;n++;
  }
  return n;
}

function retryDelaySeconds(attempt:number):number{return Math.min(900,Math.max(5,Math.pow(2,Math.min(8,attempt))*5));}

export async function replicatePending(db:D1Database,env:Env,limit=50):Promise<{ok:boolean;processed:number;appended:number;operational:number;pending:number;checkpoint?:string;error?:string}>{
  const rows=await db.prepare("SELECT outbox_id,event_id,attempt_count FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY') AND next_attempt_at<=?1 ORDER BY outbox_id LIMIT ?2").bind(nowIso(),Math.max(1,Math.min(limit,100))).all<OutboxRow>();
  const due=rows.results??[];
  if(!due.length){const p=await db.prepare("SELECT COUNT(*) n FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')").first<{n:number}>();return{ok:true,processed:0,appended:0,operational:0,pending:p?.n??0};}
  const ids=due.map(x=>x.event_id),marks=ids.map(()=>"?").join(",");
  try{
    const claim=crypto.randomUUID(),at=nowIso();
    await db.batch(due.map(x=>db.prepare("UPDATE sheet_replication_outbox SET status='INFLIGHT',claim_token=?1,claimed_at=?2,attempt_count=attempt_count+1,last_error_class=NULL,last_error=NULL WHERE outbox_id=?3 AND status IN ('PENDING','RETRY')").bind(claim,at,x.outbox_id)));
    const token=await googleAccessToken(env);await ensureReplicaSheet(env,token);const present=await existingEventIds(env,token);
    const eventsResult=await db.prepare(`SELECT * FROM events WHERE event_id IN (${marks}) ORDER BY authority_epoch,authority_seq`).bind(...ids).all<EventRow>();
    const allEvents=eventsResult.results??[],technical=allEvents.filter(e=>!present.has(e.event_id));const checkpoint=await appendTechnicalRows(env,token,technical);const operational=await replicateOperational(db,env,token,allEvents);const doneAt=nowIso();
    await db.batch(due.map(x=>db.prepare("UPDATE sheet_replication_outbox SET status='SYNCED',claim_token=NULL,claimed_at=NULL,replicated_at=?1,google_checkpoint=?2,last_error_class=NULL,last_error=NULL WHERE outbox_id=?3").bind(doneAt,checkpoint,x.outbox_id)));
    const pending=await db.prepare("SELECT COUNT(*) n FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')").first<{n:number}>();
    await db.prepare("UPDATE replication_status SET target_identity=?1,state='HEALTHY',checkpoint=?2,pending_count=?3,last_attempt_at=?4,last_success_at=?4,last_error_class=NULL,last_error=NULL,updated_at=?4 WHERE singleton_id=1").bind(env.GOOGLE_STAGING_SHEET_ID,checkpoint,pending?.n??0,doneAt).run();
    return{ok:true,processed:due.length,appended:technical.length,operational,pending:pending?.n??0,checkpoint};
  }catch(e){
    const msg=String(e).slice(0,700),at=nowIso();
    await db.batch(due.map(x=>{const sec=retryDelaySeconds(x.attempt_count+1),next=new Date(Date.now()+sec*1000).toISOString();return db.prepare("UPDATE sheet_replication_outbox SET status='RETRY',claim_token=NULL,claimed_at=NULL,next_attempt_at=?1,last_error_class='TRANSIENT',last_error=?2 WHERE outbox_id=?3").bind(next,msg,x.outbox_id);}));
    const pending=await db.prepare("SELECT COUNT(*) n FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')").first<{n:number}>();
    await db.prepare("UPDATE replication_status SET state='DEGRADED',pending_count=?1,retry_count=retry_count+1,last_attempt_at=?2,last_error_class='TRANSIENT',last_error=?3,updated_at=?2 WHERE singleton_id=1").bind(pending?.n??0,at,msg).run();
    return{ok:false,processed:due.length,appended:0,operational:0,pending:pending?.n??0,error:msg};
  }
}

export async function replicationHealth(db:D1Database):Promise<Record<string,unknown>>{
  const row=await db.prepare("SELECT target_kind,target_identity,schema_version,state,checkpoint,pending_count,retry_count,last_attempt_at,last_success_at,last_error_class,last_error,updated_at FROM replication_status WHERE singleton_id=1").first<Record<string,unknown>>();
  const actual=await db.prepare("SELECT COUNT(*) n FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')").first<{n:number}>();
  return{...(row??{}),pending_count:actual?.n??0};
}
