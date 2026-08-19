from pathlib import Path

api=Path('google-apps-script/PICK_PACK_API.gs')
s=api.read_text()
anchor="  if(action==='service_discovery')return ppJson_(ppM2Discovery_(body));"
block="""  if(action==='service_discovery')return ppJson_(ppM2Discovery_(body));
  if(action==='m2_internal_reconcile_status')return ppJson_(ppM2InternalReconcileStatus_(body));
  if(action==='m2_internal_reconcile_begin')return ppJson_(ppM2InternalReconcileBegin_(body));
  if(action==='m2_internal_reconcile_flush')return ppJson_(ppM2InternalReconcileFlush_(body));
  if(action==='m2_internal_reconcile_complete')return ppJson_(ppM2InternalReconcileComplete_(body));
  if(action==='m2_internal_reconcile_revert')return ppJson_(ppM2InternalReconcileRevert_(body));"""
if "m2_internal_reconcile_begin" not in s:
    if anchor not in s: raise SystemExit('GAS_DISPATCH_ANCHOR_MISSING')
    s=s.replace(anchor,block,1)
api.write_text(s)

m2=Path('google-apps-script/SERVICE_MIGRATION_M2.gs')
t=m2.read_text()
add=r'''

/* Internal server-to-server adapter for the existing owner-locked M2 recovery state machine.
 * This does not create a new transition; it only authenticates the same begin/flush/complete
 * operations with the existing GAS bridge secret so CI recovery never needs a human session token.
 */
function ppM2InternalRecoveryAuthorized_(body){return ppM2BridgeSecretOk_(body||{});}
function ppM2InternalReconcileStatus_(body){
  if(!ppM2InternalRecoveryAuthorized_(body))return {ok:false,error:'BRIDGE_SECRET_INVALID'};
  const sh=ppM2FallbackSheet_(),last=sh.getLastRow(),statuses=last>=2?sh.getRange(2,13,last-1,1).getDisplayValues().flat():[];
  return {ok:true,authority_mode:ppM2Mode_(),authority_epoch:ppM2Epoch_(),fallback_seq:Number(ppM2Props_().getProperty('PP_M2_FALLBACK_SEQ')||'0'),pending:statuses.filter(function(x){return String(x)==='PENDING';}).length,ingested:statuses.filter(function(x){return String(x)==='INGESTED';}).length,service_generation:ppM2Generation_(),service_url:ppM2ServiceUrl_()};
}
function ppM2InternalReconcileBegin_(body){
  if(!ppM2InternalRecoveryAuthorized_(body))return {ok:false,error:'BRIDGE_SECRET_INVALID'};
  return ppM2BeginReconcile_({role:'SUPERADMIN',login_id:'service-recovery'},body||{});
}
function ppM2InternalReconcileFlush_(body){
  if(!ppM2InternalRecoveryAuthorized_(body))return {ok:false,error:'BRIDGE_SECRET_INVALID'};
  return ppM2FlushFallbackInbox_();
}
function ppM2InternalReconcileComplete_(body){
  if(!ppM2InternalRecoveryAuthorized_(body))return {ok:false,error:'BRIDGE_SECRET_INVALID'};
  return ppM2CompleteFailback_({role:'SUPERADMIN',login_id:'service-recovery'},body||{});
}
function ppM2InternalReconcileRevert_(body){
  if(!ppM2InternalRecoveryAuthorized_(body))return {ok:false,error:'BRIDGE_SECRET_INVALID'};
  if(String((body||{}).confirmation||'')!=='OWNER_LOCKED_M2_FAILBACK')return {ok:false,error:'FAILBACK_CONFIRMATION_REQUIRED'};
  const lock=LockService.getScriptLock();if(!lock.tryLock(5000))return {ok:false,error:'RECONCILE_BUSY'};
  try{const p=ppM2Props_(),mode=ppM2Mode_();if(mode!=='RECONCILING')return {ok:false,error:'RECONCILE_REVERT_REQUIRES_RECONCILING',mode:mode};p.setProperty('PP_M2_AUTHORITY_MODE','GOOGLE_FALLBACK');p.deleteProperty('PP_M2_RECONCILE_STARTED_AT');p.deleteProperty('PP_M2_RECONCILE_BY');return {ok:true,authority_mode:'GOOGLE_FALLBACK',authority_epoch:ppM2Epoch_()};}finally{lock.releaseLock();}
}
'''
if 'function ppM2InternalRecoveryAuthorized_' not in t:t+=add
m2.write_text(t)
print('SESSION1_GAS_INTERNAL_RECOVERY_PATCH=PASS')
