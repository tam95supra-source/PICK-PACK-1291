#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s=P.read_text(encoding='utf-8')
MARK='S36B_COMPILE_HOTFIX'
if MARK in s:
    print('S36B already applied');raise SystemExit(0)
# S34D renamed the report renderer after S34C; S36 is applied later and must use the final name.
s=s.replace('box.addView(reportGrid("",makeGrid(selected,"position",selectedDate),"Vị trí","position"))','box.addView(s34ReportGrid("",makeGrid(selected,"position",selectedDate),"Vị trí","position"))')
s=s.replace('box.addView(reportGrid("",makeGrid(selected,"tenure",selectedDate),"Thâm niên","label"))','box.addView(s34ReportGrid("",makeGrid(selected,"tenure",selectedDate),"Thâm niên","label"))')
# History detail function is historyTimeline(items) in the final S34/S35 chain.
s=s.replace('setOnClickListener{historyTimelineScreen(mnv,items.toMutableList())}','setOnClickListener{historyTimeline(items)}')
# Inline the small status chip; no generic badge() helper exists in this activity.
old='addView(badge(label,when(state){"FAILED"->red;"PENDING"->Color.rgb(217,119,6);else->teal}))'
new='addView(txt(label,9f,when(state){"FAILED"->red;"PENDING"->Color.rgb(217,119,6);else->teal},true).apply{setPadding(dp(7),dp(4),dp(7),dp(4));background=round(Color.WHITE,9)})'
if old not in s: raise SystemExit('S36B badge anchor missing')
s=s.replace(old,new,1)
# Add a marker adjacent to the S36 marker without changing behavior.
s=s.replace('// S36_PERF_HISTORY_REPORT_SERVICE: selected-date history, bounded global search, pagination and Service telemetry.','// S36_PERF_HISTORY_REPORT_SERVICE: selected-date history, bounded global search, pagination and Service telemetry.\n    // S36B_COMPILE_HOTFIX',1)
P.write_text(s,encoding='utf-8')
o=P.read_text(encoding='utf-8')
for x in [MARK,'s34ReportGrid(','historyTimeline(items)','SERVICE • Hoạt động']:
    if x not in o: raise SystemExit('S36B contract missing '+x)
for bad in ['historyTimelineScreen(mnv,items.toMutableList())','badge(label,']:
    if bad in o: raise SystemExit('S36B unresolved helper '+bad)
print('Applied S36B compile hotfix: report renderer, history status chip and detail route')
