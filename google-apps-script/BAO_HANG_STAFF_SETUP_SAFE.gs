/*
 * BÁO HÀNG STAFF BRIDGE — SAFE INSTALLER
 * One-time owner authorization only. It validates the source, installs triggers,
 * and stores a row->employee snapshot. It intentionally does NOT reconcile or
 * upsert any Báo hàng user during setup.
 */
function setupBaoHangStaffBridgeSafe() {
  const ss = SpreadsheetApp.openById(PP_BH_STAFF_BRIDGE.SOURCE_ID);
  if (ss.getId() !== PP_BH_STAFF_BRIDGE.SOURCE_ID) throw new Error('BH_BRIDGE_SOURCE_ID_MISMATCH');
  const sheet = ss.getSheetByName(PP_BH_STAFF_BRIDGE.SOURCE_TAB);
  if (!sheet) throw new Error('BH_BRIDGE_SOURCE_TAB_MISSING');

  const lastRow = Math.max(1, sheet.getLastRow());
  const seen = {};
  if (lastRow >= 2) {
    sheet.getRange(2, 1, lastRow - 1, 1).getDisplayValues().forEach(function(row, i) {
      const code = String(row[0] || '').trim();
      if (!code) return;
      const key = code.toLowerCase();
      if (seen[key]) throw new Error('BH_BRIDGE_DUPLICATE_EMPLOYEE_CODE:' + code + ':ROWS_' + seen[key] + '_' + (i + 2));
      seen[key] = i + 2;
    });
  }

  ScriptApp.getProjectTriggers().forEach(function(t) {
    const h = String(t.getHandlerFunction() || '');
    if (h === 'ppBaoHangStaffBridgeEdit' || h === 'ppBaoHangStaffBridgeChange' || h === 'ppBaoHangStaffBridgeRetry') {
      ScriptApp.deleteTrigger(t);
    }
  });

  ScriptApp.newTrigger('ppBaoHangStaffBridgeEdit')
    .forSpreadsheet(PP_BH_STAFF_BRIDGE.SOURCE_ID)
    .onEdit()
    .create();
  ScriptApp.newTrigger('ppBaoHangStaffBridgeChange')
    .forSpreadsheet(PP_BH_STAFF_BRIDGE.SOURCE_ID)
    .onChange()
    .create();

  const snapshot = ppBaoHangBridgeSaveSnapshot_();
  const props = PropertiesService.getScriptProperties();
  props.deleteProperty(PP_BH_STAFF_BRIDGE.PENDING_PROP);
  props.deleteProperty('PP_BH_STAFF_LAST_ERROR');
  props.setProperty('PP_BH_STAFF_SAFE_INSTALLED_AT', new Date().toISOString());

  return {
    ok: true,
    mode: 'SOURCE_DRIVEN_DELTA_V1',
    installer: 'SAFE_NO_RECONCILE',
    edit_trigger: true,
    change_trigger: true,
    snapshot_rows: Object.keys(snapshot).length,
    backend_mutations: 0,
    recovery_ping: false
  };
}
