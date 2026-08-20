#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'service/src/core.ts'
MOBILE=ROOT/'service/src/mobile_hotfix.ts'
MARK='S38_ATTENDANCE_RESOURCE_CONTRACT'


def replace_region(src:str,start_marker:str,end_marker:str,replacement:str)->str:
    a=src.find(start_marker)
    b=src.find(end_marker,a+len(start_marker))
    if a<0 or b<0:
        raise SystemExit(f'S38 region anchor missing: {start_marker} -> {end_marker}')
    return src[:a]+replacement.rstrip()+"\n\n"+src[b:]

core=CORE.read_text(encoding='utf-8')
if MARK not in core:
    iface='''  user_pack: string | null;\n  version: number;'''
    if iface not in core: raise SystemExit('S38 AttendanceRow anchor missing')
    core=core.replace(iface,'''  user_pack: string | null;\n  pda_enter_status: string | null;\n  pda_exit_status: string | null;\n  resource_note: string | null;\n  version: number;''',1)

    enter=r'''async function commitAttendanceEnter(db: D1Database, auth: AuthContext, req: CanonicalMutationRequest, a: AuthorityRow): Promise<EventRow> {
  // S38_ATTENDANCE_RESOURCE_CONTRACT: one session/day + audited duplicate-user override + PDA entry condition.
  const p=req.payload, mnv=text(p,"mnv",80), shift=text(p,"shift",80), choice=workChoice(p.work_choice);
  if(!mnv||!shift) throw new CoreError("ATTENDANCE_FIELDS_REQUIRED","VALIDATION",400);
  const pda=text(p,"pda_serial"), pick=text(p,"user_pick"), table=text(p,"pack_table"), pack=text(p,"user_pack");
  const pdaStatusAtEnter=text(p,"pda_status_at_enter",120);
  const duplicateUser=Boolean(p.duplicate_user);
  const resourceNote=duplicateUser?"TRÙNG USER":text(p,"resource_note",120);
  if(choice==="KHONG"&&(pda||pick||table||pack)) throw new CoreError("KHONG_RESOURCES_NOT_ALLOWED","VALIDATION",400);
  if(choice==="PICK"&&(!pda||table||pack)) throw new CoreError("PICK_RESOURCE_SELECTION_INVALID","VALIDATION",400);
  if(choice==="PACK"&&(!table||!pack||pda||pick)) throw new CoreError("PACK_RESOURCE_SELECTION_INVALID","VALIDATION",400);
  if(duplicateUser&&choice==="KHONG") throw new CoreError("DUPLICATE_USER_OVERRIDE_INVALID","VALIDATION",400);

  const checks=await db.batch([
    db.prepare("SELECT 1 AS x FROM employees WHERE mnv=?1").bind(mnv),
    db.prepare("SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,pda_enter_status,pda_exit_status,resource_note,version FROM attendance_sessions WHERE mnv=?1 AND business_date=?2").bind(mnv,req.business_date),
    db.prepare("SELECT available,status_label FROM resources WHERE resource_type='PDA' AND resource_id=?1").bind(pda),
    db.prepare("SELECT available FROM resources WHERE resource_type='USER_PICK' AND resource_id=?1").bind(pick),
    db.prepare("SELECT available FROM resources WHERE resource_type='PACK_TABLE' AND resource_id=?1").bind(table),
    db.prepare("SELECT available FROM resources WHERE resource_type='USER_PACK' AND resource_id=?1").bind(pack),
  ]);
  if(!(checks[0]?.results?.length)) throw new CoreError("EMPLOYEE_NOT_FOUND","VALIDATION",404);
  const current=(checks[1]?.results?.[0]??null) as AttendanceRow|null,currentVersion=current?.version??0;
  if(currentVersion!==req.base_version) throw new CoreError("STALE_BASE_VERSION","CONFLICT",409,false,{current_version:currentVersion});
  if(current?.state==="ACTIVE") throw new CoreError("ATTENDANCE_ALREADY_ACTIVE","CONFLICT",409,false,{session_id:current.session_id});
  if(current?.state==="ENDED") throw new CoreError("ATTENDANCE_ALREADY_ENDED","CONFLICT",409,false,{session_id:current.session_id});

  const pdaRow=(checks[2]?.results?.[0]??null) as {available?:number;status_label?:string}|null;
  if(pda&&!Boolean(pdaRow?.available)) throw new CoreError("PDA_UNAVAILABLE","RESOURCE",409);
  if(pda){
    if(!pdaStatusAtEnter) throw new CoreError("PDA_ENTRY_STATUS_REQUIRED","VALIDATION",400);
    if(String(pdaRow?.status_label||"").trim()!==pdaStatusAtEnter) throw new CoreError("PDA_ENTRY_STATUS_STALE","CONFLICT",409,false,{current_status:String(pdaRow?.status_label||"")});
  }
  if(pick&&!Boolean((checks[3]?.results?.[0] as {available?:number}|undefined)?.available)) throw new CoreError("USER_PICK_UNAVAILABLE","RESOURCE",409);
  if(table&&!Boolean((checks[4]?.results?.[0] as {available?:number}|undefined)?.available)) throw new CoreError("PACK_TABLE_UNAVAILABLE","RESOURCE",409);
  if(pack&&!Boolean((checks[5]?.results?.[0] as {available?:number}|undefined)?.available)) throw new CoreError("USER_PACK_UNAVAILABLE","RESOURCE",409);

  if(choice==="PACK"){
    const mapping=await db.prepare("SELECT 1 AS x FROM resource_pack_map WHERE pack_table=?1 AND shift=?2 AND user_pack=?3 AND available=1 LIMIT 1").bind(table,shift,pack).first<{x:number}>();
    if(!mapping) throw new CoreError("PACK_MAPPING_INVALID","RESOURCE",409);
  }

  if(duplicateUser){
    const t=choice==="PICK"?"USER_PICK":"USER_PACK",id=choice==="PICK"?pick:pack;
    if(!id) throw new CoreError("DUPLICATE_USER_OVERRIDE_INVALID","VALIDATION",400);
    const collision=await db.prepare(`SELECT 1 AS x FROM resource_leases WHERE business_date=?1 AND resource_type=?2 AND resource_id=?3 AND mnv<>?4
      UNION ALL SELECT 1 AS x FROM resource_daily_consumption WHERE business_date=?1 AND resource_type=?2 AND resource_id=?3 AND mnv<>?4 LIMIT 1`)
      .bind(req.business_date,t,id,mnv).first<{x:number}>();
    if(!collision) throw new CoreError("DUPLICATE_USER_OVERRIDE_NOT_REQUIRED","CONFLICT",409);
  }

  const event=await buildEvent(req,auth,a,currentVersion+1),sessionId=req.entity_id,stmts=eventStatements(db,event,a.authority_seq);
  stmts.push(db.prepare(`INSERT INTO attendance_sessions(session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,pda_enter_status,pda_exit_status,resource_note,enter_at,entered_by,version,updated_at)
    VALUES(?1,?2,?3,?4,?5,'ACTIVE',?6,?7,?8,?9,?10,NULL,?11,?12,?13,?14,?15)
    ON CONFLICT(mnv,business_date) DO UPDATE SET session_id=excluded.session_id,shift=excluded.shift,work_choice=excluded.work_choice,state='ACTIVE',pda_serial=excluded.pda_serial,user_pick=excluded.user_pick,pack_table=excluded.pack_table,user_pack=excluded.user_pack,pda_enter_status=excluded.pda_enter_status,pda_exit_status=NULL,resource_note=excluded.resource_note,enter_at=excluded.enter_at,entered_by=excluded.entered_by,version=excluded.version,updated_at=excluded.updated_at`)
    .bind(sessionId,mnv,req.business_date,shift,choice,pda||null,pick||null,table||null,pack||null,pdaStatusAtEnter||null,resourceNote||null,event.committed_at,auth.login_id,event.new_version,event.committed_at));
  const leased:Array<[string,string]>=[["PDA",pda],["PACK_TABLE",table]];
  if(!duplicateUser){leased.push(["USER_PICK",pick],["USER_PACK",pack]);}
  stmts.push(...leaseStatements(db,sessionId,mnv,req.business_date,event.event_id,event.committed_at,leased));
  try { await db.batch(stmts); } catch (e) {
    const msg=String(e);
    if(msg.includes("resource_leases")||msg.includes("resource_daily_consumption")||msg.includes("UNIQUE constraint")) throw new CoreError("EXCLUSIVE_RESOURCE_CONFLICT","RESOURCE",409,false);
    throw e;
  }
  return event;
}'''
    core=replace_region(core,'async function commitAttendanceEnter(','async function commitAttendanceExit(',enter)

    exit_fn=r'''async function commitAttendanceExit(db:D1Database, auth:AuthContext, req:CanonicalMutationRequest, a:AuthorityRow):Promise<EventRow>{
  // S38: a PICK session cannot exit until the operator confirms the same PDA condition recorded at entry.
  const p=req.payload,mnv=text(p,"mnv",80),pdaExitStatus=text(p,"pda_exit_status",120);
  const checks=await db.batch([
    db.prepare("SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,pda_enter_status,pda_exit_status,resource_note,version FROM attendance_sessions WHERE mnv=?1 AND business_date=?2").bind(mnv,req.business_date),
    db.prepare("SELECT COUNT(*) AS n FROM labor_sessions WHERE mnv=?1 AND business_date=?2 AND state='OPEN'").bind(mnv,req.business_date),
  ]);
  const current=(checks[0]?.results?.[0]??null) as AttendanceRow|null;
  if(!current||current.state!=="ACTIVE") throw new CoreError("ATTENDANCE_NOT_ACTIVE","CONFLICT",409);
  if(current.version!==req.base_version) throw new CoreError("STALE_BASE_VERSION","CONFLICT",409,false,{current_version:current.version});
  const open=(checks[1]?.results?.[0]??null) as {n?:number}|null;if((open?.n??0)>0) throw new CoreError("OPEN_LABOR_BLOCKS_EXIT","CONFLICT",409);
  if(current.pda_serial){
    const initial=String(current.pda_enter_status||"").trim();
    if(!initial) throw new CoreError("PDA_ENTRY_STATUS_MISSING_NOTIFY_SPECIALIST","INTEGRITY",409,false,{pda_serial:current.pda_serial});
    if(!pdaExitStatus) throw new CoreError("PDA_EXIT_STATUS_REQUIRED","VALIDATION",400,{pda_serial:current.pda_serial,initial_status:initial});
    if(pdaExitStatus!==initial) throw new CoreError("PDA_STATUS_MISMATCH_NOTIFY_SPECIALIST","CONFLICT",409,false,{pda_serial:current.pda_serial,initial_status:initial,current_status:pdaExitStatus});
  }
  const event=await buildEvent(req,auth,a,current.version+1),stmts=eventStatements(db,event,a.authority_seq);
  stmts.push(db.prepare("UPDATE attendance_sessions SET state='ENDED',pda_exit_status=?1,exit_at=?2,exited_by=?3,version=?4,updated_at=?2 WHERE session_id=?5 AND version=?6 AND state='ACTIVE'").bind(pdaExitStatus||null,event.committed_at,auth.login_id,event.new_version,current.session_id,current.version));
  stmts.push(db.prepare("DELETE FROM resource_leases WHERE session_id=?1").bind(current.session_id));
  await db.batch(stmts); return event;
}'''
    core=replace_region(core,'async function commitAttendanceExit(','async function commitResourceChange(',exit_fn)
    CORE.write_text(core,encoding='utf-8')

mobile=MOBILE.read_text(encoding='utf-8')
if MARK not in mobile:
    options=r'''async function resourceOptions(db:D1Database,date:string,mnv:string):Promise<Record<string,unknown>>{
  // S38_ATTENDANCE_RESOURCE_CONTRACT: normal lists hide busy/used users; explicit reissue lists preserve an audited duplicate path.
  const leaseRows=(await db.prepare("SELECT resource_type,resource_id,mnv FROM resource_leases WHERE business_date=?1").bind(date).all<{resource_type:string;resource_id:string;mnv:string}>()).results??[];
  const busy=new Set(leaseRows.filter(x=>x.mnv!==mnv).map(x=>`${x.resource_type}|${x.resource_id}`));
  const activeRows=(await db.prepare("SELECT mnv,user_pick,user_pack FROM attendance_sessions WHERE business_date=?1 AND state='ACTIVE'").bind(date).all<{mnv:string;user_pick:string|null;user_pack:string|null}>()).results??[];
  for(const x of activeRows){if(x.mnv===mnv)continue;if(x.user_pick)busy.add(`USER_PICK|${x.user_pick}`);if(x.user_pack)busy.add(`USER_PACK|${x.user_pack}`);}
  const usedRows=(await db.prepare("SELECT resource_type,resource_id,mnv FROM resource_daily_consumption WHERE business_date=?1").bind(date).all<{resource_type:string;resource_id:string;mnv:string}>()).results??[];
  const used=new Set(usedRows.filter(x=>x.mnv!==mnv).map(x=>`${x.resource_type}|${x.resource_id}`));
  const current=await db.prepare("SELECT pda_serial,user_pick,pack_table,user_pack,pda_enter_status,resource_note FROM attendance_sessions WHERE business_date=?1 AND mnv=?2 AND state='ACTIVE'").bind(date,mnv).first<{pda_serial:string|null;user_pick:string|null;pack_table:string|null;user_pack:string|null;pda_enter_status:string|null;resource_note:string|null}>();

  const pdasRaw=(await db.prepare("SELECT resource_id,status_label,metadata_json FROM resources WHERE resource_type='PDA' AND available=1 ORDER BY resource_id").all<{resource_id:string;status_label:string;metadata_json:string}>()).results??[];
  const pdas=pdasRaw.filter(x=>!busy.has(`PDA|${x.resource_id}`)||x.resource_id===current?.pda_serial).map(x=>{let m:Record<string,unknown>={};try{m=JSON.parse(x.metadata_json) as Record<string,unknown>;}catch{}return{serial:x.resource_id,last5:String(m["5 số cuối Seri"]||x.resource_id.slice(-5)),status:x.status_label};});
  const pdaStatusRows=(await db.prepare("SELECT DISTINCT status_label FROM resources WHERE resource_type='PDA' AND TRIM(status_label)<>'' ORDER BY status_label").all<{status_label:string}>()).results??[];
  const pda_statuses=pdaStatusRows.map(x=>x.status_label).filter(Boolean);

  const picksRaw=(await db.prepare("SELECT resource_id FROM resources WHERE resource_type='USER_PICK' AND available=1 ORDER BY resource_id").all<{resource_id:string}>()).results??[];
  const user_picks=picksRaw.map(x=>x.resource_id).filter(id=>(!busy.has(`USER_PICK|${id}`)&&!used.has(`USER_PICK|${id}`))||id===current?.user_pick);
  const user_picks_reissue=picksRaw.map(x=>x.resource_id).filter(id=>id!==current?.user_pick&&(busy.has(`USER_PICK|${id}`)||used.has(`USER_PICK|${id}`))).map(id=>({id,busy:busy.has(`USER_PICK|${id}`),used_today:used.has(`USER_PICK|${id}`),duplicate_user:true,note:"TRÙNG USER"}));

  const packsRaw=(await db.prepare("SELECT pack_table,shift,user_pack FROM resource_pack_map WHERE available=1 ORDER BY pack_table,shift,user_pack").all<{pack_table:string;shift:string;user_pack:string}>()).results??[];
  const pack_tables=packsRaw.filter(x=>((!busy.has(`PACK_TABLE|${x.pack_table}`)&&!busy.has(`USER_PACK|${x.user_pack}`)&&!used.has(`USER_PACK|${x.user_pack}`))||(x.pack_table===current?.pack_table&&x.user_pack===current?.user_pack))).map(x=>({table:x.pack_table,shift:x.shift,user_pack:x.user_pack,duplicate_user:false}));
  const pack_tables_reissue=packsRaw.filter(x=>!busy.has(`PACK_TABLE|${x.pack_table}`)&&!(x.pack_table===current?.pack_table&&x.user_pack===current?.user_pack)&&(busy.has(`USER_PACK|${x.user_pack}`)||used.has(`USER_PACK|${x.user_pack}`))).map(x=>({table:x.pack_table,shift:x.shift,user_pack:x.user_pack,duplicate_user:true,note:"TRÙNG USER"}));
  return{ok:true,business_date:date,pdas,pda_statuses,user_picks,user_picks_reissue,pack_tables,pack_tables_reissue,current};
}'''
    mobile=replace_region(mobile,'async function resourceOptions(','async function employeeContext(',options)
    old='''  const session=await env.DB.prepare("SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,enter_at,exit_at,entered_by,exited_by,version FROM attendance_sessions WHERE business_date=?1 AND mnv=?2").bind(date,mnv).first<Record<string,unknown>>();'''
    new='''  const session=await env.DB.prepare("SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,pda_enter_status,pda_exit_status,resource_note,enter_at,exit_at,entered_by,exited_by,version FROM attendance_sessions WHERE business_date=?1 AND mnv=?2").bind(date,mnv).first<Record<string,unknown>>();'''
    if old not in mobile: raise SystemExit('S38 employee session query anchor missing')
    mobile=mobile.replace(old,new,1)
    old2='''  const options=body.include_options===true&&state==="NOT_ENTERED"?await resourceOptions(env.DB,date,mnv):null;'''
    new2='''  const options=body.include_options===true?await resourceOptions(env.DB,date,mnv):null;'''
    if old2 not in mobile: raise SystemExit('S38 employee options anchor missing')
    mobile=mobile.replace(old2,new2,1)
    MOBILE.write_text(mobile,encoding='utf-8')

c=CORE.read_text(encoding='utf-8');m=MOBILE.read_text(encoding='utf-8')
for x in [MARK,'pda_enter_status','pda_exit_status','PDA_STATUS_MISMATCH_NOTIFY_SPECIALIST','DUPLICATE_USER_OVERRIDE_NOT_REQUIRED','PACK_MAPPING_INVALID']:
    if x not in c: raise SystemExit('S38 core contract missing: '+x)
for x in [MARK,'user_picks_reissue','pack_tables_reissue','pda_statuses','duplicate_user:true','include_options===true?await resourceOptions']:
    if x not in m: raise SystemExit('S38 mobile contract missing: '+x)
print('Applied S38 attendance/resource service contract')
