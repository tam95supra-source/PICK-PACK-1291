#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'tools/apply_s35_owner_ui_history_consistency.py'
src=SCRIPT.read_text(encoding='utf-8')
start=src.find("status_old='''")
end=src.find('# ---------------------------------------------------------------------------\n# Nghiệp vụ:',start)
if start<0 or end<0:
    raise SystemExit('S35 wrapper source anchors missing')
replacement='''status_anchor='if (!status.connected || !status.changed) return'\npos=s.find(status_anchor)\nif pos<0:\n    raise SystemExit('S35 foreground history refresh anchor missing')\nline_end=s.find('\\n',pos)\nif line_end<0:\n    raise SystemExit('S35 foreground history refresh line end missing')\ns=s[:line_end+1]+'                if(screenState=="HISTORY"){historyLastCanonicalRefreshAt=0L;refreshHistoryCanonical()}\\n'+s[line_end+1:]\n\n'''
patched=src[:start]+replacement+src[end:]
ns={'__name__':'__main__','__file__':str(SCRIPT)}
exec(compile(patched,str(SCRIPT),'exec'),ns,ns)
