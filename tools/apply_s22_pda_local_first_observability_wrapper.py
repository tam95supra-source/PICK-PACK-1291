#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'tools/apply_s22_pda_local_first_observability.py'
source=path.read_text(encoding='utf-8')
old='"                lastConnected = status.connected\\n                refreshHeaderConnection()\\n",'
new='"                lastConnected = status.connected\\n",'
old_repl='"                lastConnected = status.connected\\n                lastLatencyMs = status.latencyMs\\n                serviceProviderCache = serviceProviderFromRuntime()\\n                refreshHeaderConnection()\\n",'
new_repl='"                lastConnected = status.connected\\n                lastLatencyMs = status.latencyMs\\n                serviceProviderCache = serviceProviderFromRuntime()\\n",'
if old not in source or old_repl not in source:
    raise SystemExit('S22 wrapper source anchors missing')
source=source.replace(old,new,1).replace(old_repl,new_repl,1)
exec(compile(source,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
