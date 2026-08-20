#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'tools/apply_s33_owner_ui_sync_resources.py'
src=SCRIPT.read_text(encoding='utf-8')
old=(
"    # Generated call has one stable result assignment after the m2 selection.\n"
"    target='      val result = if (m2?.handled == true) {'\n"
"    if target not in s: raise SystemExit('S33 API result anchor missing')\n"
"    s=s.replace(target,'      val result = if (action in setOf(\"resource_master_list\",\"resource_master_upsert\",\"resource_master_delete\",\"history_correction\")) serviceOwnerCall(action,payload) else if (m2?.handled == true) {',1)\n"
)
new=(
"    # S33 wrapper: route owner-only Service actions before the existing S31 call router.\n"
"    call_pos=s.find('fun call(action: String')\n"
"    try_pos=s.find('try {',call_pos) if call_pos>=0 else -1\n"
"    if call_pos<0 or try_pos<0: raise SystemExit('S33 API call router anchor missing')\n"
"    owner_branch=(\n"
"        '      if (action in setOf(\\\"resource_master_list\\\",\\\"resource_master_upsert\\\",\\\"resource_master_delete\\\",\\\"history_correction\\\")) {\\n'\n"
"        '          val result=serviceOwnerCall(action,payload)\\n'\n"
"        '          if(result.code==401) clearSession()\\n'\n"
"        '          if(action in setOf(\\\"resource_master_upsert\\\",\\\"resource_master_delete\\\",\\\"history_correction\\\")) AppHistory.record(appContext,action,result.ok,result.error.orEmpty())\\n'\n"
"        '          callback(result)\\n'\n"
"        '          return@execute\\n'\n"
"        '      }\\n'\n"
"    )\n"
"    s=s[:try_pos+5]+owner_branch+s[try_pos+5:]\n"
)
if old not in src:
    raise SystemExit('S33 wrapper target block missing')
patched=src.replace(old,new,1)
ns={'__name__':'__main__','__file__':str(SCRIPT)}
exec(compile(patched,str(SCRIPT),'exec'),ns,ns)
