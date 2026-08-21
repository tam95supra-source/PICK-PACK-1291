/* Pick Pack 1291 M2 Service migration control plane.
 * Service-first control plane: Worker/D1 is normal-mode authority; GAS provides discovery,
 * compatibility, fallback and controlled recovery/failback fencing.
 */

function ppM2Props_(){return PropertiesService.getScriptProperties();}
function ppM2Mode_(){return String(ppM2Props_().getProperty('PP_M2_AUTHORITY_MODE')||'GOOGLE_FALLBACK');}
function ppM2Epoch_(){return Number(ppM2Props_().getProperty('PP_M2_AUTHORITY_EPOCH')||'1');}
function ppM2Generation_(){return String(ppM2Props_().getProperty('PP_M2_SERVICE_GENERATION')||'legacy-gas-production');}
function ppM2ServiceUrl_(){return String(ppM2Props_().getProperty('PP_M2_SERVICE_URL')||'').replace(/\/+$/,'');}
function ppM2BridgeSecret_(){return String(ppM2Props_().getProperty('PP_M2_GAS_BRIDGE_SECRET')||'');}
function ppM2ValidServiceUrl_(v){return /^https:\/\/[A-Za-z0-9._-]+(?:\.workers\.dev|\.pages\.dev)(?:\/.*)?$/.test(String(v||''));}

// Discovery is a hot path used by Android, CI and recovery observers. Read the Script
// Properties store once per request so authority/generation/seq are from one coherent snapshot.
// Do not add a TTL cache here: authority transitions must become visible immediately.
function ppM2StateSnapshot_(){
  const all=ppM2Props_().getProperties();
  return {
    mode:String(all.PP_M2_AUTHORITY_MODE||'GOOGLE_FALLBACK'),
    epoch:Number(all.PP_M2_AUTHORITY_EPOCH||'1'),
    generation:String(all.PP_M2_SERVICE_GENERATION||'legacy-gas-production'),
    serviceUrl:String(all.PP_M2_SERVICE_URL||'').replace(/\/+$/,''),
    fallbackSeq:Number(all.PP_M2_FALLBACK_SEQ||'0'),
    scope:String(all.PP_M2_AUTHORITY_SCOPE||'PRODUCTION'),
    bridgeConfigured:!!String(all.PP_M2_GAS_BRIDGE_SECRET||''),
  };
}

function ppM2Discovery_(body){
  const s=ppM2StateSnapshot_();
  return {
    ok:true,
    discovery_version:2,
    service_url:ppM2ValidServiceUrl_(s.serviceUrl)?s.serviceUrl:'',
    authority_mode:s.mode,
    authority:{authority_epoch:s.epoch,authority_seq:s.fallbackSeq,mode:s.mode,scope:s.scope,service_generation:s.generation},
    service_generation:s.generation,
    gas_fallback:true,
    legacy_bridge:true,
    cutover_configured:s.mode==='SERVICE_PRIMARY'&&ppM2ValidServiceUrl_(s.serviceUrl)&&s.bridgeConfigured,
    business_date:ppBusinessIso_(),
    app_channel:String((body||{})._app_channel||''),
  };
}

function ppM2ServiceFetch_(path,payload){
  const url=ppM2ServiceUrl_(),secret=ppM2BridgeSecret_();
  if(!ppM2ValidServiceUrl_(url)||!secret)throw new Error('SERVICE_PRIMARY_NOT_CONFIGURED');
  const response=UrlFetchApp.fetch(url+path,{
    method:'post',contentType:'application/json',muteHttpExceptions:true,
    headers:{'x-gas-bridge-secret':secret},payload:JSON.stringify(payload||{})
  });
  const code=response.getResponseCode(),text=response.getContentText()||'{}';let json={};
  try{json=JSON.parse(text);}catch(_){json={ok:false,error:'SERVICE_BAD_JSON'};}
  return {code:code,json:json};
}

function ppM2BridgeActor_(auth,body){return {login_id:String(auth.login_id||auth.login||''),role:String(auth.role||'USER'),display_name:String(auth.display_name||auth.login_id||''),device_id:String((body||{})._device_id||'gas-legacy')};}
function ppM2SanitizePayload_(value){if(Array.isArray(value))return value.map(ppM2SanitizePayload_);if(value&&typeof value==='object'){const out={};Object.keys(value).forEach(function(k){if(/(^|_)(token|password|verifier|secret|authorization|cookie|oauth)(_|$)/i.test(k))return;out[k]=ppM2SanitizePayload_(value[k]);});return out;}return value;}
function ppM2BridgeMutation_(auth,body,action){
  const eventId=String(body.event_id||Utilities.getUuid());
  const req={actor:ppM2BridgeActor_(auth,body),mutation:{action:action,event_id:eventId,business_date:String(body.business_date||ppBusinessIso_()),device_id:String(body._device_id||'gas-legacy'),payload:ppM2SanitizePayload_(body)}};
  const r=ppM2ServiceFetch_('/internal/legacy-bridge',req);
  if(r.code>=200&&r.code<300&&r.json&&r.json.ok){ppM2ClearServiceFailure_();return r.json;}
  const err=(r.json&&r.json.error&&(r.json.error.code||r.json.error))||('HTTP_'+r.code);throw new Error('SERVICE_BRIDGE:'+err);
}

function ppM2ClearServiceFailure_(){ppM2Props_().deleteProperty('PP_M2_SERVICE_FAIL');ppM2Props_().deleteProperty('PP_M2_SERVICE_FAIL_AT');}
function ppM2RegisterServiceFailure_(){
  const p=ppM2Props_(),now=Date.now(),oldAt=Number(p.getProperty('PP_M2_SERVICE_FAIL_AT')||'0'),old=Number(p.getProperty('PP_M2_SERVICE_FAIL')||'0');
  const count=(oldAt&&now-oldAt<15000)?old+1:1;p.setProperty('PP_M2_SERVICE_FAIL',String(count));p.setProperty('PP_M2_SERVICE_FAIL_AT',String(now));return count;
}

function ppM2ClaimFallback_(reason){
  const lock=LockService.getScriptLock();if(!lock.tryLock(5000))throw new Error('FAILOVER_BUSY_RETRY');
  try{
    const p=ppM2Props_(),mode=String(p.getProperty('PP_M2_AUTHORITY_MODE')||'GOOGLE_FALLBACK');
    if(mode==='GOOGLE_FALLBACK')return {mode:mode,authority_epoch:ppM2Epoch_()};
    if(mode!=='SERVICE_PRIMARY')throw new Error('FAILOVER_MODE_INVALID:'+mode);
    const next=ppM2Epoch_()+1;p.setProperty('PP_M2_AUTHORITY_EPOCH',String(next));p.setProperty('PP_M2_AUTHORITY_MODE','GOOGLE_FALLBACK');p.setProperty('PP_M2_FALLBACK_SEQ','0');p.setProperty('PP_M2_FALLBACK_STARTED_AT',new Date().toISOString());p.setProperty('PP_M2_FALLBACK_REASON',String(reason||'SERVICE_UNAVAILABLE').slice(0,300));
    return {mode:'GOOGLE_FALLBACK',authority_epoch:next};
  } finally {lock.releaseLock();}
}

function ppM2FallbackSheet_(){
  const ss=ppSs_(),name='__PP_M2_FALLBACK_EVENTS';let sh=ss.getSheetByName(name);
  const header=['event_id','authority_epoch','authority_seq','service_generation','action','business_date','actor','role','device_id','occurred_at','payload_json','checksum','ingest_status'];
  if(!sh){sh=ss.insertSheet(name);sh.getRange(1,1,1,header.length).setValues([header]);sh.hideSheet();}
  else {const got=sh.getRange(1,1,1,header.length).getDisplayValues()[0];if(JSON.stringify(got)!==JSON.stringify(header))throw new Error('FALLBACK_SCHEMA_DRIFT');}
  return sh;
}
function ppM2Hex_(bytes){return bytes.map(function(b){return ('0'+((b+256)%256).toString(16)).slice(-2);}).join('');}
function ppM2RecordFallback_(auth,body,action,result){
  const lock=LockService.getScriptLock();if(!lock.tryLock(10000))throw new Error('FALLBACK_LEDGER_BUSY');
  try{
    const p=ppM2Props_(),seq=Number(p.getProperty('PP_M2_FALLBACK_SEQ')||'0')+1;p.setProperty('PP_M2_FALLBACK_SEQ',String(seq));
    const eventId=String(body.event_id||(result&&result.result&&result.result.event_id)||Utilities.getUuid()),date=String(body.business_date||ppBusinessIso_()),at=new Date().toISOString(),payload=JSON.stringify(ppM2SanitizePayload_(body||{})),raw=[eventId,ppM2Epoch_(),seq,ppM2Generation_(),action,date,String(auth.login_id||''),String(auth.role||'USER'),String(body._device_id||''),at,payload].join('|');
    const checksum=ppM2Hex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,raw,Utilities.Charset.UTF_8));
    ppM2FallbackSheet_().appendRow([eventId,ppM2Epoch_(),seq,ppM2Generation_(),action,date,String(auth.login_id||''),String(auth.role||'USER'),String(body._device_id||''),at,payload,checksum,'PENDING']);
    return {event_id:eventId,authority_epoch:ppM2Epoch_(),authority_seq:seq,checksum:checksum};
  } finally {lock.releaseLock();}
}

function ppM2OperationalRoute_(auth,body,action,fallbackFn){
  const mode=ppM2Mode_();
  if(mode==='RECONCILING')return {ok:false,error:'RECONCILING_RETRY',retryable:true};
  if(mode==='OFFLINE_LOCAL')return {ok:false,error:'OFFLINE_LOCAL_NO_SERVER_WRITES',retryable:true};
  if(mode==='SERVICE_PRIMARY'){
    if(!ppM2ValidServiceUrl_(ppM2ServiceUrl_())||!ppM2BridgeSecret_())return {ok:false,error:'SERVICE_PRIMARY_NOT_CONFIGURED',retryable:false};
    try{return ppM2BridgeMutation_(auth,body,action);}catch(err){
      const failures=ppM2RegisterServiceFailure_();
      if(failures<2)return {ok:false,error:'SERVICE_TEMP_UNAVAILABLE_RETRY',retryable:true};
      ppM2ClaimFallback_(String(err));
    }
  }
  if(ppM2Mode_()!=='GOOGLE_FALLBACK')return {ok:false,error:'WRITE_AUTHORITY_UNAVAILABLE',retryable:true};
  const result=fallbackFn();
  if(result&&result.ok!==false){const fence=ppM2RecordFallback_(auth,body,action,result);result.authority=fence;result.projection='GOOGLE_FALLBACK';}
  return result;
}

function ppM2BeginReconcile_(auth,body){
  if(!auth||String(auth.role)!=='SUPERADMIN')return {ok:false,error:'SUPERADMIN_REQUIRED'};
  if(String(body.confirmation||'')!=='OWNER_LOCKED_M2_FAILBACK')return {ok:false,error:'FAILBACK_CONFIRMATION_REQUIRED'};
  const lock=LockService.getScriptLock();if(!lock.tryLock(5000))return {ok:false,error:'RECONCILE_BUSY'};
  try{
    const p=ppM2Props_(),mode=ppM2Mode_();if(mode!=='GOOGLE_FALLBACK')return {ok:false,error:'RECONCILE_REQUIRES_GOOGLE_FALLBACK',mode:mode};
    p.setProperty('PP_M2_AUTHORITY_MODE','RECONCILING');p.setProperty('PP_M2_RECONCILE_STARTED_AT',new Date().toISOString());p.setProperty('PP_M2_RECONCILE_BY',String(auth.login_id||''));
    return {ok:true,authority_mode:'RECONCILING',authority_epoch:ppM2Epoch_(),fallback_seq:Number(p.getProperty('PP_M2_FALLBACK_SEQ')||'0')};
  } finally {lock.releaseLock();}
}

function ppM2FlushFallbackInbox_(){
  const mode=ppM2Mode_();if((mode!=='GOOGLE_FALLBACK'&&mode!=='RECONCILING')||!ppM2ValidServiceUrl_(ppM2ServiceUrl_())||!ppM2BridgeSecret_())return {ok:false,error:'FALLBACK_FLUSH_NOT_READY',mode:mode};
  const sh=ppM2FallbackSheet_(),last=sh.getLastRow();if(last<2)return {ok:true,sent:0,pending:0};
  const rows=sh.getRange(2,1,last-1,13).getDisplayValues();let sent=0,pending=0;
  rows.forEach(function(r,i){if(String(r[12]||'')!=='PENDING')return;pending++;const payload={event_id:r[0],authority_epoch:Number(r[1]),authority_seq:Number(r[2]),service_generation:r[3],event:{action:r[4],business_date:r[5],actor:r[6],role:r[7],device_id:r[8],occurred_at:r[9],payload_json:r[10]},checksum:r[11]};try{const x=ppM2ServiceFetch_('/internal/fallback/ingest',payload);if(x.code>=200&&x.code<300&&x.json&&x.json.ok){sh.getRange(i+2,13).setValue('INGESTED');sent++;pending--;}}catch(_){}});
  return {ok:pending===0,sent:sent,pending:pending,authority_epoch:ppM2Epoch_()};
}

function ppM2CompleteFailback_(auth,body){
  if(!auth||String(auth.role)!=='SUPERADMIN')return {ok:false,error:'SUPERADMIN_REQUIRED'};
  if(String(body.confirmation||'')!=='OWNER_LOCKED_M2_FAILBACK')return {ok:false,error:'FAILBACK_CONFIRMATION_REQUIRED'};
  const nextEpoch=Number(body.authority_epoch||0),generation=String(body.service_generation||''),url=String(body.service_url||ppM2ServiceUrl_());
  if(ppM2Mode_()!=='RECONCILING')return {ok:false,error:'FAILBACK_COMPLETE_REQUIRES_RECONCILING',mode:ppM2Mode_()};
  if(nextEpoch<=ppM2Epoch_()||!generation||!ppM2ValidServiceUrl_(url)||!ppM2BridgeSecret_())return {ok:false,error:'FAILBACK_TARGET_INVALID'};
  const sh=ppM2FallbackSheet_(),last=sh.getLastRow();if(last>=2){const statuses=sh.getRange(2,13,last-1,1).getDisplayValues().flat();if(statuses.some(function(x){return String(x)==='PENDING';}))return {ok:false,error:'FALLBACK_EVENTS_NOT_INGESTED'};}
  const lock=LockService.getScriptLock();if(!lock.tryLock(5000))return {ok:false,error:'FAILBACK_COMPLETE_BUSY'};
  try{
    const p=ppM2Props_();p.setProperty('PP_M2_SERVICE_URL',url.replace(/\/+$/,''));p.setProperty('PP_M2_AUTHORITY_EPOCH',String(nextEpoch));p.setProperty('PP_M2_AUTHORITY_MODE','SERVICE_PRIMARY');p.setProperty('PP_M2_SERVICE_GENERATION',generation);p.setProperty('PP_M2_FALLBACK_SEQ','0');p.setProperty('PP_M2_FAILBACK_COMPLETED_AT',new Date().toISOString());ppM2ClearServiceFailure_();
    return {ok:true,authority_mode:'SERVICE_PRIMARY',authority_epoch:nextEpoch,service_generation:generation,service_url:url};
  } finally {lock.releaseLock();}
}
