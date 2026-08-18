#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'google-apps-script/PICK_PACK_API.gs'
text=path.read_text(encoding='utf-8')
marker='M2_SERVICE_AUTHORITY_ROUTING'
if marker in text:
    print('M2 GAS authority routing already present; skip.')
    raise SystemExit(0)

def once(old,new,label):
    global text
    n=text.count(old)
    if n!=1: raise SystemExit(f'M2 GAS anchor {label}: expected 1, got {n}')
    text=text.replace(old,new,1)

once(
    "    if (action === 'health') return ppJson_(ppHealth_());\n",
    "    // M2_SERVICE_AUTHORITY_ROUTING\n    if (action === 'service_discovery') return ppJson_(ppM2Discovery_(body));\n    if (action === 'health') return ppJson_(ppHealth_());\n",
    'public discovery route',
)
for action,fn in [('enter','ppEnter_'),('exit','ppExit_'),('resource_change','ppResourceChange_'),('labor_start','ppLaborStart_'),('labor_finish','ppLaborFinish_')]:
    old=f"    if (action === '{action}') return ppJson_(ppWithLock_(function(){{ return {fn}(auth, body); }}));\n"
    new=f"    if (action === '{action}') return ppJson_(ppM2OperationalRoute_(auth, body, '{action}', function(){{ return ppWithLock_(function(){{ return {fn}(auth, body); }}); }}));\n"
    once(old,new,action)
path.write_text(text,encoding='utf-8')
print('Applied M2 GAS Service authority routing')
