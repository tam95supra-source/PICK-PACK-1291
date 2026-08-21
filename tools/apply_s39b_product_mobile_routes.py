#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'service/src/entry_product.ts'
MARK='S39B_PRODUCT_MOBILE_ROUTES'
s=P.read_text(encoding='utf-8')
if MARK not in s:
    s=s.replace('import current, { RealtimeHub } from "./entry_hotfix"; // S39_MOBILE_ROUTE_LEGACY_FIX','import current, { RealtimeHub } from "./entry"; // S39B_PRODUCT_MOBILE_ROUTES',1)
    if 'from "./mobile_hotfix"' not in s:
        anchor='import { authenticate } from "./auth";\n'
        if anchor not in s: raise SystemExit('S39B import anchor missing')
        s=s.replace(anchor,anchor+'import { exchangeGasSession, mobileRead } from "./mobile_hotfix";\n',1)
    fetch_anchor='''    const u=new URL(request.url);\n    if(u.pathname==="/v1/admin/business-dates"&&request.method==="GET")return historicalBusinessDates(request,env);'''
    replacement='''    const u=new URL(request.url);\n    // S39B_PRODUCT_MOBILE_ROUTES: production entrypoint owns these routes directly; no wrapper indirection.\n    if(u.pathname==="/v1/auth/gas-session"&&request.method==="POST")return exchangeGasSession(request,env);\n    if(u.pathname==="/v1/mobile/read"&&request.method==="POST")return mobileRead(request,env);\n    if(u.pathname==="/v1/admin/business-dates"&&request.method==="GET")return historicalBusinessDates(request,env);'''
    if fetch_anchor not in s: raise SystemExit('S39B fetch anchor missing')
    s=s.replace(fetch_anchor,replacement,1)
P.write_text(s,encoding='utf-8')
o=P.read_text(encoding='utf-8')
for x in [MARK,'exchangeGasSession','mobileRead','/v1/auth/gas-session','/v1/mobile/read','from "./entry"']:
    if x not in o: raise SystemExit('S39B product route contract missing: '+x)
print('Applied S39B: mobile/session endpoints wired directly in production entrypoint')
