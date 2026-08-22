#!/usr/bin/env python3
from pathlib import Path


def replace_block(text: str, start: str, end: str, replacement: str) -> str:
    a = text.find(start)
    if a < 0:
        raise SystemExit(f"S56 missing start anchor: {start}")
    b = text.find(end, a)
    if b < 0:
        raise SystemExit(f"S56 missing end anchor: {end}")
    return text[:a] + replacement.rstrip() + "\n\n" + text[b:]

rep = Path("service/src/replication.ts")
s = rep.read_text()

user_fn = r'''// S56_BETA49_EVENT_USER_PROJECTION_V1
async function replicateUserAssignments(_db:D1Database,sheetId:string,token:string,index:OperationalIndex,e:EventRow,s:AttendanceOperationalRow):Promise<number>{
  if(e.event_type==="ATTENDANCE_EXIT")return 0;
  const p=payload(e),after=pobj(p,"after"),src=Object.keys(after).length?after:p;
  const assignments:Array<["PICK"|"PACK",string]>=[["PICK",ptext(src,"user_pick")],["PACK",ptext(src,"user_pack")]];
  let n=0;
  for(const [pos,user] of assignments){
    if(!user)continue;
    const key=`${e.event_id}:${pos}`;
    if(index.userEvents.has(key))continue;
    await appendValues(sheetId,token,"THÔNG TIN USER CỦA NLĐ","A:K",[[visibleDate(e.business_date),s.shift,s.mnv,s.full_name,s.supplier,s.department,s.site,pos,user,e.actor_id,key]]);
    index.userEvents.add(key);n++;
  }
  return n;
}'''
s = replace_block(s, "async function replicateUserAssignments", "function resourceChangeDetail", user_fn)

summary_fn = r'''// S56_BETA49_RA_RESOURCE_AGGREGATE_V1
async function attendanceResourceSummary(db:D1Database,e:EventRow,s:AttendanceOperationalRow):Promise<{pda:string;pick:string;table:string;pack:string}>{
  const r=await db.prepare("SELECT payload_json FROM events WHERE entity_id=?1 AND event_type IN ('ATTENDANCE_ENTER','RESOURCE_CHANGE','ATTENDANCE_EXIT') ORDER BY authority_epoch,authority_seq").bind(e.entity_id).all<{payload_json:string}>();
  const pdas:string[]=[],picks:string[]=[],tables:string[]=[],packs:string[]=[];
  const add=(a:string[],v:string)=>{v=String(v||"").trim();if(v&&!a.includes(v))a.push(v);};
  for(const row of r.results??[]){
    let p:Record<string,unknown>={};try{p=JSON.parse(row.payload_json) as Record<string,unknown>;}catch{}
    const after=pobj(p,"after"),src=Object.keys(after).length?after:p;
    add(pdas,ptext(src,"pda_serial"));add(picks,ptext(src,"user_pick"));add(tables,ptext(src,"pack_table"));add(packs,ptext(src,"user_pack"));
  }
  add(pdas,s.pda_serial||"");add(picks,s.user_pick||"");add(tables,s.pack_table||"");add(packs,s.user_pack||"");
  return{pda:pdas.join(", "),pick:picks.join(", "),table:tables.join(", "),pack:packs.join(", ")};
}

async function replicateAttendanceEvent(db:D1Database,sheetId:string,token:string,index:OperationalIndex,e:EventRow):Promise<void>{
  const s=await attendanceOperational(db,e.entity_id);await replicateUserAssignments(db,sheetId,token,index,e,s);
  if(e.event_type==="RESOURCE_CHANGE"){await appendHistory(sheetId,token,index,e,s.session_id,s.mnv,s.full_name,s.shift,"Cập nhật công việc / tài nguyên",resourceChangeDetail(e));return;}
  if(index.raEvents.has(e.event_id))return;
  const enter=e.event_type==="ATTENDANCE_ENTER",action=enter?"VÀO":"RA",appAction=enter?"ENTER":"EXIT",resources=await attendanceResourceSummary(db,e,s);
  await appendValues(sheetId,token,"RA - VÀO TRONG CA","A:V",[[visibleDate(e.business_date),s.shift,s.mnv,s.full_name,s.phone,s.supplier,s.department,s.site,s.warehouse,s.main_position,workLabel(s.work_choice),resources.pda,resources.pick,resources.table,resources.pack,action,"",e.actor_id,visibleDateTime(e.occurred_at),e.event_id,appAction,e.authority_seq]]);index.raEvents.add(e.event_id);
  await appendHistory(sheetId,token,index,e,s.session_id,s.mnv,s.full_name,s.shift,enter?"Vào ca":"Ra ca",`${enter?"Bắt đầu":"Kết thúc"} phiên • Vị trí chính: ${s.main_position||"—"}`);
}'''
s = replace_block(s, "async function replicateAttendanceEvent", "async function replicateLaborStartOperational", summary_fn)

old_early = '''  if(!due.length){const p=await db.prepare("SELECT COUNT(*) n FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')").first<{n:number}>();return{ok:true,processed:0,appended:0,operational:0,pending:p?.n??0};}'''
new_early = '''  if(!due.length){
    const p=await db.prepare("SELECT COUNT(*) n FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')").first<{n:number}>(),n=p?.n??0,at=nowIso();
    await db.prepare("UPDATE replication_status SET pending_count=?1,updated_at=?2 WHERE singleton_id=1").bind(n,at).run();
    return{ok:true,processed:0,appended:0,operational:0,pending:n};
  }'''
if old_early not in s:
    raise SystemExit("S56 replication early-return anchor missing")
s = s.replace(old_early, new_early, 1)
rep.write_text(s)

idx = Path("service/src/index.ts")
t = idx.read_text()
old_sched = '''  async scheduled(_controller:ScheduledController,env:Env,ctx:ExecutionContext):Promise<void>{ctx.waitUntil(Promise.all([replicatePending(env.DB,env),flushPushOutbox(env.DB,env)]).then(()=>undefined).catch(e=>console.log(JSON.stringify({level:"error",kind:"scheduled_background_failed",error:String(e).slice(0,240)}))));},'''
new_sched = '''  // S56_BETA49_AWAIT_CANONICAL_REPLICATION_V1: do not detach the canonical Sheet projection from the cron lifetime.\n  async scheduled(_controller:ScheduledController,env:Env,_ctx:ExecutionContext):Promise<void>{\n    try{await Promise.all([replicatePending(env.DB,env),flushPushOutbox(env.DB,env)]);}\n    catch(e){console.log(JSON.stringify({level:"error",kind:"scheduled_canonical_failed",error:String(e).slice(0,240)}));}\n  },'''
if old_sched not in t:
    raise SystemExit("S56 scheduler anchor missing")
t = t.replace(old_sched, new_sched, 1)
idx.write_text(t)

print("S56 Beta49 Service field fixes materialized")
