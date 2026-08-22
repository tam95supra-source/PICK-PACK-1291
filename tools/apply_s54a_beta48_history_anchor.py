#!/usr/bin/env python3
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s=p.read_text(encoding='utf-8')
if 'S54_BETA48_OWNER_10_FIXES' in s:
    print('S54A: S54 already materialized')
    raise SystemExit(0)

# S36..S53 have changed the exact selected-date expression several times. Normalize only the
# History declaration tuple so S54 can apply deterministically without coupling to an old expression.
pat=r'var selectedDate=[^;\n]+;var filter="ALL";var pageSize=60;var query=""'
replacement='var selectedDate=operationalStore.latestBusinessDate().ifBlank{operationalStore.businessDate()};var filter="ALL";var pageSize=60;var query=""'
s,n=re.subn(pat,replacement,s,count=1)
if n!=1:
    raise SystemExit(f'S54A History declaration not found: {n}')
p.write_text(s,encoding='utf-8')
print('S54A normalized post-S53 History declaration')
