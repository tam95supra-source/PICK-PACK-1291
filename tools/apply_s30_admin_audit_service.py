#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ADMIN=ROOT/'service/src/admin_audit.ts'
ENTRY=ROOT/'service/src/entry.ts'
COMPAT=ROOT/'service/src/compat.ts'
REPL=ROOT/'service/src/replication.ts'
MARK='S30_CANONICAL_ADMIN_AUDIT'

# admin_audit: canonical event uses current business date so PDA N..N-6 cache sees it.
s=ADMIN.read_text(encoding='utf-8')
if MARK not in s:
    s=s.replace('import { nowIso, sha256Hex } from "./util";','import { nowIso, sha256Hex } from "./util";\n\n// S30_CANONICAL_ADMIN_AUDIT',1)
    old='''  const a=await currentAuthority(db);if(a.mode!=="SERVICE_PRIMARY"||a.scope!=="PRODUCTION")throw new CoreError("ADMIN_AUDIT_REQUIRES_SERVICE_PRIMARY","CONFLICT",409,true);\n  const seq=a.authority_seq+1,at=nowIso(),targetId=text(input.target_id,180)||auth.login_id,targetType=text(input.target_type,80)||"ADMIN_ACTION";\n  const payload=sanitizeSensitive({action,target_type:targetType,target_id:targetId,target_label:text(input.target_label,240),result:text(input.result,80)||"OK",detail:text(input.detail,500)}) as Record<string,unknown>;\n  const base={event_id:eventId,event_type:TYPE[action]||"ADMIN_AUDIT",entity_type:targetType,entity_id:targetId,business_date:"MASTER",authority_epoch:a.authority_epoch,authority_seq:seq,service_generation:a.service_generation,base_version:0,new_version:0,actor_id:auth.login_id,actor_role:auth.role,device_id:text(input.device_id,180)||auth.device_id,occurred_at:text(input.occurred_at,80)||at,committed_at:at,payload_json:JSON.stringify(payload),idempotency_key:`admin-audit:${eventId}`,origin:"ADMIN_AUDIT",schema_version:1};\n'''
    new='''  const a=await currentAuthority(db);if(a.mode!=="SERVICE_PRIMARY"||a.scope!=="PRODUCTION")throw new CoreError("ADMIN_AUDIT_REQUIRES_SERVICE_PRIMARY","CONFLICT",409,true);\n  const latest=await db.prepare("SELECT business_date FROM business_dates ORDER BY sequence_no DESC LIMIT 1").first<{business_date:string}>();\n  if(!latest?.business_date)throw new CoreError("BUSINESS_DATE_NOT_BOOTSTRAPPED","INTEGRITY",503,true);\n  const businessDate=latest.business_date,seq=a.authority_seq+1,at=nowIso(),targetId=text(input.target_id,180)||auth.login_id,targetType=text(input.target_type,80)||"ADMIN_ACTION";\n  const payload=sanitizeSensitive({action,target_type:targetType,target_id:targetId,target_label:text(input.target_label,240),mnv:targetType==="STAFF"?targetId:"",result:text(input.result,80)||"OK",detail:text(input.detail,500)}) as Record<string,unknown>;\n  const base={event_id:eventId,event_type:TYPE[action]||"ADMIN_AUDIT",entity_type:targetType,entity_id:targetId,business_date:businessDate,authority_epoch:a.authority_epoch,authority_seq:seq,service_generation:a.service_generation,base_version:0,new_version:0,actor_id:auth.login_id,actor_role:auth.role,device_id:text(input.device_id,180)||auth.device_id,occurred_at:text(input.occurred_at,80)||at,committed_at:at,payload_json:JSON.stringify(payload),idempotency_key:`admin-audit:${eventId}`,origin:"ADMIN_AUDIT",schema_version:1};\n'''
    if old not in s: raise SystemExit('S30 admin audit date anchor missing')
    s=s.replace(old,new,1)
    old='''    db.prepare(`INSERT INTO events(event_id,event_type,entity_type,entity_id,business_date,authority_epoch,authority_seq,service_generation,base_version,new_version,actor_id,actor_role,device_id,occurred_at,committed_at,payload_json,idempotency_key,origin,schema_version,checksum) VALUES(?1,?2,?3,?4,'MASTER',?5,?6,?7,0,0,?8,?9,?10,?11,?12,?13,?14,'ADMIN_AUDIT',1,?15)`).bind(e.event_id,e.event_type,e.entity_type,e.entity_id,e.authority_epoch,e.authority_seq,e.service_generation,e.actor_id,e.actor_role,e.device_id,e.occurred_at,e.committed_at,e.payload_json,e.idempotency_key,e.checksum),\n    db.prepare("INSERT INTO sheet_replication_outbox(event_id,status,attempt_count,next_attempt_at,created_at) VALUES(?1,'PENDING',0,?2,?2)").bind(e.event_id,at),\n'''
    new='''    db.prepare(`INSERT INTO events(event_id,event_type,entity_type,entity_id,business_date,authority_epoch,authority_seq,service_generation,base_version,new_version,actor_id,actor_role,device_id,occurred_at,committed_at,payload_json,idempotency_key,origin,schema_version,checksum) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20)`).bind(e.event_id,e.event_type,e.entity_type,e.entity_id,e.business_date,e.authority_epoch,e.authority_seq,e.service_generation,e.base_version,e.new_version,e.actor_id,e.actor_role,e.device_id,e.occurred_at,e.committed_at,e.payload_json,e.idempotency_key,e.origin,e.schema_version,e.checksum),\n    db.prepare("INSERT INTO sheet_replication_outbox(event_id,status,attempt_count,next_attempt_at,created_at) VALUES(?1,'PENDING',0,?2,?2)").bind(e.event_id,at),\n    db.prepare("INSERT INTO mutation_assertions(event_id,ok) VALUES(?1,1)").bind(e.event_id),\n'''
    if old not in s: raise SystemExit('S30 admin audit insert anchor missing')
    s=s.replace(old,new,1)
    ADMIN.write_text(s,encoding='utf-8')

# entry: authenticated public Service endpoint, fenced during reconciliation.
s=ENTRY.read_text(encoding='utf-8')
if MARK not in s:
    anchor='import { authenticate, internalAuthorized } from "./auth";'
    if anchor not in s: raise SystemExit('S30 entry import anchor missing')
    s=s.replace(anchor,anchor+'\nimport { commitAdminAudit, type AdminAuditInput } from "./admin_audit"; // '+MARK,1)
    anchor='''async function drRebuildGoogle(request:Request,env:Env):Promise<Response>{\n'''
    fn='''async function adminAudit(request:Request,env:Env):Promise<Response>{\n  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);\n  const input=await readJsonBody<AdminAuditInput>(request);\n  try{const result=await commitAdminAudit(env.DB,auth,input);return json({ok:true,duplicate:result.duplicate,event:result.event},result.duplicate?200:201);}\n  catch(e){if(e instanceof Error)console.log(JSON.stringify({level:"warn",kind:"admin_audit_failed",error:String(e).slice(0,240)}));throw e;}\n}\n\n'''
    if anchor not in s: raise SystemExit('S30 entry function anchor missing')
    s=s.replace(anchor,fn+anchor,1)
    old='''      if(path==="/v1/mutations"||path==="/v1/mutations/batch"||path==="/v1/legacy-mutations"||path==="/v1/legacy-mutations/batch"||path==="/internal/legacy-bridge")return apiError("RECONCILING_RETRY","CONFLICT",409,true);\n    }\n    return base.fetch(request,env);\n'''
    new='''      if(path==="/v1/mutations"||path==="/v1/mutations/batch"||path==="/v1/legacy-mutations"||path==="/v1/legacy-mutations/batch"||path==="/v1/admin-audit"||path==="/internal/legacy-bridge")return apiError("RECONCILING_RETRY","CONFLICT",409,true);\n    }\n    if(path==="/v1/admin-audit"&&request.method==="POST")return adminAudit(request,env);\n    return base.fetch(request,env);\n'''
    if old not in s: raise SystemExit('S30 entry route anchor missing')
    s=s.replace(old,new,1)
    ENTRY.write_text(s,encoding='utf-8')

# compat day: map admin audit into readable Android history entries.
s=COMPAT.read_text(encoding='utf-8')
if MARK not in s:
    old='''function labelFor(type:string):string{return type==="ATTENDANCE_ENTER"?"Vào ca":type==="ATTENDANCE_EXIT"?"Ra ca":type==="RESOURCE_CHANGE"?"Đổi tài nguyên":type==="LABOR_START"?"Bắt đầu công nhật":type==="LABOR_FINISH"?"Kết thúc công nhật":type;}\n'''
    new='''// S30_CANONICAL_ADMIN_AUDIT\nfunction labelFor(type:string):string{return type==="ATTENDANCE_ENTER"?"Vào ca":type==="ATTENDANCE_EXIT"?"Ra ca":type==="RESOURCE_CHANGE"?"Đổi tài nguyên":type==="LABOR_START"?"Bắt đầu công nhật":type==="LABOR_FINISH"?"Kết thúc công nhật":type==="MASTER_STAFF_UPSERT"?"Cập nhật nhân sự":type==="MASTER_STAFF_DELETE"?"Xóa nhân sự":type==="ACCOUNT_UPSERT"?"Tạo / sửa tài khoản":type==="ACCOUNT_STATUS"?"Đổi trạng thái tài khoản":type==="ACCOUNT_EMAIL"?"Đổi email tài khoản":type==="ACCOUNT_PASSWORD"?"Đổi mật khẩu":type==="MASTER_STAFF_IMPORT"?"Import nhân sự":type==="ACCOUNT_LOGIN"?"Đăng nhập":type==="ACCOUNT_LOGOUT"?"Đăng xuất":type==="SETTINGS_CHANGE"?"Đổi cài đặt":type==="FALLBACK_RECONCILED_DUPLICATE"?"Đối soát dữ liệu dự phòng":type;}\n'''
    if old not in s: raise SystemExit('S30 compat label anchor missing')
    s=s.replace(old,new,1)
    old='''    let p:Record<string,unknown>={};try{p=JSON.parse(e.payload_json) as Record<string,unknown>;}catch{}const mnv=String(p.mnv??""),key=`${e.business_date}|${mnv}`,session=sessionByKey.get(key),emp=staff.get(key);\n    const item:CompatEvent={event_id:e.event_id,mnv,full_name:emp?.full_name??"",shift:String(session?.shift??p.shift??""),event_type:e.event_type,label:labelFor(e.event_type),at:e.committed_at,at_iso:e.committed_at,actor:e.actor_id,detail:String(p.note??p.labor_type??""),authority_seq:e.authority_seq};const list=eventsByDate.get(e.business_date)??[];list.push(item);eventsByDate.set(e.business_date,list);\n'''
    new='''    let p:Record<string,unknown>={};try{p=JSON.parse(e.payload_json) as Record<string,unknown>;}catch{}const mnv=String(p.mnv??""),key=`${e.business_date}|${mnv}`,session=sessionByKey.get(key),emp=staff.get(key);\n    const item:CompatEvent={event_id:e.event_id,mnv,full_name:emp?.full_name??String(p.target_label??""),shift:String(session?.shift??p.shift??""),event_type:e.event_type,label:labelFor(e.event_type),at:e.committed_at,at_iso:e.committed_at,actor:e.actor_id,detail:String(p.note??p.labor_type??p.detail??""),authority_seq:e.authority_seq};const list=eventsByDate.get(e.business_date)??[];list.push(item);eventsByDate.set(e.business_date,list);\n'''
    if old not in s: raise SystemExit('S30 compat event anchor missing')
    s=s.replace(old,new,1)
    COMPAT.write_text(s,encoding='utf-8')

# replication: canonical admin audit is also visible in Google LỊCH SỬ NGHIỆP VỤ.
s=REPL.read_text(encoding='utf-8')
if MARK not in s:
    anchor='''async function replicateOperational(db:D1Database,env:Env,token:string,events:EventRow[]):Promise<number>{\n'''
    helper='''// S30_CANONICAL_ADMIN_AUDIT\nfunction adminAuditLabel(type:string):string{const m:Record<string,string>={MASTER_STAFF_UPSERT:"Cập nhật nhân sự",MASTER_STAFF_DELETE:"Xóa nhân sự",ACCOUNT_UPSERT:"Tạo / sửa tài khoản",ACCOUNT_STATUS:"Đổi trạng thái tài khoản",ACCOUNT_EMAIL:"Đổi email tài khoản",ACCOUNT_PASSWORD:"Đổi mật khẩu",MASTER_STAFF_IMPORT:"Import nhân sự",ACCOUNT_LOGIN:"Đăng nhập",ACCOUNT_LOGOUT:"Đăng xuất",SETTINGS_CHANGE:"Đổi cài đặt"};return m[type]||type;}\nasync function replicateAdminAudit(sheetId:string,token:string,index:OperationalIndex,e:EventRow):Promise<void>{\n  const p=payload(e),targetType=ptext(p,"target_type")||e.entity_type,targetId=ptext(p,"target_id")||e.entity_id,targetLabel=ptext(p,"target_label"),detail=ptext(p,"detail");\n  const mnv=targetType==="STAFF"?targetId:"";\n  await appendHistory(sheetId,token,index,e,`ADMIN|${targetType}|${targetId}`,mnv,targetLabel,"",adminAuditLabel(e.event_type),detail);\n}\n\n'''
    if anchor not in s: raise SystemExit('S30 replication helper anchor missing')
    s=s.replace(anchor,helper+anchor,1)
    old='''    else if(e.event_type==="LABOR_FINISH")await replicateLaborFinishOperational(db,env.GOOGLE_SOURCE_SHEET_ID,token,index,e);\n    else continue;n++;\n'''
    new='''    else if(e.event_type==="LABOR_FINISH")await replicateLaborFinishOperational(db,env.GOOGLE_SOURCE_SHEET_ID,token,index,e);\n    else if(e.origin==="ADMIN_AUDIT")await replicateAdminAudit(env.GOOGLE_SOURCE_SHEET_ID,token,index,e);\n    else continue;n++;\n'''
    if old not in s: raise SystemExit('S30 replication loop anchor missing')
    s=s.replace(old,new,1)
    REPL.write_text(s,encoding='utf-8')

print('Applied S30 canonical admin audit service route + PDA day history + Google replication')
