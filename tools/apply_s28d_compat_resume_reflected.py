#!/usr/bin/env python3
from pathlib import Path

recovery=Path('service/src/recovery.ts')
s=recovery.read_text(encoding='utf-8')
if 'export async function recordAlreadyReflectedEnter' not in s:
    old='async function recordAlreadyReflectedEnter(db:D1Database,row:InboxRow):Promise<boolean>{'
    if old not in s: raise SystemExit('S28D recovery helper anchor missing')
    s=s.replace(old,'export async function recordAlreadyReflectedEnter(db:D1Database,row:InboxRow):Promise<boolean>{',1)
    recovery.write_text(s,encoding='utf-8')

compat=Path('service/src/recovery_resume_compat.ts')
t=compat.read_text(encoding='utf-8')
mark='S28D_COMPAT_REFLECTED_ENTER'
if mark not in t:
    anchor='import { nowIso, sha256Hex } from "./util";'
    if anchor not in t: raise SystemExit('S28D compat import anchor missing')
    t=t.replace(anchor,anchor+'\nimport { recordAlreadyReflectedEnter } from "./recovery"; // S28D_COMPAT_REFLECTED_ENTER',1)
    old='for(let i=before.authority_seq;i<rows.length;i++){await replayRow(db,env,rows[i]!);applied++;}'
    new='for(let i=before.authority_seq;i<rows.length;i++){const row=rows[i]!;if(await recordAlreadyReflectedEnter(db,row)){applied++;continue;}await replayRow(db,env,row);applied++;}'
    if old not in t: raise SystemExit('S28D compat replay loop anchor missing')
    t=t.replace(old,new,1)
    compat.write_text(t,encoding='utf-8')
print('S28D compatibility resume now uses exact reflected-enter reconciliation')
