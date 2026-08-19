#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
IDX=ROOT/'service/src/index.ts'
REP=ROOT/'service/src/replication.ts'
M2=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt'
API=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt'
MARK='S30_CANONICAL_ADMIN_AUDIT'

s=IDX.read_text(encoding='utf-8')
# S30D already owns the Service batch/direct routes. During Android Gradle transforms,
# do not try to re-apply the older Service anchors; only compose the Android portion below.
if MARK not in s and 'S30D_CANONICAL_AUDIT_BATCH' not in s:
    a='import { commitLegacyMutation, type LegacyMutationInput } from "./legacy";'
    if a not in s: raise SystemExit('S30 index import anchor missing')
    s=s.replace(a,a+'\nimport { commitAdminAudit, type AdminAuditInput } from "./admin_audit"; // '+MARK,1)
    anchor='async function legacyMutationBatch(request:Request,env:Env):Promise<Response>{'
    pos=s.find(anchor)
    if pos<0: raise SystemExit('S30 legacy batch anchor missing')
    fn='''async function adminAudit(request:Request,env:Env):Promise<Response>{\n  const auth=await requireAuth(request,env),input=await readJsonBody<AdminAuditInput>(request),result=await commitAdminAudit(env.DB,auth,input),e=result.event;\n  const delivered=await broadcastEvent(env,e);return json({ok:true,duplicate:result.duplicate,event:eventPublic(e as unknown as Record<string,unknown>),realtime_delivered:delivered},result.duplicate?200:201);\n}\n'''
    s=s[:pos]+fn+s[pos:]
    old='''  for(const input of events){const localEventId=String(input?.event_id||"");try{\n    const result=await commitLegacyMutation(env.DB,env,auth,input),e=result.event as {event_id:string;event_type:string;entity_type:string;entity_id:string;business_date:string;authority_epoch:number;authority_seq:number;service_generation:string;new_version:number},delivered=await broadcastEvent(env,e);\n'''
    new='''  for(const input of events){const localEventId=String(input?.event_id||"");try{\n    if(String((input as unknown as {action?:string}).action||"")==="admin_audit"){\n      const ai=input as unknown as AdminAuditInput;const ar=await commitAdminAudit(env.DB,auth,ai),ae=ar.event,delivered=await broadcastEvent(env,ae);\n      results.push({local_event_id:localEventId,status:ar.duplicate?"DUPLICATE":"CONFIRMED",canonical_event_id:ae.event_id,authority_epoch:ae.authority_epoch,authority_seq:ae.authority_seq,new_version:0,error_code:null,conflict:null,realtime_delivered:delivered});continue;\n    }\n    const result=await commitLegacyMutation(env.DB,env,auth,input),e=result.event as {event_id:string;event_type:string;entity_type:string;entity_id:string;business_date:string;authority_epoch:number;authority_seq:number;service_generation:string;new_version:number},delivered=await broadcastEvent(env,e);\n'''
    if old not in s: raise SystemExit('S30 legacy batch loop anchor missing')
    s=s.replace(old,new,1)
    r='  if(p==="/v1/legacy-mutations/batch"&&method==="POST")return legacyMutationBatch(request,env);'
    if r not in s: raise SystemExit('S30 route anchor missing')
    s=s.replace(r,r+'\n  if(p==="/v1/admin/audit"&&method==="POST")return adminAudit(request,env);',1)
    IDX.write_text(s,encoding='utf-8')

s=REP.read_text(encoding='utf-8')
if MARK not in s:
    anchor='async function replicateOperational(db:D1Database,env:Env,token:string,events:EventRow[]):Promise<number>{'
    pos=s.find(anchor)
    if pos<0: raise SystemExit('S30 replication function anchor missing')
    helper='''function adminHistoryLabel(type:string):string{const m:Record<string,string>={MASTER_STAFF_UPSERT:"Cập nhật nhân sự",MASTER_STAFF_DELETE:"Xóa nhân sự",MASTER_STAFF_IMPORT:"Import nhân sự",ACCOUNT_UPSERT:"Tạo / sửa tài khoản",ACCOUNT_STATUS:"Đổi trạng thái tài khoản",ACCOUNT_EMAIL:"Đổi email tài khoản",ACCOUNT_PASSWORD:"Đổi mật khẩu",ACCOUNT_LOGIN:"Đăng nhập",ACCOUNT_LOGOUT:"Đăng xuất",SETTINGS_CHANGE:"Thay đổi cài đặt",FALLBACK_RECONCILED_DUPLICATE:"Đối soát dữ liệu dự phòng"};return m[type]??type;}\nasync function replicateAdminHistory(env:Env,token:string,index:OperationalIndex,e:EventRow):Promise<void>{\n  const p=payload(e),target=ptext(p,"target_id")||e.entity_id,label=adminHistoryLabel(e.event_type),targetLabel=ptext(p,"target_label"),result=ptext(p,"result"),detail=[targetLabel,ptext(p,"detail"),result&&`Kết quả: ${result}`].filter(Boolean).join(" • ");\n  await appendHistory(env.GOOGLE_SOURCE_SHEET_ID,token,index,e,`ADMIN:${target}`,target,targetLabel,"",label,detail);\n}\n// S30_CANONICAL_ADMIN_AUDIT\n'''
    s=s[:pos]+helper+s[pos:]
    old='''    else if(e.event_type==="LABOR_FINISH")await replicateLaborFinishOperational(db,env.GOOGLE_SOURCE_SHEET_ID,token,index,e);\n    else continue;n++;\n'''
    new='''    else if(e.event_type==="LABOR_FINISH")await replicateLaborFinishOperational(db,env.GOOGLE_SOURCE_SHEET_ID,token,index,e);\n    else if(["MASTER_STAFF_UPSERT","MASTER_STAFF_DELETE","MASTER_STAFF_IMPORT","ACCOUNT_UPSERT","ACCOUNT_STATUS","ACCOUNT_EMAIL","ACCOUNT_PASSWORD","ACCOUNT_LOGIN","ACCOUNT_LOGOUT","SETTINGS_CHANGE","FALLBACK_RECONCILED_DUPLICATE"].includes(e.event_type))await replicateAdminHistory(env,token,index,e);\n    else continue;n++;\n'''
    if old not in s: raise SystemExit('S30 replication loop anchor missing')
    s=s.replace(old,new,1)
    REP.write_text(s,encoding='utf-8')

s=M2.read_text(encoding='utf-8')
if MARK not in s:
    anchor='    fun acknowledgeFallback(eventId: String, ok: Boolean, error: String?) {'
    pos=s.find(anchor)
    if pos<0: raise SystemExit('S30 M2 audit insert anchor missing')
    fn='''    // S30_CANONICAL_ADMIN_AUDIT: durable sanitized audit through the same SQLite outbox.\n    fun audit(action:String,payload:JSONObject){\n        if(action !in ADMIN_AUDIT_ACTIONS)return\n        val eventId=java.util.UUID.randomUUID().toString()\n        val targetId=when(action){"staff_upsert","staff_delete"->payload.optString("mnv");"account_upsert","account_status","change_email","change_password"->payload.optString("login_id").ifBlank{payload.optString("target_login_id")};else->""}\n        val targetLabel=payload.optString("full_name").ifBlank{payload.optString("display_name")}.take(180)\n        val detail=when(action){"staff_upsert"->"Thêm / cập nhật hồ sơ nhân sự";"staff_delete"->"Xóa hồ sơ nhân sự";"account_upsert"->"Tạo / cập nhật tài khoản";"account_status"->"Thay đổi trạng thái tài khoản";"change_email"->"Thay đổi email tài khoản";"change_password"->"Thay đổi mật khẩu";else->"Thao tác quản trị"}\n        val body=JSONObject().put("action","admin_audit").put("event_id",eventId).put("target_type",if(action.startsWith("staff_"))"STAFF" else "ACCOUNT").put("target_id",targetId.take(180)).put("target_label",targetLabel).put("result","OK").put("detail",detail).put("device_id",M2DeviceIdentity.id(app)).put("occurred_at",java.time.Instant.now().toString())\n        store.enqueueMutation(body,false);M2WorkScheduler.schedule(app)\n    }\n\n'''
    s=s[:pos]+fn+s[pos:]
    anchor2='        val SYNC_ACTIONS = setOf("sync_status", "sync_day", "sync_bootstrap")'
    if anchor2 not in s: raise SystemExit('S30 M2 companion anchor missing')
    s=s.replace(anchor2,'        val ADMIN_AUDIT_ACTIONS = setOf("staff_upsert","staff_delete","account_upsert","account_status","change_email","change_password")\n'+anchor2,1)
    M2.write_text(s,encoding='utf-8')

s=API.read_text(encoding='utf-8')
if MARK not in s:
    anchor='    private val executor = Executors.newSingleThreadExecutor()\n'
    if anchor not in s: raise SystemExit('S30 API transport anchor missing')
    s=s.replace(anchor,anchor+'    private val adminAuditTransport by lazy { M2ServiceTransport(appContext) } // '+MARK+'\n',1)
    # Earlier runtime patches reshape the result-success block. Anchor immediately before the
    # stable 401/session handling line instead of depending on the exact preceding block.
    audit_anchor='      if (result.code == 401) clearSession()\n'
    if s.count(audit_anchor)!=1: raise SystemExit(f'S30 API post-result anchor mismatch: {s.count(audit_anchor)}')
    audit_line='      if (result.ok && action in M2ServiceTransport.ADMIN_AUDIT_ACTIONS) adminAuditTransport.audit(action,payload)\n'
    s=s.replace(audit_anchor,audit_line+audit_anchor,1)
    API.write_text(s,encoding='utf-8')

print('Applied S30 canonical admin audit across Service replication and Android durable outbox')
