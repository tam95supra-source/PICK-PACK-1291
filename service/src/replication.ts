import { REPLICA_HEADERS, type EventRow } from "./domain";
import { nowIso } from "./util";

interface OutboxRow { outbox_id:number; event_id:string; attempt_count:number; }
interface GoogleToken { access_token?:string; expires_in?:number; error?:string; }
interface EmployeeRow { mnv:string;full_name:string;phone:string;main_position:string;supplier:string;department:string;site:string;warehouse:string; }
interface AttendanceReplicaRow { session_id:string;mnv:string;business_date:string;shift:string;work_choice:string;pda_serial:string|null;user_pick:string|null;pack_table:string|null;user_pack:string|null; }
interface LaborReplicaRow { labor_id:string;mnv:string;business_date:string;shift:string;labor_type:string;time_marker:string;start_at:string;end_at:string|null;note:string;deduct_staff:number;start_event_id:string;finish_event_id:string|null; }
interface AttendanceOperationalRow extends AttendanceReplicaRow,EmployeeRow {}
interface LaborOperationalRow extends LaborReplicaRow,EmployeeRow { attendance_session_id:string|null;attendance_work_choice:string|null; }
interface OperationalIndex { raEvents:Set<string>;laborStartRows:Map<string,number>;laborFinishEvents:Set<string>;historyEvents:Set<string>; }

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
function appendRowNumber(updatedRange:string):number|null{const m=/!A(\d+):/i.exec(updatedRange);return m?.[1]?Number(m[1]):null;}

async function getValues(sheetId:string,token:string,sheet:string,range:string):Promise<unknown[][]>{
  const url=`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(sheetId)}/values/${encodeURIComponent(a1(sheet,range))}?valueRenderOption=FORMATTED_VALUE`;
  const r=await fetch(url,{headers:authHeaders(token)});if(!r.ok)throw new Error(`GOOGLE_READ:${sheet}:${r.status}`);const j=await r.json<{values?:unknown[][]}>();return j.values??[];
}
async function batchGetValues(sheetId:string,token:string,ranges:Array<[string,string]>):Promise<unknown[][][]>{
  const qs=ranges.map(([sheet,range])=>`ranges=${encodeURIComponent(a1(sheet,range))}`).join("&"),url=`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(sheetId)}/values:batchGet?valueRenderOption=FORMATTED_VALUE&${qs}`;
  const r=await fetch(url,{headers:authHeaders(token)});if(!r.ok)throw new Error(`GOOGLE_BATCH_READ:${r.status}`);const j=await r.json<{valueRanges?:Array<{values?:unknown[][]}>}>();return ranges.map((_,i)=>j.valueRanges?.[i]?.values??[]);
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
function assertHeaderValues(sheet:string,values:unknown[][],headers:readonly string[]):void{const got=(values[0]??[]).map(String);if(JSON.stringify(got)!==JSON.stringify([...headers]))throw new Error(`GOOGLE_OPERATIONAL_SCHEMA_DRIFT:${sheet}`);}

async function ensureReplicaSheet(env:Env,token:string):Promise<Set<string>>{
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
  const [header,ids]=await batchGetValues(id,token,[["__M1_SERVICE_REPLICA","A1:T1"],["__M1_SERVICE_REPLICA","A2:A"]]);
  if(JSON.stringify((header[0]??[]).map(String))!==JSON.stringify([...REPLICA_HEADERS]))await putValues(id,token,"__M1_SERVICE_REPLICA","A1:T1",[[...REPLICA_HEADERS]]);
  return new Set(ids.map(r=>String(r[0]??"")).filter(Boolean));
}

function eventValues(e:EventRow):unknown[]{return[e.event_id,e.event_type,e.entity_type,e.entity_id,e.business_date,e.authority_epoch,e.authority_seq,e.service_generation,e.base_version,e.new_version,e.actor_id,e.actor_role,e.device_id,e.occurred_at,e.committed_at,e.payload_json,e.idempotency_key,e.origin,e.schema_version,e.checksum];}
async function appendTechnicalRows(env:Env,token:string,events:EventRow[]):Promise<string>{return appendValues(env.GOOGLE_STAGING_SHEET_ID,token,"__M1_SERVICE_REPLICA","A:T",events.map(eventValues));}

async function loadOperationalIndex(env:Env,token:string):Promise<OperationalIndex>{
  const id=env.GOOGLE_SOURCE_SHEET_ID,ranges:Array<[string,string]>=[
    ["RA - VÀO TRONG CA","A1:V1"],["CÔNG NHẬT","A1:W1"],["LỊCH SỬ NGHIỆP VỤ","A1:M1"],
    ["RA - VÀO TRONG CA","T2:T"],["CÔNG NHẬT","T2:U"],["LỊCH SỬ NGHIỆP VỤ","K2:K"],
  ],v=await batchGetValues(id,token,ranges);
  assertHeaderValues("RA - VÀO TRONG CA",v[0]??[],RA_HEADERS);assertHeaderValues("CÔNG NHẬT",v[1]??[],LABOR_HEADERS);assertHeaderValues("LỊCH SỬ NGHIỆP VỤ",v[2]??[],HISTORY_HEADERS);
  const raEvents=new Set((v[3]??[]).map(r=>String(r[0]??"")).filter(Boolean)),laborStartRows=new Map<string,number>(),laborFinishEvents=new Set<string>();
  for(let i=0;i<(v[4]??[]).length;i++){const r=(v[4]??[])[i]??[],start=String(r[0]??""),finish=String(r[1]??"");if(start)laborStartRows.set(start,i+2);if(finish)laborFinishEvents.add(finish);}
  const historyEvents=new Set((v[5]??[]).map(r=>String(r[0]??"")).filter(Boolean));return{raEvents,laborStartRows,laborFinishEvents,historyEvents};
}

async function appendHistory(sheetId:string,token:string,index:OperationalIndex,e:EventRow,sessionId:string,mnv:string,name:string,shift:string,label:string,detail:string):Promise<void>{
  if(index.historyEvents.has(e.event_id))return;
  await appendValues(sheetId,token,"LỊCH SỬ NGHIỆP VỤ","A:M",[[visibleDate(e.business_date),sessionId,mnv,name,shift,e.event_type,label,visibleDateTime(e.occurred_at),e.actor_id,detail,e.event_id,"SERVICE_M2",e.authority_seq]]);index.historyEvents.add(e.event_id);
}

async function attendanceOperational(db:D1Database,entityId:string):Promise<AttendanceOperationalRow>{
  const r=await db.prepare(`SELECT s.session_id,s.mnv,s.business_date,s.shift,s.work_choice,s.pda_serial,s.user_pick,s.pack_table,s.user_pack,e.full_name,e.phone,e.main_position,e.supplier,e.department,e.site,e.warehouse
    FROM attendance_sessions s JOIN employees e ON e.mnv=s.mnv WHERE s.session_id=?1`).bind(entityId).first<AttendanceOperationalRow>();if(!r)throw new Error(`REPLICA_ATTENDANCE_MISSING:${entityId}`);return r;
}
async function laborOperational(db:D1Database,entityId:string):Promise<LaborOperationalRow>{
  const r=await db.prepare(`SELECT l.labor_id,l.mnv,l.business_date,l.shift,l.labor_type,l.time_marker,l.start_at,l.end_at,l.note,l.deduct_staff,l.start_event_id,l.finish_event_id,e.full_name,e.phone,e.main_position,e.supplier,e.department,e.site,e.warehouse,a.session_id AS attendance_session_id,a.work_choice AS attendance_work_choice
    FROM labor_sessions l JOIN employees e ON e.mnv=l.mnv LEFT JOIN attendance_sessions a ON a.mnv=l.mnv AND a.business_date=l.business_date WHERE l.labor_id=?1`).bind(entityId).first<LaborOperationalRow>();if(!r)throw new Error(`REPLICA_LABOR_MISSING:${entityId}`);return r;
}

async function replicateAttendanceOperational(db:D1Database,sheetId:string,token:string,index:OperationalIndex,e:EventRow):Promise<void>{
  if(index.raEvents.has(e.event_id))return;
  const s=await attendanceOperational(db,e.entity_id),p=payload(e);
  const labels:Record<string,[string,string]>={ATTENDANCE_ENTER:["Vào ca","ENTER"],RESOURCE_CHANGE:["Đổi tài nguyên","RESOURCE"],ATTENDANCE_EXIT:["Ra ca","EXIT"]};
  const [label,appAction]=labels[e.event_type]??[e.event_type,e.event_type];const note=ptext(p,"note")||"SERVICE M2";
  await appendValues(sheetId,token,"RA - VÀO TRONG CA","A:V",[[visibleDate(e.business_date),s.shift,s.mnv,s.full_name,s.phone,s.supplier,s.department,s.site,s.warehouse,s.main_position,workLabel(s.work_choice),s.pda_serial??"",s.user_pick??"",s.pack_table??"",s.user_pack??"",label,note,e.actor_id,visibleDateTime(e.occurred_at),e.event_id,appAction,e.authority_seq]]);index.raEvents.add(e.event_id);
  const detail=[workLabel(s.work_choice),s.pda_serial,s.user_pick,s.pack_table,s.user_pack].filter(Boolean).join(" • ");
  await appendHistory(sheetId,token,index,e,s.session_id,s.mnv,s.full_name,s.shift,label,detail);
}

async function replicateLaborStartOperational(db:D1Database,sheetId:string,token:string,index:OperationalIndex,e:EventRow):Promise<void>{
  if(index.laborStartRows.has(e.event_id))return;
  const l=await laborOperational(db,e.entity_id);if(!l.attendance_session_id)throw new Error(`REPLICA_ATTENDANCE_FOR_LABOR_MISSING:${l.mnv}`);
  const updated=await appendValues(sheetId,token,"CÔNG NHẬT","A:W",[[visibleDate(e.business_date),l.shift,l.mnv,l.full_name,l.phone,l.supplier,l.department,l.site,l.warehouse,l.main_position,workLabel(l.attendance_work_choice??""),l.labor_type,visibleDateTime(l.start_at),"",l.time_marker,"Đang làm",l.note||"",e.actor_id,visibleDateTime(e.occurred_at),e.event_id,"",e.authority_seq,l.deduct_staff?"Có":"Không"]]);
  const row=appendRowNumber(updated);if(row!==null)index.laborStartRows.set(e.event_id,row);
  await appendHistory(sheetId,token,index,e,l.attendance_session_id,l.mnv,l.full_name,l.shift,"Bắt đầu công nhật",`${l.labor_type} • Mốc ${l.time_marker} • Khấu trừ ${l.deduct_staff?"Có":"Không"}`);
}

async function replicateLaborFinishOperational(db:D1Database,sheetId:string,token:string,index:OperationalIndex,e:EventRow):Promise<void>{
  if(index.laborFinishEvents.has(e.event_id))return;
  const l=await laborOperational(db,e.entity_id),row=index.laborStartRows.get(l.start_event_id);if(!row)throw new Error(`REPLICA_LABOR_START_ROW_MISSING:${l.start_event_id}`);
  const oldNote=l.note||String((await getValues(sheetId,token,"CÔNG NHẬT",`Q${row}:Q${row}`))[0]?.[0]??"");
  await putValues(sheetId,token,"CÔNG NHẬT",`N${row}:V${row}`,[[visibleDateTime(l.end_at||e.occurred_at),l.time_marker,"Hoàn thành",oldNote,e.actor_id,visibleDateTime(e.occurred_at),l.start_event_id,e.event_id,e.authority_seq]]);index.laborFinishEvents.add(e.event_id);
  await appendHistory(sheetId,token,index,e,l.attendance_session_id||`${visibleDate(e.business_date)}|${l.mnv}`,l.mnv,l.full_name,l.shift,"Hoàn thành công nhật",`${l.labor_type} • Mốc ${l.time_marker} • Khấu trừ ${l.deduct_staff?"Có":"Không"}`);
}

async function replicateOperational(db:D1Database,env:Env,token:string,events:EventRow[]):Promise<number>{
  const a=await db.prepare("SELECT scope FROM authority_state WHERE singleton_id=1").first<{scope:string}>();if(a?.scope!=="PRODUCTION")return 0;const index=await loadOperationalIndex(env,token);let n=0;
  for(const e of events){
    if(["ATTENDANCE_ENTER","RESOURCE_CHANGE","ATTENDANCE_EXIT"].includes(e.event_type))await replicateAttendanceOperational(db,env.GOOGLE_SOURCE_SHEET_ID,token,index,e);
    else if(e.event_type==="LABOR_START")await replicateLaborStartOperational(db,env.GOOGLE_SOURCE_SHEET_ID,token,index,e);
    else if(e.event_type==="LABOR_FINISH")await replicateLaborFinishOperational(db,env.GOOGLE_SOURCE_SHEET_ID,token,index,e);
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
    const token=await googleAccessToken(env),present=await ensureReplicaSheet(env,token);
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
  const results=await db.batch([
    db.prepare("SELECT target_kind,target_identity,schema_version,state,checkpoint,pending_count,retry_count,last_attempt_at,last_success_at,last_error_class,last_error,updated_at FROM replication_status WHERE singleton_id=1"),
    db.prepare("SELECT COUNT(*) n FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')"),
  ]),row=(results[0]?.results?.[0]??{}) as Record<string,unknown>,actual=(results[1]?.results?.[0]??{}) as {n?:number};return{...row,pending_count:actual.n??0};
}
