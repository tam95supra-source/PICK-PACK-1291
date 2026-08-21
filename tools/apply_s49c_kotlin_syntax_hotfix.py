#!/usr/bin/env python3
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S49C_BETA43_KOTLIN_SYNTAX_HOTFIX'
s=OPS.read_text(encoding='utf-8')
if MARK in s:
    print('S49C already applied')
    raise SystemExit(0)
if 'S49_BETA43_SESSION_ADMIN_CORRECTIONS' not in s:
    raise SystemExit('S49C requires S49 first')

# 1) Kotlin does not support Java-style multi-variable declarations.
old='val t=o.optString("table"),u=o.optString("user_pack")'
new='val t=o.optString("table");val u=o.optString("user_pack")'
if old not in s:
    raise SystemExit('S49C PACK pair declaration anchor missing')
s=s.replace(old,new,1)

# 2) Local function declarations emitted by S49 must end before the next val.
clean='fun clean(v:String)=v.trim().takeUnless{it.equals("null",true)||it=="—"}?:""'
old_serial=clean+';val serial='
old_pda=clean+';val pda='
if old_serial not in s:
    raise SystemExit('S49C addPdaIdentity clean/serial anchor missing')
if old_pda not in s:
    raise SystemExit('S49C renderActive clean/pda anchor missing')
s=s.replace(old_serial,clean+'\n        val serial=',1)
s=s.replace(old_pda,clean+'\n        val pda=',1)

if re.search(r'\b(?:val|var)\s+[A-Za-z_]\w*\s*=\s*[^;\n]+,\s*[A-Za-z_]\w*\s*=',s):
    raise SystemExit('S49C residual Java-style multi-variable declaration')
if clean+';val ' in s:
    raise SystemExit('S49C residual local-fun/val same-line declaration')

s=s.replace('    // S49B_BETA43_KOTLIN_QUOTE_HOTFIX','    // S49B_BETA43_KOTLIN_QUOTE_HOTFIX\n    // '+MARK,1)
OPS.write_text(s,encoding='utf-8')
o=OPS.read_text(encoding='utf-8')
assert MARK in o
assert new in o
assert clean+'\n        val serial=' in o
assert clean+'\n        val pda=' in o
print('Applied S49C: fixed PACK pair declaration and local clean() declaration boundaries')
