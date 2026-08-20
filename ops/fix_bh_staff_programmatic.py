from pathlib import Path

p = Path('google-apps-script/PICK_PACK_API.gs')
s = p.read_text()
start = s.index('function ppStaffUpsert_(auth,body){')
mid = s.index('\nfunction ppStaffDelete_(auth,body){', start)
end = s.index('\nfunction ppAuthenticate_(body)', mid)
up = s[start:mid]
de = s[mid:end]

if 'ppBaoHangBridgeNotifyServiceStaffMutation_' not in up:
    raise RuntimeError('UPSERT_BRIDGE_MISSING')
if 'ppBaoHangBridgeNotifyServiceStaffMutation_' not in de:
    raise RuntimeError('DELETE_BRIDGE_MISSING')

up_anchor = "const bridge=ppBaoHangBridgeNotifyServiceStaffMutation_(eventId,row,oldCode,'UPSERT');"
de_anchor = "const bridge=ppBaoHangBridgeNotifyServiceStaffMutation_(eventId,row,mnv,'DELETE');"
if up_anchor not in up or de_anchor not in de:
    raise RuntimeError('BRIDGE_CALL_ANCHOR_MISSING')
if 'SpreadsheetApp.flush();' not in up:
    up = up.replace(up_anchor, 'SpreadsheetApp.flush();' + up_anchor, 1)
if 'SpreadsheetApp.flush();' not in de:
    de = de.replace(de_anchor, 'SpreadsheetApp.flush();' + de_anchor, 1)

p.write_text(s[:start] + up + de + s[end:])

bridge = Path('google-apps-script/BAO_HANG_STAFF_BRIDGE.gs').read_text()
if "HMAC_PROP: 'STAFF_BRIDGE_HMAC_SECRET'" not in bridge:
    raise RuntimeError('HMAC_SENDER_MISSING')
if 'function ppBaoHangBridgeHmacHex_' not in bridge:
    raise RuntimeError('HMAC_FUNCTION_MISSING')
if 'ScriptApp.getOAuthToken()' in bridge:
    raise RuntimeError('OAUTH_SENDER_NOT_RETIRED')
