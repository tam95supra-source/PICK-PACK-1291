#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s=OPS.read_text(encoding='utf-8')
needles=[
    'MasterDataCache.resourceOptions(this@OperationsActivity)',
    'PdaLocalProjection.resourceOptions(this,mnv)',
]
for needle in needles:
    pos=0
    found=0
    while True:
        i=s.find(needle,pos)
        if i<0: break
        found+=1
        lo=max(0,i-320);hi=min(len(s),i+len(needle)+420)
        context=s[lo:hi].replace('\n','\\n')
        print(f'S55D_STALE_CONTEXT needle={needle} occurrence={found} context={context}')
        pos=i+len(needle)
    print(f'S55D_STALE_COUNT needle={needle} count={found}')
print('S55D stale resource context diagnostic complete')
