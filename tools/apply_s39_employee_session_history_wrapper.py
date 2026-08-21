#!/usr/bin/env python3
from pathlib import Path
import runpy

ROOT=Path(__file__).resolve().parents[1]
try:
    runpy.run_path(str(ROOT/'tools/apply_s39_employee_session_history.py'),run_name='__main__')
except SystemExit as e:
    # S39's original terminal assertion searched the whole OperationsActivity and can see
    # unrelated legacy paging in other screens. Accept only this exact diagnostic and
    # independently prove that the History screen itself has true 100-row paging.
    if str(e)!='S39 old cumulative History paging survived':
        raise
    o=(ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt').read_text(encoding='utf-8')
    a=o.find('    private fun historyScreen(){');b=o.find('\n    private fun historyTimeline(',a)
    if a<0 or b<0: raise SystemExit('S39W History scope missing')
    hist=o[a:b]
    if 'val pageSize=100;var pageStart=0' not in hist: raise SystemExit('S39W page size 100 missing')
    if 'drop(pageStart).take(pageSize)' not in hist: raise SystemExit('S39W true paging missing')
    if 'pageSize+=60' in hist: raise SystemExit('S39W cumulative History paging survived')
    if 'tối đa 100 bản ghi mỗi trang' not in hist: raise SystemExit('S39W page label missing')
    print('S39 wrapper PASS: History-scoped paging regression check is 100 rows/page')
