from pathlib import Path

p=Path('google-apps-script/PICK_PACK_API.gs')
s=p.read_text()
start=s.index('function ppStaffUpsert_(auth,body){')
mid=s.index('\nfunction ppStaffDelete_(auth,body){',start)
end=s.index('\nfunction ppAuthenticate_(body)',mid)
up=s[start:mid]
de=s[mid:end]
anchor="const sh=ppSheet_(PP.STAFF),vals=sh.getDataRange().getDisplayValues();let row=0;for(let i=1;i<vals.length;i++){if(String(vals[i][0]||'').trim()===mnv){row=i+1;break;}}"
if "ppBaoHangBridgeNotifyServiceStaffMutation_" not in up:
    assert anchor in up
    up=up.replace(anchor,anchor+"const oldCode=row?String(vals[row-1][0]||'').trim():'';",1)
    old="else{const target=sh.getLastRow()+1;if(target>2)sh.getRange(target-1,1,1,12).copyTo(sh.getRange(target,1,1,12),SpreadsheetApp.CopyPasteType.PASTE_FORMAT,false);sh.getRange(target,1,1,12).setValues([data]);}"
    new="else{const target=sh.getLastRow()+1;if(target>2)sh.getRange(target-1,1,1,12).copyTo(sh.getRange(target,1,1,12),SpreadsheetApp.CopyPasteType.PASTE_FORMAT,false);sh.getRange(target,1,1,12).setValues([data]);row=target;}"
    assert old in up
    up=up.replace(old,new,1)
    oldret="ppMarkMasterMutation_(eventId);const rev=ppBumpRevision_();const master=ppBumpMasterRevision_();return {ok:true,result:{event_id:eventId,revision:rev,master_revision:master}};"
    newret="ppMarkMasterMutation_(eventId);const rev=ppBumpRevision_();const master=ppBumpMasterRevision_();const bridge=ppBaoHangBridgeNotifyServiceStaffMutation_(eventId,row,oldCode,'UPSERT');return {ok:true,result:{event_id:eventId,revision:rev,master_revision:master,bao_hang_bridge:bridge}};"
    assert oldret in up
    up=up.replace(oldret,newret,1)
if "ppBaoHangBridgeNotifyServiceStaffMutation_" not in de:
    oldret="sh.deleteRow(row);ppMarkMasterMutation_(eventId);const rev=ppBumpRevision_();const master=ppBumpMasterRevision_();return {ok:true,result:{event_id:eventId,revision:rev,master_revision:master}};"
    newret="sh.deleteRow(row);ppMarkMasterMutation_(eventId);const rev=ppBumpRevision_();const master=ppBumpMasterRevision_();const bridge=ppBaoHangBridgeNotifyServiceStaffMutation_(eventId,row,mnv,'DELETE');return {ok:true,result:{event_id:eventId,revision:rev,master_revision:master,bao_hang_bridge:bridge}};"
    assert oldret in de
    de=de.replace(oldret,newret,1)
p.write_text(s[:start]+up+de+s[end:])

b=Path('google-apps-script/BAO_HANG_STAFF_BRIDGE.gs')
bs=b.read_text()
if 'function ppBaoHangBridgeNotifyServiceStaffMutation_(' not in bs:
    bs += r'''

// Programmatic writes (Web/App/service) do not fire Google Sheets onEdit/onChange.
// Emit the same trusted delta bridge explicitly after the source Sheet mutation.
function ppBaoHangBridgeNotifyServiceStaffMutation_(eventId, row, oldCode, changeType) {
  try {
    if (typeof ppBaoHangBridgeSendOrQueue_ !== 'function') return 'UNAVAILABLE';
    const rowNumber = Math.max(2, Number(row || 0));
    const clean = String(eventId || Utilities.getUuid()).replace(/[^A-Za-z0-9._:-]/g, '').slice(0, 90) || Utilities.getUuid();
    const oldCodes = {};
    if (oldCode) oldCodes[String(rowNumber)] = String(oldCode).trim();
    const result = ppBaoHangBridgeSendOrQueue_({
      action: 'staff-source-ping',
      event_id: 'ppstaff-' + clean,
      source_id: PP_BH_STAFF_BRIDGE.SOURCE_ID,
      source_tab: PP_BH_STAFF_BRIDGE.SOURCE_TAB,
      change_type: 'SERVICE_' + String(changeType || 'MUTATION').slice(0, 24),
      row_start: rowNumber,
      row_end: rowNumber,
      col_start: 1,
      col_end: 6,
      old_codes: oldCodes,
      at: new Date().toISOString()
    });
    return result && result.ok ? 'SENT' : (result && result.queued ? 'QUEUED' : 'FAILED');
  } catch (err) {
    console.error('BAO_HANG_STAFF_BRIDGE SERVICE ' + String(err && err.stack || err));
    return 'FAILED';
  }
}
'''

if "HMAC_PROP: 'STAFF_BRIDGE_HMAC_SECRET'" not in bs:
    anchor="  PENDING_PROP: 'PP_BH_STAFF_PENDING_V1',\n"
    assert anchor in bs
    bs=bs.replace(anchor,anchor+"  HMAC_PROP: 'STAFF_BRIDGE_HMAC_SECRET',\n",1)

old_post="""function ppBaoHangBridgePost_(payload) {
  const body = Object.assign({}, payload, {oauth_token: ScriptApp.getOAuthToken()});
  const res = UrlFetchApp.fetch(PP_BH_STAFF_BRIDGE.TARGET_URL, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(body),
    followRedirects: true,
    muteHttpExceptions: true
  });
  const code = res.getResponseCode();
  let out = {};
  try { out = JSON.parse(res.getContentText() || '{}'); } catch (_) {}
  if (code < 200 || code >= 300 || !out.ok) {
    throw new Error('BH_BRIDGE_HTTP_' + code + ':' + String(out.error || res.getContentText() || '').slice(0,250));
  }
  return out;
}
"""
new_post="""function ppBaoHangBridgePost_(payload) {
  const secret = String(PropertiesService.getScriptProperties().getProperty(PP_BH_STAFF_BRIDGE.HMAC_PROP) || '');
  if (secret.length < 32) throw new Error('BH_BRIDGE_HMAC_NOT_CONFIGURED');
  const body = Object.assign({}, payload, {sent_at:new Date().toISOString()});
  body.hmac_sha256 = ppBaoHangBridgeHmacHex_(body, secret);
  const res = UrlFetchApp.fetch(PP_BH_STAFF_BRIDGE.TARGET_URL, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(body),
    followRedirects: true,
    muteHttpExceptions: true
  });
  const code = res.getResponseCode();
  let out = {};
  try { out = JSON.parse(res.getContentText() || '{}'); } catch (_) {}
  if (code < 200 || code >= 300 || !out.ok) {
    throw new Error('BH_BRIDGE_HTTP_' + code + ':' + String(out.error || res.getContentText() || '').slice(0,250));
  }
  return out;
}

function ppBaoHangBridgeCanonical_(payload) {
  const oldCodes = payload.old_codes && typeof payload.old_codes === 'object' && !Array.isArray(payload.old_codes) ? payload.old_codes : {};
  const oldPart = Object.keys(oldCodes).sort(function(a,b){
    const na=Number(a), nb=Number(b);
    if (Number.isFinite(na) && Number.isFinite(nb) && na !== nb) return na-nb;
    return String(a).localeCompare(String(b));
  }).map(function(k){ return String(k) + '=' + String(oldCodes[k] || ''); }).join('&');
  return [String(payload.action || ''),String(payload.event_id || ''),String(payload.source_id || ''),String(payload.source_tab || ''),String(payload.change_type || ''),String(payload.row_start || ''),String(payload.row_end || ''),String(payload.col_start || ''),String(payload.col_end || ''),String(payload.at || ''),String(payload.sent_at || ''),oldPart].join('\\n');
}

function ppBaoHangBridgeHmacHex_(payload, secret) {
  const bytes = Utilities.computeHmacSha256Signature(ppBaoHangBridgeCanonical_(payload), secret, Utilities.Charset.UTF_8);
  return bytes.map(function(b){ return ('0' + ((b + 256) % 256).toString(16)).slice(-2); }).join('');
}
"""
if old_post in bs:
    bs=bs.replace(old_post,new_post,1)
elif 'function ppBaoHangBridgeHmacHex_' not in bs:
    raise RuntimeError('PP_BRIDGE_POST_ANCHOR_NOT_FOUND')

bs=bs.replace(" * No Báo hàng secret is stored here. Receiver authenticates the trigger owner's Google OAuth identity\n * and then re-reads the trusted source Sheet before applying any backend mutation.\n"," * Shared HMAC material is stored only in Apps Script Properties, never in source.\n * Receiver verifies signed metadata and re-reads the trusted source Sheet before backend mutation.\n")
b.write_text(bs)
