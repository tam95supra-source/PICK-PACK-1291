#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
S33 = ROOT / "tools/apply_s33_owner_ui_sync_resources.py"
MARK = "S50B_BETA44_COMPILE_HOTFIX"

s = OPS.read_text(encoding="utf-8")

# S50 replaces syncScreen through settingsScreen. In the canonical chain S33 inserted
# pdaExchangeScreen between those functions, so the S50 range replacement can remove it.
# Restore the exact S33 implementation rather than duplicating/reinventing PDA logic.
if "    private fun pdaExchangeScreen(){" not in s:
    src = S33.read_text(encoding="utf-8")
    begin_marker = "    pda=r'''"
    begin = src.find(begin_marker)
    if begin < 0:
        raise SystemExit("S50B S33 PDA source anchor missing")
    begin += len(begin_marker)
    end = src.find("'''", begin)
    if end < 0:
        raise SystemExit("S50B S33 PDA source terminator missing")
    pda = src[begin:end].strip("\n")
    insert = s.find("    private fun settingsScreen(){")
    if insert < 0:
        raise SystemExit("S50B settings insert anchor missing")
    s = s[:insert] + pda + "\n\n" + s[insert:]

# `protected` is a Kotlin keyword. S50 account manager used it as a local variable.
s = s.replace('val id=x.optString("login_id"),protected=id==login||x.optString("role")=="SUPERADMIN";',
              'val id=x.optString("login_id"),protectedAccount=id==login||x.optString("role")=="SUPERADMIN";', 1)
s = s.replace("isEnabled=!protected;", "isEnabled=!protectedAccount;")
s = s.replace("if(isSuper()&&!protected)", "if(isSuper()&&!protectedAccount)")

# Durable marker in generated Kotlin for build diagnostics.
anchor = "    private fun pdaExchangeScreen(){"
if MARK not in s:
    if anchor not in s:
        raise SystemExit("S50B PDA function still missing")
    s = s.replace(anchor, "    // " + MARK + "\n" + anchor, 1)

if "protected=" in s or "!protected;" in s or "&&!protected)" in s:
    raise SystemExit("S50B protected keyword repair incomplete")
if "private fun pdaExchangeScreen(){" not in s:
    raise SystemExit("S50B PDA exchange contract missing")

OPS.write_text(s, encoding="utf-8")
print("Applied S50B Beta44 compile hotfix: preserved PDA exchange and repaired Kotlin keyword")
