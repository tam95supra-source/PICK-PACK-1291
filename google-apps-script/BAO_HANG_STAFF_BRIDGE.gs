/*
 * PICK PACK 1291 -> BÁO HÀNG 1291 staff event bridge.
 * Source-driven only: DỮ LIỆU THEO NGÀY emits a small event when DANH SÁCH NHÂN SỰ changes.
 * No Báo hàng secret is stored here. Receiver authenticates the trigger owner's Google OAuth identity
 * and then re-reads the trusted source Sheet before applying any backend mutation.
 */

const PP_BH_STAFF_BRIDGE = Object.freeze({
  SOURCE_ID: '1E7ZWz-4eMcBliQxDYBVoogIoeSYyiaXGwj0I6mbMm78',
  SOURCE_TAB: 'DANH SÁCH NHÂN SỰ',
  TARGET_URL: 'https://script.google.com/macros/s/AKfycbwb8Hcdg7tp0jqHLZU6kW5hkEclDC9d29DGvPuwcxvZbR9t9xnrWzaIYe8UZET-D_yI/exec',
  RELEVANT_COLUMNS: [1, 2, 4, 5, 6],
  SNAPSHOT_PROP: 'PP_BH_STAFF_ROW_CODES_V1',
  PENDING_PROP: 'PP_BH_STAFF_PENDING_V1',
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
