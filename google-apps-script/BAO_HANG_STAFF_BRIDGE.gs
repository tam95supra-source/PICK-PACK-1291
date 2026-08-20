/*
 * PICK PACK 1291 -> BÁO HÀNG 1291 staff event bridge.
 * Source-driven only: DỮ LIỆU THEO NGÀY emits a small event when DANH SÁCH NHÂN SỰ changes.
 * Shared HMAC material is stored only in Apps Script Properties, never in source.
 * Receiver verifies signed metadata and re-reads the trusted source Sheet before backend mutation.
 */

const PP_BH_STAFF_BRIDGE = Object.freeze({
  SOURCE_ID: '1E7ZWz-4eMcBliQxDYBVoogIoeSYyiaXGwj0I6mbMm78',
  SOURCE_TAB: 'DANH SÁCH NHÂN SỰ',
  TARGET_URL: 'https://script.google.com/macros/s/AKfycbwb8Hcdg7tp0jqHLZU6kW5hkEclDC9d29DGvPuwcxvZbR9t9xnrWzaIYe8UZET-D_yI/exec',
  RELEVANT_COLUMNS: [1, 2, 4, 5, 6],
  SNAPSHOT_PROP: 'PP_BH_STAFF_ROW_CODES_V1',
  PENDING_PROP: 'PP_BH_STAFF_PENDING_V1',
  HMAC_PROP: 'STAFF_BRIDGE_HMAC_SECRET',
  MAX_PENDING: 30
});

function setupBaoHangStaffBridge() {
  const ss = SpreadsheetApp.openById(PP_BH_STAFF_BRIDGE.SOURCE_ID);
  if (ss.getId() !== PP_BH_STAFF_BRIDGE.SOURCE_ID) throw new Error('BH_BRIDGE_SOURCE_ID_MISMATCH');
  const sheet = ss.getSheetByName(PP_BH_STAFF_BRIDGE.SOURCE_TAB);
  if (!sheet) throw new Error('BH_BRIDGE_SOURCE_TAB_MISSING');

  ScriptApp.getProjectTriggers().forEach(function(t) {
    const h = t.getHandlerFunction();
    if (h === 'ppBaoHangStaffBridgeEdit' || h === 'ppBaoHangStaffBridgeChange' || h === 'ppBaoHangStaffBridgeRetry') {
      ScriptApp.deleteTrigger(t);
    }
  });

  ScriptApp.newTrigger('ppBaoHangStaffBridgeEdit').forSpreadsheet(PP_BH_STAFF_BRIDGE.SOURCE_ID).onEdit().create();
  ScriptApp.newTrigger('ppBaoHangStaffBridgeChange').forSpreadsheet(PP_BH_STAFF_BRIDGE.SOURCE_ID).onChange().create();

  ppBaoHangBridgeSaveSnapshot_();
  const result = ppBaoHangBridgeSendOrQueue_({
    action: 'staff-source-structure-ping',
    event_id: Utilities.getUuid(),
    source_id: PP_BH_STAFF_BRIDGE.SOURCE_ID,
    source_tab: PP_BH_STAFF_BRIDGE.SOURCE_TAB,
    change_type: 'SETUP_RECOVERY',
    at: new Date().toISOString()
  });

  return {
    ok: true,
    mode: 'SOURCE_DRIVEN_DELTA_V1',
    edit_trigger: true,
    change_trigger: true,
    recovery_ping: result
  };
}

function removeBaoHangStaffBridge() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    const h = t.getHandlerFunction();
    if (h === 'ppBaoHangStaffBridgeEdit' || h === 'ppBaoHangStaffBridgeChange' || h === 'ppBaoHangStaffBridgeRetry') {
      ScriptApp.deleteTrigger(t);
    }
  });
  return {ok:true};
}

function getBaoHangStaffBridgeStatus() {
  const handlers = ScriptApp.getProjectTriggers().map(function(t){ return t.getHandlerFunction(); });
  const props = PropertiesService.getScriptProperties();
  let pending = [];
  try { pending = JSON.parse(props.getProperty(PP_BH_STAFF_BRIDGE.PENDING_PROP) || '[]'); } catch (_) {}
  return {
    ok: true,
    source_id: PP_BH_STAFF_BRIDGE.SOURCE_ID,
    source_tab: PP_BH_STAFF_BRIDGE.SOURCE_TAB,
    edit_trigger: handlers.indexOf('ppBaoHangStaffBridgeEdit') >= 0,
    change_trigger: handlers.indexOf('ppBaoHangStaffBridgeChange') >= 0,
    retry_trigger: handlers.indexOf('ppBaoHangStaffBridgeRetry') >= 0,
    pending: pending.length,
    last_ok: props.getProperty('PP_BH_STAFF_LAST_OK') || '',
    last_error: props.getProperty('PP_BH_STAFF_LAST_ERROR') || ''
  };
}

function ppBaoHangStaffBridgeEdit(e) {
  try {
    if (!e || !e.range) return;
    const sheet = e.range.getSheet();
    if (!sheet || sheet.getParent().getId() !== PP_BH_STAFF_BRIDGE.SOURCE_ID || sheet.getName() !== PP_BH_STAFF_BRIDGE.SOURCE_TAB) return;
    if (e.range.getLastRow() <= 1) return;
    if (!ppBaoHangBridgeTouchesRelevant_(e.range)) return;

    const rowStart = Math.max(2, e.range.getRow());
    const rowEnd = Math.max(rowStart, e.range.getLastRow());
    const snapshot = ppBaoHangBridgeLoadSnapshot_();
    const oldCodes = {};
    for (let row = rowStart; row <= rowEnd; row++) {
      const oldCode = String(snapshot[String(row)] || '').trim();
      if (oldCode) oldCodes[String(row)] = oldCode;
    }

    const payload = {
      action: 'staff-source-ping',
      event_id: Utilities.getUuid(),
      source_id: PP_BH_STAFF_BRIDGE.SOURCE_ID,
      source_tab: PP_BH_STAFF_BRIDGE.SOURCE_TAB,
      change_type: 'EDIT',
      row_start: rowStart,
      row_end: rowEnd,
      col_start: e.range.getColumn(),
      col_end: e.range.getLastColumn(),
      old_codes: oldCodes,
      at: new Date().toISOString()
    };

    // Save new row-code state independently of transport success. The queued payload already carries old codes.
    ppBaoHangBridgeRefreshSnapshotRows_(sheet, snapshot, rowStart, rowEnd);
    ppBaoHangBridgeSendOrQueue_(payload);
  } catch (err) {
    ppBaoHangBridgeRecordError_('EDIT', err);
  }
}

function ppBaoHangStaffBridgeChange(e) {
  try {
    const type = String(e && e.changeType || '').toUpperCase();
    if (!type || type === 'EDIT') return;
    ppBaoHangBridgeSendOrQueue_({
      action: 'staff-source-structure-ping',
      event_id: Utilities.getUuid(),
      source_id: PP_BH_STAFF_BRIDGE.SOURCE_ID,
      source_tab: PP_BH_STAFF_BRIDGE.SOURCE_TAB,
      change_type: type,
      at: new Date().toISOString()
    });
    ppBaoHangBridgeSaveSnapshot_();
  } catch (err) {
    ppBaoHangBridgeRecordError_('CHANGE', err);
  }
}

function ppBaoHangStaffBridgeRetry() {
  const props = PropertiesService.getScriptProperties();
  let pending = [];
  try { pending = JSON.parse(props.getProperty(PP_BH_STAFF_BRIDGE.PENDING_PROP) || '[]'); } catch (_) {}
  if (!Array.isArray(pending) || !pending.length) {
    props.deleteProperty(PP_BH_STAFF_BRIDGE.PENDING_PROP);
    ppBaoHangBridgeDeleteRetryTriggers_();
    return {ok:true,pending:0};
  }

  const keep = [];
  pending.slice(0, PP_BH_STAFF_BRIDGE.MAX_PENDING).forEach(function(payload) {
    try { ppBaoHangBridgePost_(payload); }
    catch (err) { keep.push(payload); }
  });
  props.setProperty(PP_BH_STAFF_BRIDGE.PENDING_PROP, JSON.stringify(keep));
  ppBaoHangBridgeDeleteRetryTriggers_();
  if (keep.length) ScriptApp.newTrigger('ppBaoHangStaffBridgeRetry').timeBased().after(60 * 1000).create();
  return {ok:keep.length===0,pending:keep.length};
}

function ppBaoHangBridgeTouchesRelevant_(range) {
  const first = range.getColumn();
  const last = range.getLastColumn();
  return PP_BH_STAFF_BRIDGE.RELEVANT_COLUMNS.some(function(c){ return c >= first && c <= last; });
}

function ppBaoHangBridgeSendOrQueue_(payload) {
  try {
    const result = ppBaoHangBridgePost_(payload);
    PropertiesService.getScriptProperties().setProperty('PP_BH_STAFF_LAST_OK', new Date().toISOString());
    return result;
  } catch (err) {
    ppBaoHangBridgeQueue_(payload);
    ppBaoHangBridgeRecordError_('SEND', err);
    return {ok:false,queued:true,error:String(err && err.message || err).slice(0,300)};
  }
}

function ppBaoHangBridgePost_(payload) {
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
  return [String(payload.action || ''),String(payload.event_id || ''),String(payload.source_id || ''),String(payload.source_tab || ''),String(payload.change_type || ''),String(payload.row_start || ''),String(payload.row_end || ''),String(payload.col_start || ''),String(payload.col_end || ''),String(payload.at || ''),String(payload.sent_at || ''),oldPart].join('\n');
}

function ppBaoHangBridgeHmacHex_(payload, secret) {
  const bytes = Utilities.computeHmacSha256Signature(ppBaoHangBridgeCanonical_(payload), secret, Utilities.Charset.UTF_8);
  return bytes.map(function(b){ return ('0' + ((b + 256) % 256).toString(16)).slice(-2); }).join('');
}

function ppBaoHangBridgeQueue_(payload) {
  const props = PropertiesService.getScriptProperties();
  let pending = [];
  try { pending = JSON.parse(props.getProperty(PP_BH_STAFF_BRIDGE.PENDING_PROP) || '[]'); } catch (_) {}
  if (!Array.isArray(pending)) pending = [];
  const ids = {};
  pending.forEach(function(x){ if (x && x.event_id) ids[String(x.event_id)] = true; });
  if (!ids[String(payload.event_id || '')]) pending.push(payload);
  if (pending.length > PP_BH_STAFF_BRIDGE.MAX_PENDING) pending = pending.slice(-PP_BH_STAFF_BRIDGE.MAX_PENDING);
  props.setProperty(PP_BH_STAFF_BRIDGE.PENDING_PROP, JSON.stringify(pending));
  ppBaoHangBridgeDeleteRetryTriggers_();
  ScriptApp.newTrigger('ppBaoHangStaffBridgeRetry').timeBased().after(60 * 1000).create();
}

function ppBaoHangBridgeDeleteRetryTriggers_() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === 'ppBaoHangStaffBridgeRetry') ScriptApp.deleteTrigger(t);
  });
}

function ppBaoHangBridgeLoadSnapshot_() {
  try {
    const value = PropertiesService.getScriptProperties().getProperty(PP_BH_STAFF_BRIDGE.SNAPSHOT_PROP) || '{}';
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (_) { return {}; }
}

function ppBaoHangBridgeSaveSnapshot_() {
  const sheet = SpreadsheetApp.openById(PP_BH_STAFF_BRIDGE.SOURCE_ID).getSheetByName(PP_BH_STAFF_BRIDGE.SOURCE_TAB);
  const lastRow = Math.max(1, sheet.getLastRow());
  const map = {};
  if (lastRow >= 2) {
    sheet.getRange(2, 1, lastRow - 1, 1).getDisplayValues().forEach(function(r, i) {
      const code = String(r[0] || '').trim();
      if (code) map[String(i + 2)] = code;
    });
  }
  PropertiesService.getScriptProperties().setProperty(PP_BH_STAFF_BRIDGE.SNAPSHOT_PROP, JSON.stringify(map));
  return map;
}

function ppBaoHangBridgeRefreshSnapshotRows_(sheet, map, rowStart, rowEnd) {
  const values = sheet.getRange(rowStart, 1, rowEnd - rowStart + 1, 1).getDisplayValues();
  values.forEach(function(r, i) {
    const row = String(rowStart + i);
    const code = String(r[0] || '').trim();
    if (code) map[row] = code;
    else delete map[row];
  });
  PropertiesService.getScriptProperties().setProperty(PP_BH_STAFF_BRIDGE.SNAPSHOT_PROP, JSON.stringify(map));
}

function ppBaoHangBridgeRecordError_(where, err) {
  PropertiesService.getScriptProperties().setProperty(
    'PP_BH_STAFF_LAST_ERROR',
    JSON.stringify({where:where,error:String(err && err.message || err).slice(0,500),at:new Date().toISOString()})
  );
  console.error('BAO_HANG_STAFF_BRIDGE ' + where + ' ' + String(err && err.stack || err));
}


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
