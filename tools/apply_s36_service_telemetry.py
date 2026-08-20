#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'service/src/index.ts'
s=P.read_text(encoding='utf-8')
MARK='S36_SERVICE_ONLINE_TELEMETRY'
if MARK in s:
    print('S36 service telemetry already applied')
    raise SystemExit(0)

old='''interface StatusRow {
  business_date:string|null; sequence_no:number|null;
  authority_epoch:number; authority_seq:number; authority_mode:string; authority_scope:string; authority_generation:string; authority_updated_at:string;
  target_kind:string|null; target_identity:string|null; replication_schema_version:number|null; replication_state:string|null; checkpoint:string|null;
  replication_pending_count:number|null; actual_pending_count:number|null; retry_count:number|null; last_attempt_at:string|null; last_success_at:string|null;
  last_error_class:string|null; last_error:string|null; replication_updated_at:string|null;
}'''
new='''interface StatusRow {
  business_date:string|null; sequence_no:number|null;
  authority_epoch:number; authority_seq:number; authority_mode:string; authority_scope:string; authority_generation:string; authority_updated_at:string;
  target_kind:string|null; target_identity:string|null; replication_schema_version:number|null; replication_state:string|null; checkpoint:string|null;
  replication_pending_count:number|null; actual_pending_count:number|null; retry_count:number|null; last_attempt_at:string|null; last_success_at:string|null;
  last_error_class:string|null; last_error:string|null; replication_updated_at:string|null;
  online_recent_devices:number|null; // S36_SERVICE_ONLINE_TELEMETRY
}'''
if old not in s: raise SystemExit('S36 StatusRow anchor missing')
s=s.replace(old,new,1)

oldq='''      r.target_kind,r.target_identity,r.schema_version AS replication_schema_version,r.state AS replication_state,r.checkpoint,r.pending_count AS replication_pending_count,r.retry_count,r.last_attempt_at,r.last_success_at,r.last_error_class,r.last_error,r.updated_at AS replication_updated_at,
      (SELECT COUNT(*) FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')) AS actual_pending_count
    FROM authority_state a CROSS JOIN recent LEFT JOIN replication_status r ON r.singleton_id=1 WHERE a.singleton_id=1 ORDER BY recent.sequence_no DESC`;'''
newq='''      r.target_kind,r.target_identity,r.schema_version AS replication_schema_version,r.state AS replication_state,r.checkpoint,r.pending_count AS replication_pending_count,r.retry_count,r.last_attempt_at,r.last_success_at,r.last_error_class,r.last_error,r.updated_at AS replication_updated_at,
      (SELECT COUNT(*) FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')) AS actual_pending_count,
      (SELECT COUNT(DISTINCT device_id) FROM client_devices WHERE last_online_at IS NOT NULL AND last_online_at>=?1) AS online_recent_devices
    FROM authority_state a CROSS JOIN recent LEFT JOIN replication_status r ON r.singleton_id=1 WHERE a.singleton_id=1 ORDER BY recent.sequence_no DESC`;'''
if oldq not in s: raise SystemExit('S36 sync status query anchor missing')
s=s.replace(oldq,newq,1)

oldbatch='''  const results=await env.DB.batch([env.DB.prepare(q),env.DB.prepare(heartbeat).bind(auth.device_id,auth.login_id,now,cutoff)]),rows=(results[0]?.results??[]) as unknown as StatusRow[],first=rows[0];
  if(!first)throw new CoreError("AUTHORITY_STATE_MISSING","INTEGRITY",503,false);const {authority,replication}=statusParts(first),dates=rows.map(r=>({business_date:r.business_date,sequence_no:r.sequence_no}));
  return json({ok:true,authority,server_seq:first.authority_seq,service_generation:first.authority_generation,business_dates:dates,replication,realtime:true,delta_endpoint:"/v1/delta",ws_endpoint:"/v1/realtime"});'''
newbatch='''  const onlineCutoff=new Date(Date.now()-90_000).toISOString();
  const results=await env.DB.batch([env.DB.prepare(q).bind(onlineCutoff),env.DB.prepare(heartbeat).bind(auth.device_id,auth.login_id,now,cutoff)]),rows=(results[0]?.results??[]) as unknown as StatusRow[],first=rows[0];
  if(!first)throw new CoreError("AUTHORITY_STATE_MISSING","INTEGRITY",503,false);const {authority,replication}=statusParts(first),dates=rows.map(r=>({business_date:r.business_date,sequence_no:r.sequence_no}));
  const realtimeBusinessDate=String(first.business_date||"");let realtimeConnections=0;
  if(realtimeBusinessDate){try{const hub=env.REALTIME_HUB.getByName(`business:${realtimeBusinessDate}`) as unknown as {connectionCount():Promise<number>};realtimeConnections=Number(await hub.connectionCount())||0;}catch(err){console.log(JSON.stringify({level:"warn",kind:"realtime_count_failed",error:String(err)}));}}
  return json({ok:true,authority,server_seq:first.authority_seq,service_generation:first.authority_generation,business_dates:dates,replication,realtime:true,realtime_connections:realtimeConnections,realtime_business_date:realtimeBusinessDate,online_recent_devices:Number(first.online_recent_devices??0),online_window_seconds:90,delta_endpoint:"/v1/delta",ws_endpoint:"/v1/realtime"});'''
if oldbatch not in s: raise SystemExit('S36 syncStatus return anchor missing')
s=s.replace(oldbatch,newbatch,1)
P.write_text(s,encoding='utf-8')
for x in [MARK,'realtime_connections','online_recent_devices','online_window_seconds:90','connectionCount():Promise<number>']:
    if x not in P.read_text(encoding='utf-8'): raise SystemExit('S36 service contract missing: '+x)
print('Applied S36 service online telemetry')
