from pathlib import Path

def replace(path, old, new):
    p=Path(path); s=p.read_text()
    if old in s:
        p.write_text(s.replace(old,new)); print('patched',path)
    elif new in s: print('already',path)
    else: raise SystemExit(f'anchor missing {path}: {old[:120]!r}')

# Normal mutations are bounded; all-time Web edits must use /v1/corrections so reason/before/after are mandatory.
replace('service/src/core.ts',
'''  const writeWindow=auth.role==="SUPERADMIN"?(req.client_source==="WEB"?0:7):2;''',
'''  const writeWindow=auth.role==="SUPERADMIN"?7:2;''')

print('SESSION1_POLICY_FOLLOWUP_APPLIED')
