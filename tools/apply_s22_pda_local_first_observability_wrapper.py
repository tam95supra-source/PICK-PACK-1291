#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'tools/apply_s22_pda_local_first_observability.py'
source=path.read_text(encoding='utf-8')

# S15 inserts reconciliation between lastConnected and refreshHeaderConnection; loosen the S22 anchor.
old='"                lastConnected = status.connected\\n                refreshHeaderConnection()\\n",'
new='"                lastConnected = status.connected\\n",'
old_repl='"                lastConnected = status.connected\\n                lastLatencyMs = status.latencyMs\\n                serviceProviderCache = serviceProviderFromRuntime()\\n                refreshHeaderConnection()\\n",'
new_repl='"                lastConnected = status.connected\\n                lastLatencyMs = status.latencyMs\\n                serviceProviderCache = serviceProviderFromRuntime()\\n",'
if old not in source or old_repl not in source:
    raise SystemExit('S22 wrapper source anchors missing')
source=source.replace(old,new,1).replace(old_repl,new_repl,1)

# Keep units visible when upload and download are active simultaneously in the compact header cell.
rate_anchor='''    private fun syncHeaderText():String{\n'''
rate_replacement='''    private fun compactRate(v:Long):String=when{\n        v>=1024L*1024L->String.format(java.util.Locale.US,"%.1fM/s",v/1048576.0)\n        v>=1024L->String.format(java.util.Locale.US,"%.1fK/s",v/1024.0)\n        else->"${v}B/s"\n    }\n    private fun syncHeaderText():String{\n'''
if source.count(rate_anchor)!=1:
    raise SystemExit(f'S22 compact-rate anchor mismatch: {source.count(rate_anchor)}')
source=source.replace(rate_anchor,rate_replacement,1)
old_both='''            d.uploadBps>0&&d.downloadBps>0->"↑${formatRate(d.uploadBps).substringBefore(" ")} ↓${formatRate(d.downloadBps).substringBefore(" ")}"\n'''
new_both='''            d.uploadBps>0&&d.downloadBps>0->"↑${compactRate(d.uploadBps)} ↓${compactRate(d.downloadBps)}"\n'''
if source.count(old_both)!=1:
    raise SystemExit(f'S22 bidirectional-rate anchor mismatch: {source.count(old_both)}')
source=source.replace(old_both,new_both,1)

exec(compile(source,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
