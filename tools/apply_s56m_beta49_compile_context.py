#!/usr/bin/env python3
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
lines=p.read_text(encoding='utf-8').splitlines()
for target in (499,955):
    lo=max(1,target-4);hi=min(len(lines),target+4)
    print(f'S56M_CONTEXT target={target} total_lines={len(lines)}')
    for n in range(lo,hi+1):
        print(f'S56M_LINE {n}: {lines[n-1]}')
print('S56M compile context diagnostic complete')
