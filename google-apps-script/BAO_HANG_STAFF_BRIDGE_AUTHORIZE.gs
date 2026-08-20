/* Owner authorization helper for the signed PICK PACK -> BÁO HÀNG staff bridge.
 * No data mutation. It only performs a health ping so Google can grant script.external_request.
 */
function authorizeBaoHangStaffBridgeTransport() {
  const res = UrlFetchApp.fetch(PP_BH_STAFF_BRIDGE.TARGET_URL, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({action:'ping'}),
    followRedirects: true,
    muteHttpExceptions: true
  });
  const code = res.getResponseCode();
  let out = {};
  try { out = JSON.parse(res.getContentText() || '{}'); } catch (_) {}
  if (code < 200 || code >= 300 || out.ok !== true || String(out.project || '') !== 'bao-hang-1291') {
    throw new Error('BAO_HANG_BRIDGE_AUTHORIZATION_PING_FAILED_' + code);
  }
  return {ok:true,project:'bao-hang-1291',transport:'UrlFetchApp'};
}
