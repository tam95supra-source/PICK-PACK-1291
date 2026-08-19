#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
IDX=ROOT/'service/src/index.ts'
M2PATCH=ROOT/'tools/apply_m2_android_transport_patch.py'
GRADLE=ROOT/'app/build.gradle.kts'
MARK='S30D_CANONICAL_AUDIT_BATCH'

s=IDX.read_text(encoding='utf-8')
if MARK not in s:
    anchor='import { commitLegacyMutation, type LegacyMutationInput } from "./legacy";'
    if anchor not in s: raise SystemExit('S30D index import anchor missing')
    s=s.replace(anchor,anchor+'\nimport { commitAdminAudit, type AdminAuditInput } from "./admin_audit"; // '+MARK,1)
    anchor='async function legacyMutationBatch(request:Request,env:Env):Promise<Response>{'
    pos=s.find(anchor)
    if pos<0: raise SystemExit('S30D batch function anchor missing')
    fn='''async function adminAuditDirect(request:Request,env:Env):Promise<Response>{\n  const auth=await requireAuth(request,env),input=await readJsonBody<AdminAuditInput>(request),result=await commitAdminAudit(env.DB,auth,input),e=result.event;\n  const delivered=await broadcastEvent(env,e);return json({ok:true,duplicate:result.duplicate,event:eventPublic(e as unknown as Record<string,unknown>),realtime_delivered:delivered},result.duplicate?200:201);\n}\n'''
    s=s[:pos]+fn+s[pos:]
    old='''  for(const input of events){const localEventId=String(input?.event_id||"");try{\n    const result=await commitLegacyMutation(env.DB,env,auth,input),e=result.event as {event_id:string;event_type:string;entity_type:string;entity_id:string;business_date:string;authority_epoch:number;authority_seq:number;service_generation:string;new_version:number},delivered=await broadcastEvent(env,e);\n'''
    new='''  for(const input of events){const localEventId=String(input?.event_id||"");try{\n    if(String((input as unknown as {action?:string}).action||"")==="admin_audit"){\n      const ai=input as unknown as AdminAuditInput,ar=await commitAdminAudit(env.DB,auth,ai),ae=ar.event,delivered=await broadcastEvent(env,ae);\n      results.push({local_event_id:localEventId,status:ar.duplicate?"DUPLICATE":"CONFIRMED",canonical_event_id:ae.event_id,authority_epoch:ae.authority_epoch,authority_seq:ae.authority_seq,new_version:0,error_code:null,conflict:null,realtime_delivered:delivered});continue;\n    }\n    const result=await commitLegacyMutation(env.DB,env,auth,input),e=result.event as {event_id:string;event_type:string;entity_type:string;entity_id:string;business_date:string;authority_epoch:number;authority_seq:number;service_generation:string;new_version:number},delivered=await broadcastEvent(env,e);\n'''
    if old not in s: raise SystemExit('S30D batch loop anchor missing')
    s=s.replace(old,new,1)
    route='  if(p==="/v1/legacy-mutations/batch"&&method==="POST")return legacyMutationBatch(request,env);'
    if route not in s: raise SystemExit('S30D route anchor missing')
    s=s.replace(route,route+'\n  if(p==="/v1/admin/audit"&&method==="POST")return adminAuditDirect(request,env);',1)
    IDX.write_text(s,encoding='utf-8')

# One Android audit implementation only: canonical S30 durable outbox.
m=M2PATCH.read_text(encoding='utf-8')
m=m.replace('    runpy.run_path(str(ROOT / "tools/apply_s30_admin_audit_android.py"), run_name="__main__")\n','')
m=m.replace('runpy.run_path(str(ROOT / "tools/apply_s30_admin_audit_android.py"), run_name="__main__")\n','')
M2PATCH.write_text(m,encoding='utf-8')

g=GRADLE.read_text(encoding='utf-8')
g=g.replace('    inputs.file(rootProject.file("tools/apply_s30_admin_audit_android.py"))\n','')
if 'tools/apply_s30_canonical_admin_audit.py' not in g:
    anchor='    inputs.file(rootProject.file("tools/apply_s29_owner_localfirst_history.py"))\n'
    if anchor not in g: raise SystemExit('S30D Gradle S29 anchor missing')
    g=g.replace(anchor,anchor+'    inputs.file(rootProject.file("tools/apply_s30_canonical_admin_audit.py"))\n',1)
GRADLE.write_text(g,encoding='utf-8')
print('Applied S30D canonical audit batch bridge and normalized Android S30 chain')
