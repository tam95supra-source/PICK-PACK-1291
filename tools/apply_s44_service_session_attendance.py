#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AUTH=ROOT/'service/src/auth.ts'
MOBILE=ROOT/'service/src/mobile_hotfix.ts'
LEGACY=ROOT/'service/src/legacy.ts'
CORE=ROOT/'service/src/core.ts'
MARK='S44_IDEMPOTENT_PDA_SESSION_ATTENDANCE'

# auth.ts: same login + same PDA device reuses the current session id; different device still replaces it.
s=AUTH.read_text(encoding='utf-8')
if MARK not in s:
    old='''  const kind:SessionKind=String(input.client_source||"").toUpperCase()==="WEB"?"WEB":"PDA";\n  const sessionId=crypto.randomUUID(), issuedAt=nowIso();'''
    new='''  const kind:SessionKind=String(input.client_source||"").toUpperCase()==="WEB"?"WEB":"PDA";\n  // S44_IDEMPOTENT_PDA_SESSION_ATTENDANCE: repeated same-device auth must not invalidate an in-flight PDA bearer.\n  const currentPda=kind==="PDA"?await db.prepare("SELECT session_id,device_id FROM auth_sessions WHERE login_id=?1").bind(account.login_id).first<SessionRow>():null;\n  const sessionId=kind==="PDA"&&currentPda?.device_id===deviceId&&currentPda.session_id?currentPda.session_id:crypto.randomUUID(), issuedAt=nowIso();'''
    if old not in s: raise SystemExit('S44 auth session anchor missing')
    s=s.replace(old,new,1)
AUTH.write_text(s,encoding='utf-8')

# gas-session exchange: same-device exchange is idempotent and advertises reused/session_id for safe diagnostics.
s=MOBILE.read_text(encoding='utf-8')
if MARK not in s:
    old='''  const sessionId=crypto.randomUUID(),issuedAt=nowIso();\n  await env.DB.prepare(`INSERT INTO auth_sessions(login_id,session_id,device_id,issued_at) VALUES(?1,?2,?3,?4)'''
    new='''  // S44_IDEMPOTENT_PDA_SESSION_ATTENDANCE: same device reuses its active PDA session.\n  const current=await env.DB.prepare("SELECT session_id,device_id FROM auth_sessions WHERE login_id=?1").bind(account.login_id).first<{session_id:string;device_id:string}>();\n  const reused=Boolean(current?.session_id&&current.device_id===deviceId);\n  const sessionId=reused?String(current?.session_id):crypto.randomUUID(),issuedAt=nowIso();\n  await env.DB.prepare(`INSERT INTO auth_sessions(login_id,session_id,device_id,issued_at) VALUES(?1,?2,?3,?4)'''
    if old not in s: raise SystemExit('S44 mobile session anchor missing')
    s=s.replace(old,new,1)
    oldret='''session:{issued_at:issuedAt,device_label:String(input.device_label||"").slice(0,120)}'''
    newret='''session:{issued_at:issuedAt,device_label:String(input.device_label||"").slice(0,120),session_id:sessionId,reused}'''
    if oldret not in s: raise SystemExit('S44 mobile session return anchor missing')
    s=s.replace(oldret,newret,1)
    # employee session output includes the S38 persisted fields.
    s=s.replace('SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,enter_at,exit_at,entered_by,exited_by,version FROM attendance_sessions',
                'SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,pda_enter_status,pda_exit_status,resource_note,enter_at,exit_at,entered_by,exited_by,version FROM attendance_sessions')
MOBILE.write_text(s,encoding='utf-8')

# legacy adapter must not drop S38 attendance fields before Core.
s=LEGACY.read_text(encoding='utf-8')
if MARK not in s:
    old='''canonicalPayload={mnv,shift:text(payload.shift,80),work_choice:text(payload.work_choice,40),pda_serial:text(payload.pda_serial||payload.pda,180),user_pick:text(payload.user_pick||payload.userPick,180),pack_table:text(payload.pack_table||payload.packTable,180),user_pack:text(payload.user_pack||payload.userPack,180),note:text(payload.note,500)};'''
    new='''canonicalPayload={mnv,shift:text(payload.shift,80),work_choice:text(payload.work_choice,40),pda_serial:text(payload.pda_serial||payload.pda,180),user_pick:text(payload.user_pick||payload.userPick,180),pack_table:text(payload.pack_table||payload.packTable,180),user_pack:text(payload.user_pack||payload.userPack,180),pda_enter_status:text(payload.pda_enter_status||payload.pda_status_at_enter,180),resource_note:text(payload.resource_note,500),duplicate_user:Boolean(payload.duplicate_user),note:text(payload.note,500)}; // S44_IDEMPOTENT_PDA_SESSION_ATTENDANCE'''
    if old not in s: raise SystemExit('S44 legacy enter anchor missing')
    s=s.replace(old,new,1)
    old='''canonicalPayload=input.action==="exit"?{mnv,note:text(payload.note,500)}:{mnv,work_choice:text(payload.work_choice,40),pda_serial:text(payload.pda_serial||payload.pda,180),user_pick:text(payload.user_pick||payload.userPick,180),pack_table:text(payload.pack_table||payload.packTable,180),user_pack:text(payload.user_pack||payload.userPack,180),note:text(payload.note,500)};'''
    new='''canonicalPayload=input.action==="exit"?{mnv,pda_exit_status:text(payload.pda_exit_status,180),note:text(payload.note,500)}:{mnv,work_choice:text(payload.work_choice,40),pda_serial:text(payload.pda_serial||payload.pda,180),user_pick:text(payload.user_pick||payload.userPick,180),pack_table:text(payload.pack_table||payload.packTable,180),user_pack:text(payload.user_pack||payload.userPack,180),resource_note:text(payload.resource_note,500),duplicate_user:Boolean(payload.duplicate_user),note:text(payload.note,500)};'''
    if old not in s: raise SystemExit('S44 legacy exit/resource anchor missing')
    s=s.replace(old,new,1)
LEGACY.write_text(s,encoding='utf-8')

# Core stores the persisted S38 fields in attendance_sessions while the immutable event payload keeps duplicate_user.
s=CORE.read_text(encoding='utf-8')
if MARK not in s:
    s=s.replace('''  user_pack: string | null;\n  version: number;''','''  user_pack: string | null;\n  pda_enter_status: string | null;\n  pda_exit_status: string | null;\n  resource_note: string;\n  version: number; // S44_IDEMPOTENT_PDA_SESSION_ATTENDANCE''',1)
    s=s.replace('SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,version FROM attendance_sessions',
                'SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,pda_enter_status,pda_exit_status,resource_note,version FROM attendance_sessions')
    # Enter: capture entry status/note and persist in same transaction after session upsert.
    old='''  const pda=text(p,"pda_serial"), pick=text(p,"user_pick"), table=text(p,"pack_table"), pack=text(p,"user_pack");'''
    new='''  const pda=text(p,"pda_serial"), pick=text(p,"user_pick"), table=text(p,"pack_table"), pack=text(p,"user_pack"), pdaEnterStatus=text(p,"pda_enter_status",180), resourceNote=text(p,"resource_note",500);'''
    if old not in s: raise SystemExit('S44 core enter variable anchor missing')
    s=s.replace(old,new,1)
    enter_push='''  stmts.push(...leaseStatements(db,sessionId,mnv,req.business_date,event.event_id,event.committed_at,[["PDA",pda],["USER_PICK",pick],["PACK_TABLE",table],["USER_PACK",pack]]));'''
    enter_new='''  stmts.push(db.prepare("UPDATE attendance_sessions SET pda_enter_status=?1,resource_note=?2 WHERE session_id=?3").bind(pdaEnterStatus||null,resourceNote,sessionId));\n  stmts.push(...leaseStatements(db,sessionId,mnv,req.business_date,event.event_id,event.committed_at,[["PDA",pda],["USER_PICK",pick],["PACK_TABLE",table],["USER_PACK",pack]]));'''
    if enter_push not in s: raise SystemExit('S44 core enter persistence anchor missing')
    s=s.replace(enter_push,enter_new,1)
    # Exit status persisted atomically with exit event.
    old='''  const event=await buildEvent(req,auth,a,current.version+1),stmts=eventStatements(db,event,a.authority_seq);'''
    new='''  const pdaExitStatus=text(p,"pda_exit_status",180);\n  const event=await buildEvent(req,auth,a,current.version+1),stmts=eventStatements(db,event,a.authority_seq);'''
    # replace first occurrence after commitAttendanceExit only
    pos=s.find('async function commitAttendanceExit')
    ix=s.find(old,pos)
    if ix<0: raise SystemExit('S44 core exit event anchor missing')
    s=s[:ix]+s[ix:].replace(old,new,1)
    exit_push='''  stmts.push(db.prepare("DELETE FROM resource_leases WHERE session_id=?1").bind(current.session_id));'''
    exit_new='''  stmts.push(db.prepare("UPDATE attendance_sessions SET pda_exit_status=?1 WHERE session_id=?2").bind(pdaExitStatus||null,current.session_id));\n  stmts.push(db.prepare("DELETE FROM resource_leases WHERE session_id=?1").bind(current.session_id));'''
    pos=s.find('async function commitAttendanceExit')
    ix=s.find(exit_push,pos)
    if ix<0: raise SystemExit('S44 core exit persistence anchor missing')
    s=s[:ix]+s[ix:].replace(exit_push,exit_new,1)
    # Resource change note persisted if supplied.
    pos=s.find('async function commitResourceChange')
    needle='''  stmts.push(...leaseStatements(db,current.session_id,current.mnv,req.business_date,event.event_id,event.committed_at,'''
    ix=s.find(needle,pos)
    if ix<0: raise SystemExit('S44 resource persistence anchor missing')
    inject='''  const resourceNote=text(p,"resource_note",500);\n  if(resourceNote)stmts.push(db.prepare("UPDATE attendance_sessions SET resource_note=?1 WHERE session_id=?2").bind(resourceNote,current.session_id));\n'''
    s=s[:ix]+inject+s[ix:]
CORE.write_text(s,encoding='utf-8')

# Contracts
A=AUTH.read_text();M=MOBILE.read_text();L=LEGACY.read_text();C=CORE.read_text()
checks=[
    ('currentPda' in A and 'currentPda?.device_id===deviceId' in A,'direct PDA session reuse'),
    ('const reused=Boolean(current?.session_id&&current.device_id===deviceId)' in M,'GAS exchange session reuse'),
    ('session_id:sessionId,reused' in M,'session diagnostics response'),
    ('pda_enter_status' in L and 'pda_exit_status' in L and 'duplicate_user' in L and 'resource_note' in L,'legacy attendance preservation'),
    ('pda_enter_status' in C and 'pda_exit_status' in C and 'resource_note' in C,'core attendance persistence'),
]
for ok,label in checks:
    if not ok: raise SystemExit('S44 service contract missing: '+label)
print('Applied S44 Service: idempotent same-device PDA session + persistent S38 attendance fields')
