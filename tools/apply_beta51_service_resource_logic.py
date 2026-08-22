#!/usr/bin/env python3
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'service/src/core.ts'; MOBILE=ROOT/'service/src/mobile_hotfix.ts'; SESSION=ROOT/'service/src/session_hotfix.ts'

# mobile resource options: active lease = hard lock; used-today = explicit reissue; pack mapping is cross-shift.
p=MOBILE.read_text(encoding='utf-8')
new_mobile=r'''async function resourceOptions(db:D1Database,date:string,mnv:string):Promise<Record<string,unknown>>{
  const leaseRows=(await db.prepare("SELECT resource_type,resource_id,mnv FROM resource_leases WHERE business_date=?1").bind(date).all<{resource_type:string;resource_id:string;mnv:string}>()).results??[];
  const busy=new Set(leaseRows.map(x=>`${x.resource_type}|${x.resource_id}`));
  const usedRows=(await db.prepare("SELECT resource_type,resource_id,mnv FROM resource_daily_consumption WHERE business_date=?1").bind(date).all<{resource_type:string;resource_id:string;mnv:string}>()).results??[];
  const used=new Set(usedRows.map(x=>`${x.resource_type}|${x.resource_id}`));
  const current=await db.prepare("SELECT pda_serial,user_pick,pack_table,user_pack FROM attendance_sessions WHERE business_date=?1 AND mnv=?2 AND state='ACTIVE'").bind(date,mnv).first<{pda_serial:string|null;user_pick:string|null;pack_table:string|null;user_pack:string|null}>();

  const pdasRaw=(await db.prepare("SELECT resource_id,status_label,metadata_json FROM resources WHERE resource_type='PDA' AND available=1 ORDER BY resource_id").all<{resource_id:string;status_label:string;metadata_json:string}>()).results??[];
  const pdas=pdasRaw.filter(x=>!busy.has(`PDA|${x.resource_id}`)||x.resource_id===current?.pda_serial).map(x=>{let m:Record<string,unknown>={};try{m=JSON.parse(x.metadata_json) as Record<string,unknown>;}catch{}return{serial:x.resource_id,last5:String(m["5 số cuối Seri"]||x.resource_id.slice(-5)),status:x.status_label};});

  const picksRaw=(await db.prepare("SELECT resource_id FROM resources WHERE resource_type='USER_PICK' AND available=1 ORDER BY resource_id").all<{resource_id:string}>()).results??[];
  const user_picks:string[]=[],user_picks_reissue:Array<Record<string,unknown>>=[];
  for(const x of picksRaw){const id=x.resource_id,isCurrent=id===current?.user_pick,isBusy=busy.has(`USER_PICK|${id}`),isUsed=used.has(`USER_PICK|${id}`);if(isCurrent||(!isBusy&&!isUsed))user_picks.push(id);else if(!isBusy&&isUsed)user_picks_reissue.push({id,busy:false,used_today:true,duplicate_user:true,note:"PHÁT LẠI USER"});}

  const packsRaw=(await db.prepare("SELECT pack_table,shift,user_pack FROM resource_pack_map WHERE available=1 ORDER BY pack_table,shift,user_pack").all<{pack_table:string;shift:string;user_pack:string}>()).results??[];
  const pack_tables:Array<Record<string,unknown>>=[],pack_tables_reissue:Array<Record<string,unknown>>=[];
  for(const x of packsRaw){
    const exactCurrent=x.pack_table===current?.pack_table&&x.user_pack===current?.user_pack;
    const tableBusy=busy.has(`PACK_TABLE|${x.pack_table}`),userBusy=busy.has(`USER_PACK|${x.user_pack}`),userUsed=used.has(`USER_PACK|${x.user_pack}`);
    if(exactCurrent||(!tableBusy&&!userBusy&&!userUsed))pack_tables.push({table:x.pack_table,shift:x.shift,user_pack:x.user_pack,duplicate_user:false});
    else if(!tableBusy&&!userBusy&&userUsed)pack_tables_reissue.push({table:x.pack_table,shift:x.shift,user_pack:x.user_pack,duplicate_user:true,used_today:true,note:"PHÁT LẠI USER"});
  }
  return{ok:true,business_date:date,pdas,user_picks,user_picks_reissue,pack_tables,pack_tables_reissue,current};
}'''
p,n=re.subn(r'async function resourceOptions\(db:D1Database,date:string,mnv:string\):Promise<Record<string,unknown>>\{.*?\n\}',new_mobile,p,count=1,flags=re.S)
if n!=1: raise SystemExit(f'MOBILE_RESOURCE_OPTIONS_REPLACE={n}')
MOBILE.write_text(p,encoding='utf-8')

# core: replace lease helper with explicit replay mode + add daily-use guard.
p=CORE.read_text(encoding='utf-8')
old=re.search(r'function leaseStatements\(db: D1Database, sessionId: string, mnv: string, date: string, eventId: string, at: string, resources: Array<\[string,string\]>\): D1PreparedStatement\[\] \{.*?\n\}',p,re.S)
if not old: raise SystemExit('LEASE_HELPER_NOT_FOUND')
new=r'''function leaseStatements(db: D1Database, sessionId: string, mnv: string, date: string, eventId: string, at: string, resources: Array<[string,string]>, allowDailyReplay=false): D1PreparedStatement[] {
  const out: D1PreparedStatement[] = [];
  for (const [type,id] of resources) {
    if (!id) continue;
    out.push(db.prepare("INSERT INTO resource_leases(resource_type,resource_id,session_id,mnv,business_date,acquired_event_id,acquired_at) VALUES(?1,?2,?3,?4,?5,?6,?7)").bind(type,id,sessionId,mnv,date,eventId,at));
    if (type === "USER_PICK" || type === "USER_PACK") {
      const sql=allowDailyReplay
        ?"INSERT OR IGNORE INTO resource_daily_consumption(business_date,resource_type,resource_id,mnv,first_event_id) VALUES(?1,?2,?3,?4,?5)"
        :"INSERT INTO resource_daily_consumption(business_date,resource_type,resource_id,mnv,first_event_id) VALUES(?1,?2,?3,?4,?5)";
      out.push(db.prepare(sql).bind(date,type,id,mnv,eventId));
    }
  }
  return out;
}

async function ensureDailyUserReuseAllowed(db:D1Database,date:string,pick:string,pack:string,duplicateUser:boolean,currentPick="",currentPack=""):Promise<void>{
  for(const [type,id,current] of [["USER_PICK",pick,currentPick],["USER_PACK",pack,currentPack]] as Array<[string,string,string]>){
    if(!id||id===current)continue;
    const prior=await db.prepare("SELECT 1 x FROM resource_daily_consumption WHERE business_date=?1 AND resource_type=?2 AND resource_id=?3").bind(date,type,id).first();
    if(prior&&!duplicateUser)throw new CoreError(type==="USER_PICK"?"USER_PICK_ALREADY_USED_TODAY":"USER_PACK_ALREADY_USED_TODAY","RESOURCE",409,false);
  }
}

async function ensurePackPairAllowed(db:D1Database,table:string,pack:string):Promise<void>{
  if(!table&&!pack)return;
  if(!table||!pack)throw new CoreError("PACK_RESOURCES_REQUIRED","VALIDATION",400);
  const row=await db.prepare("SELECT 1 x FROM resource_pack_map WHERE pack_table=?1 AND user_pack=?2 AND available=1 LIMIT 1").bind(table,pack).first();
  if(!row)throw new CoreError("PACK_MAPPING_INVALID","RESOURCE",409,false);
}'''
p=p[:old.start()]+new+p[old.end():]
# Enter: insert guards before event and allow replay SQL only when explicit.
anchor='  if(choice==="PACK"&&(!table||!pack)) throw new CoreError("PACK_RESOURCES_REQUIRED","VALIDATION",400);\n  const event=await buildEvent(req,auth,a,currentVersion+1);'
rep='  if(choice==="PACK"&&(!table||!pack)) throw new CoreError("PACK_RESOURCES_REQUIRED","VALIDATION",400);\n  const duplicateUser=Boolean(p.duplicate_user);\n  await ensurePackPairAllowed(db,table,pack);\n  await ensureDailyUserReuseAllowed(db,req.business_date,pick,pack,duplicateUser);\n  const event=await buildEvent(req,auth,a,currentVersion+1);'
if anchor not in p: raise SystemExit('ENTER_GUARD_ANCHOR_MISSING')
p=p.replace(anchor,rep,1)
oldcall='stmts.push(...leaseStatements(db,sessionId,mnv,req.business_date,event.event_id,event.committed_at,[["PDA",pda],["USER_PICK",pick],["PACK_TABLE",table],["USER_PACK",pack]]));'
newcall='stmts.push(...leaseStatements(db,sessionId,mnv,req.business_date,event.event_id,event.committed_at,[["PDA",pda],["USER_PICK",pick],["PACK_TABLE",table],["USER_PACK",pack]],duplicateUser));'
if oldcall not in p: raise SystemExit('ENTER_LEASE_CALL_MISSING')
p=p.replace(oldcall,newcall,1)
# Resource change: explicit validation before event, using current resource exemptions.
anchor='  const pda=text(p,"pda_serial")||current.pda_serial||"",pick=text(p,"user_pick")||"",table=text(p,"pack_table")||"",pack=text(p,"user_pack")||"";\n  const event=await buildEvent(req,auth,a,current.version+1),stmts=eventStatements(db,event,a.authority_seq);'
rep='  const pda=text(p,"pda_serial")||current.pda_serial||"",pick=text(p,"user_pick")||"",table=text(p,"pack_table")||"",pack=text(p,"user_pack")||"";\n  const duplicateUser=Boolean(p.duplicate_user);\n  await ensurePackPairAllowed(db,table,pack);\n  await ensureDailyUserReuseAllowed(db,req.business_date,pick,pack,duplicateUser,current.user_pick||"",current.user_pack||"");\n  const event=await buildEvent(req,auth,a,current.version+1),stmts=eventStatements(db,event,a.authority_seq);'
if anchor not in p: raise SystemExit('CHANGE_GUARD_ANCHOR_MISSING')
p=p.replace(anchor,rep,1)
oldcall='stmts.push(...leaseStatements(db,current.session_id,current.mnv,req.business_date,event.event_id,event.committed_at,[["PDA",pda],["USER_PICK",pick],["PACK_TABLE",table],["USER_PACK",pack]]));'
newcall='stmts.push(...leaseStatements(db,current.session_id,current.mnv,req.business_date,event.event_id,event.committed_at,[["PDA",pda],["USER_PICK",pick],["PACK_TABLE",table],["USER_PACK",pack]],duplicateUser));'
if oldcall not in p: raise SystemExit('CHANGE_LEASE_CALL_MISSING')
p=p.replace(oldcall,newcall,1)
CORE.write_text(p,encoding='utf-8')

# session editor hotfix: remove shift from pack map validation, explicitly gate used-today reissue, retain live-lease hard lock.
p=SESSION.read_text(encoding='utf-8')
old='if(table&&pack){const m=await env.DB.prepare("SELECT 1 x FROM resource_pack_map WHERE pack_table=?1 AND user_pack=?2 AND shift=?3 AND available=1").bind(table,pack,s.shift).first();if(!m)return apiError("PACK_MAPPING_INVALID","RESOURCE",409);}'
new='if(table&&pack){const m=await env.DB.prepare("SELECT 1 x FROM resource_pack_map WHERE pack_table=?1 AND user_pack=?2 AND available=1 LIMIT 1").bind(table,pack).first();if(!m)return apiError("PACK_MAPPING_INVALID","RESOURCE",409);}'
if old not in p: raise SystemExit('SESSION_PACK_MAPPING_ANCHOR_MISSING')
p=p.replace(old,new,1)
anchor='  if(Boolean(table)!==Boolean(pack))return apiError("PACK_TABLE_USER_REQUIRED_TOGETHER","VALIDATION",400);\n  try{await validateResource(env,"PDA",pda,s.session_id);await validateResource(env,"USER_PICK",pick,s.session_id);await validateResource(env,"PACK_TABLE",table,s.session_id);await validateResource(env,"USER_PACK",pack,s.session_id);}catch(e){return apiError(String(e).replace(/^Error: /,""),"RESOURCE",409);}'
rep='  if(Boolean(table)!==Boolean(pack))return apiError("PACK_TABLE_USER_REQUIRED_TOGETHER","VALIDATION",400);\n  const duplicateUser=Boolean(b.duplicate_user);\n  try{await validateResource(env,"PDA",pda,s.session_id);await validateResource(env,"USER_PICK",pick,s.session_id);await validateResource(env,"PACK_TABLE",table,s.session_id);await validateResource(env,"USER_PACK",pack,s.session_id);}catch(e){return apiError(String(e).replace(/^Error: /,""),"RESOURCE",409);}\n  for(const [t,r,current] of [["USER_PICK",pick,text(s.user_pick)],["USER_PACK",pack,text(s.user_pack)]] as Array<[string,string,string]>){if(!r||r===current)continue;const used=await env.DB.prepare("SELECT 1 x FROM resource_daily_consumption WHERE business_date=?1 AND resource_type=?2 AND resource_id=?3").bind(s.business_date,t,r).first();if(used&&!duplicateUser)return apiError(t==="USER_PICK"?"USER_PICK_ALREADY_USED_TODAY":"USER_PACK_ALREADY_USED_TODAY","RESOURCE",409);}'
if anchor not in p: raise SystemExit('SESSION_DAILY_GUARD_ANCHOR_MISSING')
p=p.replace(anchor,rep,1)
# event payload keeps explicit replay intent
old='resource_note:note,before:{work_choice:s.work_choice'
new='resource_note:note,duplicate_user:duplicateUser,before:{work_choice:s.work_choice'
if old not in p: raise SystemExit('SESSION_EVENT_DUPLICATE_ANCHOR_MISSING')
p=p.replace(old,new,1)
SESSION.write_text(p,encoding='utf-8')

# Contract assertions
checks={
 'mobile_reissue':'user_picks_reissue,pack_tables,pack_tables_reissue,current' in MOBILE.read_text(encoding='utf-8'),
 'cross_shift_mobile':'x.shift===' not in new_mobile,
 'cross_shift_session':'user_pack=?2 AND shift=?3' not in SESSION.read_text(encoding='utf-8'),
 'core_explicit_reissue':'ensureDailyUserReuseAllowed' in CORE.read_text(encoding='utf-8') and 'allowDailyReplay' in CORE.read_text(encoding='utf-8'),
 'active_lock_kept':'INSERT INTO resource_leases' in CORE.read_text(encoding='utf-8') and 'validateResource(env,"USER_PACK"' in SESSION.read_text(encoding='utf-8'),
}
if not all(checks.values()): raise SystemExit('CONTRACT_FAIL:'+str(checks))
print('BETA51_SERVICE_RESOURCE_PATCH=PASS',checks)
