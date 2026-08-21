#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
IDX=ROOT/'service/src/index.ts'
COR=ROOT/'service/src/correction.ts'
MR=ROOT/'service/src/master_replication.ts'
REP=ROOT/'service/src/replication.ts'
MARK='S33_OWNER_RESOURCE_HISTORY'

s=IDX.read_text(encoding='utf-8')
if MARK not in s:
    anchor='import { historicalCorrection } from "./correction";'
    if anchor not in s: raise SystemExit('S33 index import anchor missing')
    s=s.replace(anchor,anchor+'\nimport { resourceAdminList, resourceAdminMutate } from "./resource_admin"; // '+MARK,1)
    route='  if(p==="/v1/corrections"&&method==="POST")return historicalCorrection(request,env);'
    if route not in s: raise SystemExit('S33 correction route anchor missing')
    s=s.replace(route,route+'\n  if(p==="/v1/admin/resources"&&method==="GET")return resourceAdminList(request,env);\n  if(p==="/v1/admin/resources"&&method==="POST")return resourceAdminMutate(request,env);',1)
    IDX.write_text(s,encoding='utf-8')

s=COR.read_text(encoding='utf-8')
if MARK not in s:
    old='  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);if(auth.role!=="SUPERADMIN")return apiError("SUPERADMIN_REQUIRED","PERMISSION",403);'
    new='  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401); // '+MARK
    if old not in s: raise SystemExit('S33 correction role anchor missing')
    s=s.replace(old,new,1)
    anchor='  const table=entity==="ATTENDANCE_SESSION"?"attendance_sessions":"labor_sessions",pk=entity==="ATTENDANCE_SESSION"?"session_id":"labor_id",before=await env.DB.prepare(`SELECT * FROM ${table} WHERE ${pk}=?1`).bind(id).first<Record<string,unknown>>();if(!before)return apiError("CORRECTION_TARGET_NOT_FOUND","VALIDATION",404);const patch=safePatch(entity,b.patch||{});'
    if anchor not in s: raise SystemExit('S33 correction target anchor missing')
    repl='  const table=entity==="ATTENDANCE_SESSION"?"attendance_sessions":"labor_sessions",pk=entity==="ATTENDANCE_SESSION"?"session_id":"labor_id",before=await env.DB.prepare(`SELECT * FROM ${table} WHERE ${pk}=?1`).bind(id).first<Record<string,unknown>>();if(!before)return apiError("CORRECTION_TARGET_NOT_FOUND","VALIDATION",404);const recent=(await env.DB.prepare("SELECT business_date FROM business_dates ORDER BY sequence_no DESC LIMIT 7").all<{business_date:string}>()).results??[],age=recent.findIndex(x=>x.business_date===String(before.business_date||"")),maxAge=auth.role==="SUPERADMIN"?6:1;if(age<0||age>maxAge)return apiError("CORRECTION_DATE_READ_ONLY","PERMISSION",403);const patch=safePatch(entity,b.patch||{});'
    s=s.replace(anchor,repl,1)
    COR.write_text(s,encoding='utf-8')

s=MR.read_text(encoding='utf-8')
if MARK not in s:
    s=s.replace('const master=events.filter(e=>Boolean(MASTER_TYPES[e.entity_type])&&(e.event_type==="MASTER_IMPORT_UPSERT"||e.event_type==="MASTER_IMPORT_ROLLBACK"));',
                'const master=events.filter(e=>Boolean(MASTER_TYPES[e.entity_type])&&(["MASTER_IMPORT_UPSERT","MASTER_IMPORT_ROLLBACK","MASTER_RESOURCE_UPSERT","MASTER_RESOURCE_DELETE"].includes(e.event_type))); // '+MARK,1)
    old='  for(const e of master){const dataset=MASTER_TYPES[e.entity_type]!,r=after(e);if(!r)continue;'
    new='  for(const e of master){const dataset=MASTER_TYPES[e.entity_type]!,p=payload(e),deleting=e.event_type==="MASTER_RESOURCE_DELETE",r=(deleting?(p.before as Record<string,unknown>|undefined):after(e));if(!r)continue;'
    if old not in s: raise SystemExit('S33 master loop anchor missing')
    s=s.replace(old,new,1)
    old='    if(dataset==="pda"){const key=text(r.resource_id),m=meta(r.metadata_json),row=rowIndex(pda,0,key)??nextRow(pda);if(row>pda.length)pda.push([]);const old=pda[row-1]??[];updates.push({range:`${q("DANH SÁCH PDA")}!A${row}:D${row}`,values:[[key,text(m["5 số cuối Seri"]??m.last5)||key.slice(-5),text(r.status_label),text(m["Ghi chú"]??m.note??old[3])]]});projected++;continue;}'
    new='    if(dataset==="pda"){const key=text(r.resource_id),m=meta(r.metadata_json),row=rowIndex(pda,0,key)??nextRow(pda);if(row>pda.length)pda.push([]);const old=pda[row-1]??[];updates.push({range:`${q("DANH SÁCH PDA")}!A${row}:D${row}`,values:[deleting?["","","",""]:[key,text(m["5 số cuối Seri"]??m.last5)||key.slice(-5),text(r.status_label),text(m["Ghi chú"]??m.note??old[3])]]});projected++;continue;}'
    if old not in s: raise SystemExit('S33 pda projection anchor missing')
    s=s.replace(old,new,1)
    old='    if(dataset==="user_pick"){const key=text(r.resource_id),m=meta(r.metadata_json),row=rowIndex(pick,1,key)??nextRow(pick);if(row>pick.length)pick.push([]);const old=pick[row-1]??[];updates.push({range:`${q("DANH SÁCH USER PICK")}!A${row}:D${row}`,values:[[text(m["Số User"]??m.number??old[0]),key,text(r.status_label),text(m["Ghi chú"]??m.note??old[3])]]});projected++;continue;}'
    new='    if(dataset==="user_pick"){const key=text(r.resource_id),m=meta(r.metadata_json),row=rowIndex(pick,1,key)??nextRow(pick);if(row>pick.length)pick.push([]);const old=pick[row-1]??[];updates.push({range:`${q("DANH SÁCH USER PICK")}!A${row}:D${row}`,values:[deleting?["","","",""]:[text(m["Số User"]??m.number??old[0]),key,text(r.status_label),text(m["Ghi chú"]??m.note??old[3])]]});projected++;continue;}'
    if old not in s: raise SystemExit('S33 pick projection anchor missing')
    s=s.replace(old,new,1)
    old='    if(dataset==="user_pack"){const key=text(r.resource_id),m=meta(r.metadata_json),row=rowIndex(pack,2,key)??nextRow(pack);if(row>pack.length)pack.push([]);const old=pack[row-1]??[];updates.push({range:`${q("DANH SÁCH USER PACK")}!A${row}:D${row}`,values:[[text(m["Tên bàn pack"]??m.pack_table??old[0]),text(m["User pack"]??m.label??old[1]),key,text(r.status_label)]]});projected++;continue;}'
    new='    if(dataset==="user_pack"){const key=text(r.resource_id),m=meta(r.metadata_json),row=rowIndex(pack,2,key)??nextRow(pack);if(row>pack.length)pack.push([]);const old=pack[row-1]??[];updates.push({range:`${q("DANH SÁCH USER PACK")}!A${row}:D${row}`,values:[deleting?["","","",""]:[text(m["Tên bàn pack"]??m.pack_table??old[0]),text(m["User pack"]??m.label??old[1]),key,text(r.status_label)]]});projected++;continue;}'
    if old not in s: raise SystemExit('S33 user pack projection anchor missing')
    s=s.replace(old,new,1)
    old='    if(dataset==="pack_table"){const key=text(r.pack_table),available=Boolean(Number(r.available)),status=text(r.status_label)||await statusLabel(db,"DANH SÁCH BÀN PACK_Tình trạng",available),tableRow=rowIndex(tables,0,key)??nextRow(tables);if(tableRow>tables.length)tables.push([]);updates.push({range:`${q("DANH SÁCH BÀN PACK")}!A${tableRow}:B${tableRow}`,values:[[key,status]]});const user=text(r.user_pack);if(user){const packRow=rowIndex(pack,2,user)??nextRow(pack);if(packRow>pack.length)pack.push([]);const old=pack[packRow-1]??[];updates.push({range:`${q("DANH SÁCH USER PACK")}!A${packRow}:D${packRow}`,values:[[key,text(r.label)||text(old[1]),user,text(old[3])||await statusLabel(db,"DANH SÁCH USER PACK_Tình trạng",true)]]});}projected++;}'
    new='    if(dataset==="pack_table"){const key=text(r.pack_table??r.resource_id),available=Boolean(Number(r.available)),status=text(r.status_label)||await statusLabel(db,"DANH SÁCH BÀN PACK_Tình trạng",available),tableRow=rowIndex(tables,0,key)??nextRow(tables);if(tableRow>tables.length)tables.push([]);updates.push({range:`${q("DANH SÁCH BÀN PACK")}!A${tableRow}:B${tableRow}`,values:[deleting?["",""]:[key,status]]});const user=text(r.user_pack);if(!deleting&&user){const packRow=rowIndex(pack,2,user)??nextRow(pack);if(packRow>pack.length)pack.push([]);const old=pack[packRow-1]??[];updates.push({range:`${q("DANH SÁCH USER PACK")}!A${packRow}:D${packRow}`,values:[[key,text(r.label)||text(old[1]),user,text(old[3])||await statusLabel(db,"DANH SÁCH USER PACK_Tình trạng",true)]]});}projected++;}'
    if old not in s: raise SystemExit('S33 table projection anchor missing')
    s=s.replace(old,new,1)
    MR.write_text(s,encoding='utf-8')

s=REP.read_text(encoding='utf-8')
s=s.replace('timeZone:"Asia/Bangkok"','timeZone:"Asia/Ho_Chi_Minh"')
REP.write_text(s,encoding='utf-8')
print('Applied S33 Service resource admin, role-window correction, Google master replication and VN timezone')
