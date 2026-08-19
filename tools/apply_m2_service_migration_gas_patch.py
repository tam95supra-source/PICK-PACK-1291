#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'google-apps-script/PICK_PACK_API.gs'
text=path.read_text(encoding='utf-8')
base_marker='M2_SERVICE_AUTHORITY_ROUTING'
control_marker='M2_SERVICE_AUTHORITY_CONTROL_ROUTES'

def once(old,new,label):
    global text
    n=text.count(old)
    if n!=1: raise SystemExit(f'M2 GAS anchor {label}: expected 1, got {n}')
    text=text.replace(old,new,1)

if base_marker not in text:
    once(
        "    if (action === 'health') return ppJson_(ppHealth_());\n",
        "    // M2_SERVICE_AUTHORITY_ROUTING\n    if (action === 'service_discovery') return ppJson_(ppM2Discovery_(body));\n    if (action === 'health') return ppJson_(ppHealth_());\n",
        'public discovery route',
    )
    for action,fn in [('enter','ppEnter_'),('exit','ppExit_'),('resource_change','ppResourceChange_'),('labor_start','ppLaborStart_'),('labor_finish','ppLaborFinish_')]:
        old=f"    if (action === '{action}') return ppJson_(ppWithLock_(function(){{ return {fn}(auth, body); }}));\n"
        new=f"    if (action === '{action}') return ppJson_(ppM2OperationalRoute_(auth, body, '{action}', function(){{ return ppWithLock_(function(){{ return {fn}(auth, body); }}); }}));\n"
        once(old,new,action)

if control_marker not in text:
    anchor="    if (action === 'sync_status') return ppJson_(ppSyncStatus_());\n"
    replacement=(
        "    // M2_SERVICE_AUTHORITY_CONTROL_ROUTES\n"
        "    if (action === 'm2_authority_status') return ppJson_(ppM2Discovery_(body));\n"
        "    if (action === 'm2_reconcile_begin') return ppJson_(ppM2BeginReconcile_(auth, body));\n"
        "    if (action === 'm2_fallback_flush') return ppJson_(String(auth.role)==='SUPERADMIN'?ppM2FlushFallbackInbox_():{ok:false,error:'SUPERADMIN_REQUIRED'});\n"
        "    if (action === 'm2_failback_complete') return ppJson_(ppM2CompleteFailback_(auth, body));\n"
        + anchor
    )
    once(anchor,replacement,'authenticated authority controls')

path.write_text(text,encoding='utf-8')
print('Applied/verified M2 GAS Service authority routing and controls')
