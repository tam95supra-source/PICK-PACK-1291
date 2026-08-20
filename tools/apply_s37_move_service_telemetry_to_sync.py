#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S37_SERVICE_TELEMETRY_SYNC_ONLY'
s=P.read_text(encoding='utf-8')
if MARK in s:
    print('S37 already applied');raise SystemExit(0)

lines=s.splitlines()
out=[]
removed_box=False
removed_call=False
for line in lines:
    if 'val serviceBox=column(surface)' in line and 'SERVICE • đang đọc trạng thái' in line:
        removed_box=True
        continue
    if 'api.call("sync_status",JSONObject())' in line and 'screenState!="HISTORY"' in line and 'realtime_connections' in line and 'online_recent_devices' in line:
        removed_call=True
        continue
    out.append(line)
s='\n'.join(out)+'\n'
if not removed_box: raise SystemExit('S37 history serviceBox anchor missing')
if not removed_call: raise SystemExit('S37 history telemetry call anchor missing')

sync_anchor='    private fun syncScreen(){\n'
if sync_anchor not in s: raise SystemExit('S37 syncScreen anchor missing')
s=s.replace(sync_anchor,sync_anchor+'        // S37_SERVICE_TELEMETRY_SYNC_ONLY: Service diagnostics belong to Đồng bộ, never Lịch sử.\n',1)

authority_anchor='                    box.addView(section("Authority canonical"));box.addView(details(listOf('
if authority_anchor not in s: raise SystemExit('S37 sync authority anchor missing')
telemetry='''                    box.addView(section("Service realtime"));box.addView(details(listOf(
                        "Realtime đang nối" to j.optInt("realtime_connections",-1).let{if(it>=0)it.toString() else "—"},
                        "Online gần đây ≤${j.optInt("online_window_seconds",90)}s" to j.optInt("online_recent_devices",-1).let{if(it>=0)it.toString() else "—"},
                        "Ngày realtime" to j.optString("realtime_business_date").ifBlank{"—"},
                        "Realtime endpoint" to if(j.optBoolean("realtime",false))"Sẵn sàng" else "Không báo sẵn sàng"
                    )))
'''
s=s.replace(authority_anchor,telemetry+authority_anchor,1)

P.write_text(s,encoding='utf-8')
o=P.read_text(encoding='utf-8')

def block(sig,next_sig):
    a=o.find('    private fun '+sig)
    b=o.find('    private fun '+next_sig,a+1)
    if a<0 or b<0: raise SystemExit('S37 block anchor missing '+sig)
    return o[a:b]

hist=block('historyScreen(){','historyTimeline(')
sync_start=o.find('    private fun syncScreen(){')
if sync_start<0: raise SystemExit('S37 sync block missing')
sync_end=o.find('\n    private fun ',sync_start+20)
sync=o[sync_start:sync_end if sync_end>0 else len(o)]
for bad in ['serviceBox','realtime_connections','online_recent_devices','SERVICE • Hoạt động']:
    if bad in hist: raise SystemExit('S37 telemetry remains in History: '+bad)
for need in [MARK,'Service realtime','Realtime đang nối','Online gần đây ≤','realtime_connections','online_recent_devices','Service RTT','Authority canonical','Nhân bản Google']:
    if need not in sync: raise SystemExit('S37 telemetry missing from Sync: '+need)
print('Applied S37: moved Service telemetry from History to Sync only')
