#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S49B_BETA43_KOTLIN_QUOTE_HOTFIX'
s=OPS.read_text(encoding='utf-8')
if MARK in s:
    print('S49B already applied')
    raise SystemExit(0)

def fix_fun(src:str, signature:str):
    start=src.find('    private fun '+signature)
    if start<0:
        raise SystemExit('S49B function anchor missing: '+signature)
    end=src.find('\n    private fun ',start+20)
    if end<0:
        end=len(src)
    chunk=src[start:end]
    needle=chr(92)+'"'
    fixed=chunk.replace(needle,'"')
    return src[:start]+fixed+src[end:], chunk.count(needle)

signatures=[
    'sessionTimelineItems(mnv:String):MutableList<JSONObject>{',
    'sessionEventTitle(typeRaw:String,label:String):String=',
    'addPdaIdentity(body:LinearLayout,ses:JSONObject){',
    'pickSummary(s:JSONObject):String{',
    'packSummary(s:JSONObject):String{',
    'returnedSessionContext(ctx:JSONObject,r:BetaApiClient.Result):JSONObject?{',
    'sessionWorkEditor(ctx:JSONObject){',
    'editableTime(iso:String):String=',
    'parseEditableTime(v:String):String?=',
    'editAttendanceTime(ctx:JSONObject,field:String){',
    'deleteExitRecord(ctx:JSONObject){',
    'renderActive(body: LinearLayout, ctx: JSONObject) {',
    'renderEnded(body: LinearLayout, ctx: JSONObject) {',
]
count=0
for sig in signatures:
    s,n=fix_fun(s,sig)
    count+=n
# Zero matches is valid: the S49 source may already contain normal Kotlin quotes.
s=s.replace('    // S49_BETA43_SESSION_ADMIN_CORRECTIONS','    // S49_BETA43_SESSION_ADMIN_CORRECTIONS\n    // '+MARK,1)
OPS.write_text(s,encoding='utf-8')
o=OPS.read_text(encoding='utf-8')
assert MARK in o
print(f'Applied S49B: quote normalization complete; repaired {count} pair(s)')
