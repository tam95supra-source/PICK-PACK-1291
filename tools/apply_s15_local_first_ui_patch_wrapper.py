#!/usr/bin/env python3
from pathlib import Path
import runpy
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "tools/apply_s15_local_first_ui_patch.py"
text = source.read_text(encoding="utf-8")

old = r'''once(
    '                refreshHeaderConnection()\n',
    ''' + "'''" + r'''                refreshHeaderConnection()
                if(status.connected && status.businessDate.isNotBlank() && status.retentionFloor.isNotBlank()) {
                    operationalSync.reconcile(status.businessDate,status.retentionFloor,status.retentionEpoch,status.dayRevisions)
                }
''' + "'''" + r''',
    'sync manifest hook',
)
'''
new = r'''listener_start = text.find('            override fun onStatus(status: ForegroundSyncCoordinator.Status) {')
if listener_start < 0:
    raise SystemExit("S15 onStatus listener anchor not found")
hook = '                refreshHeaderConnection()\n'
hook_pos = text.find(hook, listener_start)
if hook_pos < 0:
    raise SystemExit("S15 refreshHeaderConnection hook not found inside onStatus")
hook_end = hook_pos + len(hook)
manifest_hook = ''' + "'''" + r'''                if(status.connected && status.businessDate.isNotBlank() && status.retentionFloor.isNotBlank()) {
                    operationalSync.reconcile(status.businessDate,status.retentionFloor,status.retentionEpoch,status.dayRevisions)
                }
''' + "'''" + r'''
text = text[:hook_end] + manifest_hook + text[hook_end:]
'''

if old not in text:
    raise SystemExit("S15 wrapper could not locate sync-manifest source block")
text = text.replace(old, new, 1)

with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8", dir=str(ROOT / "tools")) as f:
    f.write(text)
    temp = Path(f.name)
try:
    runpy.run_path(str(temp), run_name="__main__")
finally:
    temp.unlink(missing_ok=True)
