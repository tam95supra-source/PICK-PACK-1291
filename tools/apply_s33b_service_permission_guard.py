#!/usr/bin/env python3
from pathlib import Path
import runpy

ROOT=Path(__file__).resolve().parents[1]
COR=ROOT/'service/src/correction.ts'
s=COR.read_text(encoding='utf-8')
MARK='S33B_CORRECTION_ROLE_GUARD'
if MARK not in s:
    anchor='  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401); // S33_OWNER_RESOURCE_HISTORY\n'
    if anchor not in s:
        raise SystemExit('S33B correction auth anchor missing; apply S33 first')
    s=s.replace(anchor,anchor+'  if(auth.role!=="ADMIN"&&auth.role!=="SUPERADMIN")return apiError("ADMIN_REQUIRED","PERMISSION",403); // '+MARK+'\n',1)
    COR.write_text(s,encoding='utf-8')

s=COR.read_text(encoding='utf-8')
if MARK not in s or 'maxAge=auth.role==="SUPERADMIN"?6:1' not in s:
    raise SystemExit('S33B correction permission contract missing')
print('Applied S33B correction role guard: USER read-only, ADMIN N/N-1, SUPERADMIN N..N-6')
runpy.run_path(str(ROOT/'tools/apply_s33c_service_timezone_guard.py'),run_name='__main__')
