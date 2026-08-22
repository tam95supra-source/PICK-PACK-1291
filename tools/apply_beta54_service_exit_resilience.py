from pathlib import Path

CORE = Path('service/src/core.ts')
HOT = Path('service/src/session_hotfix.ts')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 anchor, found {count}')
    return text.replace(old, new, 1)

core = CORE.read_text()
old = '''  const pdaExitStatus=text(p,"pda_exit_status",180);\n  const event=await buildEvent(req,auth,a,current.version+1),stmts=eventStatements(db,event,a.authority_seq);'''
new = '''  const pdaExitStatus=text(p,"pda_exit_status",180);\n  if(current.pda_serial){\n    let expected=text({v:current.pda_enter_status??""},"v",180);\n    if(!expected){const row=await db.prepare("SELECT status_label FROM resources WHERE resource_type='PDA' AND resource_id=?1").bind(current.pda_serial).first<{status_label:string}>();expected=String(row?.status_label??"").trim().slice(0,180);}\n    if(!pdaExitStatus)throw new CoreError("PDA_EXIT_STATUS_REQUIRED","VALIDATION",400);\n    if(expected&&pdaExitStatus!==expected)throw new CoreError("PDA_STATUS_MISMATCH_NOTIFY_SPECIALIST","CONFLICT",409,false,{expected_status:expected,current_status:pdaExitStatus,pda_serial:current.pda_serial});\n  }\n  const event=await buildEvent(req,auth,a,current.version+1),stmts=eventStatements(db,event,a.authority_seq);'''
core = replace_once(core, old, new, 'core exit PDA guard')
CORE.write_text(core)

hot = HOT.read_text()
anchor = '''async function byId(db:D1Database,id:string):Promise<SessionRow|null>{return db.prepare("SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,pda_enter_status,pda_exit_status,resource_note,enter_at,exit_at,entered_by,exited_by,version FROM attendance_sessions WHERE session_id=?1").bind(id).first<SessionRow>();}\n'''
insert = anchor + '''type SessionResolution={session:SessionRow|null;error?:"SESSION_EMPLOYEE_MISMATCH"|"SESSION_ACTIVE_AMBIGUOUS"};\nasync function resolveActiveSession(db:D1Database,id:string,mnv:string):Promise<SessionResolution>{\n  const requested=id?await byId(db,id):null;\n  if(requested&&mnv&&requested.mnv!==mnv)return{session:null,error:"SESSION_EMPLOYEE_MISMATCH"};\n  if(requested?.state==="ACTIVE")return{session:requested};\n  if(!mnv)return{session:null};\n  const rows=await db.prepare("SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,pda_enter_status,pda_exit_status,resource_note,enter_at,exit_at,entered_by,exited_by,version FROM attendance_sessions WHERE mnv=?1 AND state='ACTIVE' ORDER BY business_date DESC,updated_at DESC LIMIT 2").bind(mnv).all<SessionRow>();\n  const active=rows.results??[];\n  if(active.length>1)return{session:null,error:"SESSION_ACTIVE_AMBIGUOUS"};\n  return{session:active[0]??null};\n}\n'''
hot = replace_once(hot, anchor, insert, 'session resolver insertion')

old_work = '''  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);const b=await readJsonBody<Record<string,unknown>>(request,128_000),id=text(b.session_id,220),idem=text(b.idempotency_key,220);if(!id||!idem)return apiError("SESSION_WORK_FIELDS_REQUIRED","VALIDATION",400);const prior=await existing(env,idem);if(prior)return json({ok:true,duplicate:true,event:prior,session:await byId(env.DB,id)});\n  const s=await byId(env.DB,id);if(!s)return apiError("SESSION_NOT_FOUND","VALIDATION",404);if(s.state!=="ACTIVE")return apiError("SESSION_NOT_ACTIVE","CONFLICT",409);'''
new_work = '''  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);const b=await readJsonBody<Record<string,unknown>>(request,128_000),id=text(b.session_id,220),mnv=text(b.mnv,80),idem=text(b.idempotency_key,220);if((!id&&!mnv)||!idem)return apiError("SESSION_WORK_FIELDS_REQUIRED","VALIDATION",400);const prior=await existing(env,idem);if(prior)return json({ok:true,duplicate:true,event:prior,session:await byId(env.DB,String(prior.entity_id??id))});\n  const resolved=await resolveActiveSession(env.DB,id,mnv);if(resolved.error)return apiError(resolved.error,"CONFLICT",409);const s=resolved.session;if(!s)return apiError("SESSION_NOT_ACTIVE","CONFLICT",409);'''
hot = replace_once(hot, old_work, new_work, 'session work resolver')

old_exit = '''  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);const b=await readJsonBody<Record<string,unknown>>(request,64_000),id=text(b.session_id,220),idem=text(b.idempotency_key,220);if(!id||!idem)return apiError("SESSION_EXIT_FIELDS_REQUIRED","VALIDATION",400);const prior=await existing(env,idem);if(prior)return json({ok:true,duplicate:true,event:prior,session:await byId(env.DB,id)});const s=await byId(env.DB,id);if(!s||s.state!=="ACTIVE")return apiError("SESSION_NOT_ACTIVE","CONFLICT",409);'''
new_exit = '''  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);const b=await readJsonBody<Record<string,unknown>>(request,64_000),id=text(b.session_id,220),mnv=text(b.mnv,80),idem=text(b.idempotency_key,220);if((!id&&!mnv)||!idem)return apiError("SESSION_EXIT_FIELDS_REQUIRED","VALIDATION",400);const prior=await existing(env,idem);if(prior)return json({ok:true,duplicate:true,event:prior,session:await byId(env.DB,String(prior.entity_id??id))});const resolved=await resolveActiveSession(env.DB,id,mnv);if(resolved.error)return apiError(resolved.error,"CONFLICT",409);const s=resolved.session;if(!s)return apiError("SESSION_NOT_ACTIVE","CONFLICT",409);'''
hot = replace_once(hot, old_exit, new_exit, 'session exit resolver')
HOT.write_text(hot)

print('BETA54_SERVICE_EXIT_RESILIENCE_APPLIED')
