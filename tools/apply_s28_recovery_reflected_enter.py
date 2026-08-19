#!/usr/bin/env python3
from pathlib import Path

p=Path('service/src/recovery.ts')
s=p.read_text(encoding='utf-8')
MARK='S28_REFLECTED_ENTER_RECONCILIATION'
if MARK in s:
    print('S28 recovery patch already applied')
    raise SystemExit(0)

s=s.replace('import { currentAuthority } from "./core";', 'import { currentAuthority, sanitizeSensitive } from "./core";', 1)
s=s.replace('import { nowIso, sha256Hex } from "./util";', 'import { nowIso, sha256Hex, workChoice } from "./util";', 1)

anchor='export async function failbackFromFallbackInbox'
pos=s.find(anchor)
if pos<0: raise SystemExit('S28 failback anchor missing')
helper=r'''
// S28_REFLECTED_ENTER_RECONCILIATION
// A fallback ENTER may already be represented by the D1 projection when authority split happened.
// Only an exact semantic match is canonicalized as a no-op audit event. We never turn arbitrary
// conflicts into success, and we intentionally do not enqueue this reconciliation event back to
// Google because the source fallback row already lives there.
async function recordAlreadyReflectedEnter(db:D1Database,row:InboxRow):Promise<boolean>{
  const e=parseEnvelope(row.event_json);if(e.action!=="enter")return false;
  const p=JSON.parse(e.payload_json) as Record<string,unknown>,mnv=String(p.mnv??"").trim();if(!mnv)return false;
  const cur=await db.prepare(`SELECT session_id,state,version,shift,work_choice,COALESCE(pda_serial,'') pda_serial,COALESCE(user_pick,'') user_pick,COALESCE(pack_table,'') pack_table,COALESCE(user_pack,'') user_pack FROM attendance_sessions WHERE mnv=?1 AND business_date=?2`).bind(mnv,e.business_date).first<{session_id:string;state:string;version:number;shift:string;work_choice:string;pda_serial:string;user_pick:string;pack_table:string;user_pack:string}>();
  if(!cur||cur.state!=="ACTIVE")return false;
  const txt=(v:unknown,max=240)=>String(v??"").trim().slice(0,max);
  const expected={shift:txt(p.shift,80),work_choice:workChoice(p.work_choice),pda_serial:txt(p.pda_serial??p.pda,180),user_pick:txt(p.user_pick??p.userPick,180),pack_table:txt(p.pack_table??p.packTable,180),user_pack:txt(p.user_pack??p.userPack,180)};
  if(cur.shift!==expected.shift||cur.work_choice!==expected.work_choice||cur.pda_serial!==expected.pda_serial||cur.user_pick!==expected.user_pick||cur.pack_table!==expected.pack_table||cur.user_pack!==expected.user_pack)return false;
  const a=await currentAuthority(db);if(a.authority_epoch!==row.authority_epoch||a.authority_seq!==row.authority_seq-1)throw new Error(`FALLBACK_REFLECTED_SEQ_STATE_INVALID:${a.authority_epoch}/${a.authority_seq}:${row.authority_seq}`);
  const committed=nowIso(),payload=sanitizeSensitive({original_action:e.action,mnv,resolution:"ALREADY_REFLECTED_NOOP",source:"GOOGLE_FALLBACK"}) as Record<string,unknown>;
  const base={event_id:row.event_id,event_type:"FALLBACK_RECONCILED_DUPLICATE",entity_type:"ATTENDANCE_SESSION",entity_id:cur.session_id,business_date:e.business_date,authority_epoch:row.authority_epoch,authority_seq:row.authority_seq,service_generation:row.service_generation,base_version:cur.version,new_version:cur.version,actor_id:e.actor,actor_role:e.role,device_id:e.device_id||"gas-fallback",occurred_at:e.occurred_at||committed,committed_at:committed,payload_json:JSON.stringify(payload),idempotency_key:`fallback-reconciled:${row.event_id}`,origin:"GOOGLE_FALLBACK_RECONCILED",schema_version:1};
  const checksum=await sha256Hex(JSON.stringify(base));
  await db.batch([
    db.prepare("UPDATE authority_state SET authority_seq=?1,updated_at=?2 WHERE singleton_id=1 AND authority_epoch=?3 AND authority_seq=?4").bind(row.authority_seq,committed,row.authority_epoch,row.authority_seq-1),
    db.prepare(`INSERT INTO events(event_id,event_type,entity_type,entity_id,business_date,authority_epoch,authority_seq,service_generation,base_version,new_version,actor_id,actor_role,device_id,occurred_at,committed_at,payload_json,idempotency_key,origin,schema_version,checksum) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20)`).bind(base.event_id,base.event_type,base.entity_type,base.entity_id,base.business_date,base.authority_epoch,base.authority_seq,base.service_generation,base.base_version,base.new_version,base.actor_id,base.actor_role,base.device_id,base.occurred_at,base.committed_at,base.payload_json,base.idempotency_key,base.origin,base.schema_version,checksum),
    db.prepare("INSERT INTO mutation_assertions(event_id,ok) VALUES(?1,1)").bind(row.event_id),
    db.prepare("UPDATE fallback_event_inbox SET ingest_status='APPLIED',applied_at=?1,last_error=NULL WHERE event_id=?2").bind(committed,row.event_id),
  ]);
  return true;
}

'''
s=s[:pos]+helper+s[pos:]
old='for(let i=before.authority_seq;i<rows.length;i++){await replayRow(db,env,rows[i]!);applied++;}'
new='for(let i=before.authority_seq;i<rows.length;i++){const row=rows[i]!;if(await recordAlreadyReflectedEnter(db,row)){applied++;continue;}await replayRow(db,env,row);applied++;}'
if old not in s: raise SystemExit('S28 resume replay anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('Applied S28 reflected-enter recovery patch')
