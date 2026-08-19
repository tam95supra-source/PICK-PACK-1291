#!/usr/bin/env python3
from pathlib import Path
import runpy, subprocess

p=Path('service/src/recovery.ts')
s=p.read_text(encoding='utf-8')
if 'S28_REFLECTED_ENTER_RECONCILIATION' not in s and 'S28B_SQL_SEMANTIC_REFLECTED_ENTER' not in s:
    raise SystemExit('S28 base reflected-enter recovery patch is not present in persisted source')
runpy.run_path('tools/apply_s28b_recovery_sql_semantic.py',run_name='__main__')
runpy.run_path('tools/apply_s28d_compat_resume_reflected.py',run_name='__main__')
# Existing recovery workflow stages recovery.ts explicitly. Stage the compatibility wrapper here so
# the same workflow commit/deploy cannot lose the S28D change during its pull/rebase step.
subprocess.run(['git','add','service/src/recovery_resume_compat.ts'],check=True)
print('S28 recovery wrapper applied S28B + S28D compatibility reconciliation')
