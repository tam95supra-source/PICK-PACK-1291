#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ENTRY=ROOT/'service/src/entry_product.ts'
LEGACY=ROOT/'service/src/legacy.ts'
MARK='S39_MOBILE_ROUTE_LEGACY_FIX'

entry=ENTRY.read_text(encoding='utf-8')
if './entry_hotfix' not in entry:
    old='import current, { RealtimeHub } from "./entry";'
    if old not in entry:
        raise SystemExit('S39 entry_product import anchor missing')
    entry=entry.replace(old,'import current, { RealtimeHub } from "./entry_hotfix"; // S39_MOBILE_ROUTE_LEGACY_FIX',1)
ENTRY.write_text(entry,encoding='utf-8')

legacy=LEGACY.read_text(encoding='utf-8')
if MARK not in legacy:
    old_enter='''    canonicalPayload={mnv,shift:text(payload.shift,80),work_choice:text(payload.work_choice,40),pda_serial:text(payload.pda_serial||payload.pda,180),user_pick:text(payload.user_pick||payload.userPick,180),pack_table:text(payload.pack_table||payload.packTable,180),user_pack:text(payload.user_pack||payload.userPack,180),note:text(payload.note,500)};'''
    new_enter='''    // S39_MOBILE_ROUTE_LEGACY_FIX: preserve the full S38 attendance contract through the durable legacy batch adapter.\n    canonicalPayload={mnv,shift:text(payload.shift,80),work_choice:text(payload.work_choice,40),pda_serial:text(payload.pda_serial||payload.pda,180),user_pick:text(payload.user_pick||payload.userPick,180),pack_table:text(payload.pack_table||payload.packTable,180),user_pack:text(payload.user_pack||payload.userPack,180),pda_status_at_enter:text(payload.pda_status_at_enter,120),duplicate_user:Boolean(payload.duplicate_user),resource_note:text(payload.resource_note,120),note:text(payload.note,500)};'''
    if old_enter not in legacy:
        raise SystemExit('S39 legacy enter anchor missing')
    legacy=legacy.replace(old_enter,new_enter,1)

    old_exit='''    canonicalPayload=input.action==="exit"?{mnv,note:text(payload.note,500)}:{mnv,work_choice:text(payload.work_choice,40),pda_serial:text(payload.pda_serial||payload.pda,180),user_pick:text(payload.user_pick||payload.userPick,180),pack_table:text(payload.pack_table||payload.packTable,180),user_pack:text(payload.user_pack||payload.userPack,180),note:text(payload.note,500)};'''
    new_exit='''    canonicalPayload=input.action==="exit"?{mnv,pda_exit_status:text(payload.pda_exit_status,120),note:text(payload.note,500)}:{mnv,work_choice:text(payload.work_choice,40),pda_serial:text(payload.pda_serial||payload.pda,180),user_pick:text(payload.user_pick||payload.userPick,180),pack_table:text(payload.pack_table||payload.packTable,180),user_pack:text(payload.user_pack||payload.userPack,180),resource_note:text(payload.resource_note,120),note:text(payload.note,500)};'''
    if old_exit not in legacy:
        raise SystemExit('S39 legacy exit anchor missing')
    legacy=legacy.replace(old_exit,new_exit,1)
LEGACY.write_text(legacy,encoding='utf-8')

entry2=ENTRY.read_text(encoding='utf-8');legacy2=LEGACY.read_text(encoding='utf-8')
for need in ['./entry_hotfix','S39_MOBILE_ROUTE_LEGACY_FIX']:
    if need not in entry2 and need not in legacy2:
        raise SystemExit('S39 service contract missing: '+need)
for need in ['pda_status_at_enter','duplicate_user','resource_note','pda_exit_status']:
    if need not in legacy2:
        raise SystemExit('S39 legacy field missing: '+need)
print('Applied S39: restored mobile/session routes and preserved S38 fields through legacy batch adapter')
