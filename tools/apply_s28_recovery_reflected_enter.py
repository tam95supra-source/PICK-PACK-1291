#!/usr/bin/env python3
from pathlib import Path
import runpy

p=Path('service/src/recovery.ts')
s=p.read_text(encoding='utf-8')
if 'S28_REFLECTED_ENTER_RECONCILIATION' not in s and 'S28B_SQL_SEMANTIC_REFLECTED_ENTER' not in s:
    raise SystemExit('S28 base reflected-enter recovery patch is not present in persisted source')
runpy.run_path('tools/apply_s28b_recovery_sql_semantic.py',run_name='__main__')
print('S28 recovery wrapper applied S28B SQL semantic reconciliation')
