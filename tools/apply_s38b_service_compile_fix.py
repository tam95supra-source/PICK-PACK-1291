#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'service/src/core.ts'
s=P.read_text(encoding='utf-8')
old='throw new CoreError("PDA_EXIT_STATUS_REQUIRED","VALIDATION",400,{pda_serial:current.pda_serial,initial_status:initial});'
new='throw new CoreError("PDA_EXIT_STATUS_REQUIRED","VALIDATION",400,false,{pda_serial:current.pda_serial,initial_status:initial});'
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise SystemExit('S38B CoreError anchor missing')
P.write_text(s,encoding='utf-8')
if new not in P.read_text(encoding='utf-8'):
    raise SystemExit('S38B verification failed')
print('Applied S38B service compile fix')
