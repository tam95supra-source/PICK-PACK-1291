#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s=P.read_text(encoding='utf-8')
MARK='S47B_BETA41_COMPILE_HOTFIX'
if MARK in s:
    print('S47B already applied')
    raise SystemExit(0)
old='addView(badge(label,when(state){"FAILED"->red;"PENDING"->Color.rgb(217,119,6);else->teal}))'
new='addView(txt(label,9f,when(state){"FAILED"->red;"PENDING"->Color.rgb(217,119,6);else->teal},true).apply{setPadding(dp(7),dp(4),dp(7),dp(4));background=round(Color.WHITE,9)})'
if old not in s: raise SystemExit('S47B badge anchor missing')
s=s.replace(old,new,1)
old='setOnClickListener{historyTimelineScreen(mnv,items.toMutableList())}'
new='setOnClickListener{historyTimeline(items)}'
if old not in s: raise SystemExit('S47B history detail route anchor missing')
s=s.replace(old,new,1)
s=s.replace('// S47_BETA41_OWNER_FIVE_FIXES','// S47_BETA41_OWNER_FIVE_FIXES\n    // '+MARK,1)
P.write_text(s,encoding='utf-8')
o=P.read_text(encoding='utf-8')
for required in [MARK,'historyTimeline(items)','progress.joinToString(" - ")','Người thực hiện: $actor']:
    if required not in o: raise SystemExit('S47B contract missing: '+required)
for forbidden in ['badge(label,','historyTimelineScreen(mnv,items.toMutableList())']:
    if forbidden in o: raise SystemExit('S47B unresolved helper remains: '+forbidden)
print('Applied S47B: final History status chip and detail route compile helpers')
