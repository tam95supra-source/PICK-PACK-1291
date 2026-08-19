#!/usr/bin/env python3
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
API=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt'
s=API.read_text(encoding='utf-8')
MARK='S31A_NORMALIZED_API_CALL_ANCHOR'
if MARK not in s:
    pattern=re.compile(r'    fun\s+call\s*\(\s*action:\s*String\s*,\s*payload:\s*JSONObject\s*=\s*JSONObject\(\)\s*,\s*callback:\s*\(Result\)\s*->\s*Unit\s*\)\s*\{')
    m=pattern.search(s)
    if not m: raise SystemExit('S31A call method structural anchor missing')
    next_fun=s.find('\n    fun ',m.end())
    search_end=next_fun if next_fun>=0 else min(len(s),m.end()+3000)
    exec_pos=s.find('executor.execute {',m.end(),search_end)
    if exec_pos<0: raise SystemExit('S31A call executor structural anchor missing')
    # Preserve any older tracking/guard statements that were inserted before the network executor.
    # They belong to the network path, so move them intact just inside executor.execute. S31 then
    # inserts the operational local-fast-path before this executor and returns without waiting.
    between=s[m.end():exec_pos]
    moved=between.rstrip(' \t')
    canonical='    fun call(action: String, payload: JSONObject = JSONObject(), callback: (Result) -> Unit) {\n        executor.execute {'
    s=s[:m.start()]+canonical+moved+s[exec_pos+len('executor.execute {'):]
    class_anchor='class BetaApiClient(context: Context) {\n'
    if class_anchor not in s: raise SystemExit('S31A class anchor missing')
    s=s.replace(class_anchor,class_anchor+'    // '+MARK+'\n',1)
    API.write_text(s,encoding='utf-8')
print('Applied S31A: moved existing pre-executor tracking into network executor and normalized call anchor')
