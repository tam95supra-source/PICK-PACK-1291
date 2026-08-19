#!/usr/bin/env python3
from pathlib import Path
p=Path('service/src/recovery.ts')
s=p.read_text(encoding='utf-8')
MARK='S28B_SQL_SEMANTIC_REFLECTED_ENTER'
if MARK in s:
    print('S28B already applied'); raise SystemExit(0)
start=s.find('async function recordAlreadyReflectedEnter(')
end=s.find('\nexport async function failbackFromFallbackInbox',start)
if start<0 or end<0: raise SystemExit('S28B helper anchors missing')
helper=r'''// S28B_SQL_SEMANTIC_REFLECTED_ENTER
// Use the same SQL semantic comparison proven by the production diagnostic. This avoids
// divergent legacy alias/normalization logic between recovery code and the D1 gate.
async function recordAlreadyReflectedEnter(db:D1Database,row:InboxRow):Promise<boolean>{
  const e=parseEnvelope(row.event_json);if(e.action!=="enter")return false;
  const cur=await db.prepare(`WITH f AS (
    SELECT json_extract(event_json,'$.business_date') d,
      json_extract(json_extract(event_json,'$.payload_json'),'$.mnv') mnv,
      COALESCE(json_extract(json_extract(event_json,'$.payload_json'),'$.shift'),'') shift,
      CASE WHEN UPPER(TRIM(COALESCE(json_extract(json_extract(event_json,'$.payload_json'),'$.work_choice'),'')))='PICK' THEN 'PICK'
           WHEN UPPER(TRIM(COALESCE(json_extract(json_extract(event_json,'$.payload_json'),'$.work_choice'),'')))='PACK' THEN 'PACK' ELSE 'KHONG' END work_choice,
      COALESCE(json_extract(json_extract(event_json,'$.payload_json'),'$.pda_serial'),json_extract(json_extract(event_json,'$.payload_json'),'$.pda'),'') pda_serial,
      COALESCE(json_extract(json_extract(event_json,'$.payload_json'),'$.user_pick'),json_extract(json_extract(event_json,'$.payload_json'),'$.userPick'),'') user_pick,
      COALESCE(json_extract(json_extract(event_json,'$.payload_json'),'$.pack_table'),json_extract(json_extract(event_json,'$.payload_json'),'$.packTable'),'') pack_table,
      COALESCE(json_extract(json_extract(event_json,'$.payload_json'),'$.user_pack'),json_extract(json_extract(event_json,'$.payload_json'),'$.userPack'),'') user_pack
    FROM fallback_event_inbox WHERE event_id=?1 AND authority_epoch=?2 AND authority_seq=?3
  ) SELECT f.mnv,s.session_id,s.state,s.version,
      CASE WHEN s.shift=f.shift AND s.work_choice=f.work_choice AND COALESCE(s.pda_serial,'')=f.pda_serial AND COALESCE(s.user_pick,'')=f.user_pick AND COALESCE(s.pack_table,'')=f.pack_table AND COALESCE(s.user_pack,'')=f.user_pack THEN 1 ELSE 0 END semantic_match
    FROM f LEFT JOIN attendance_sessions s ON s.business_date=f.d AND s.mnv=f.mnv`).bind(row.event_id,row.authority_epoch,row.authority_seq).first<{mnv:string;session_id:string|null;state:string|null;version:number|null;semantic_match:number}>();
  if(!cur||!cur.session_id||cur.state!=="ACTIVE"||Number(cur.semantic_match)!==1)return false;
  const a=await currentAuthority(db);if(a.authority_epoch!==row.authority_epoch||a.authority_seq!==row.authority_seq-1)throw new Error(`FALLBACK_REFLECTED_SEQ_STATE_INVALID:${a.authority_epoch}/${a.authority_seq}:${row.authority_seq}`);
  const committed=nowIso(),payload=sanitizeSensitive({original_action:e.action,mnv:cur.mnv,resolution:"ALREADY_REFLECTED_NOOP",source:"GOOGLE_FALLBACK"}) as Record<string,unknown>,v=Number(cur.version??0);
  const base={event_id:row.event_id,event_type:"FALLBACK_RECONCILED_DUPLICATE",entity_type:"ATTENDANCE_SESSION",entity_id:cur.session_id,business_date:e.business_date,authority_epoch:row.authority_epoch,authority_seq:row.authority_seq,service_generation:row.service_generation,base_version:v,new_version:v,actor_id:e.actor,actor_role:e.role,device_id:e.device_id||"gas-fallback",occurred_at:e.occurred_at||committed,committed_at:committed,payload_json:JSON.stringify(payload),idempotency_key:`fallback-reconciled:${row.event_id}`,origin:"GOOGLE_FALLBACK_RECONCILED",schema_version:1};
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
s=s[:start]+helper+s[end+1:]
p.write_text(s,encoding='utf-8')
print('Applied S28B SQL semantic reflected-enter recovery')
