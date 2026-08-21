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

# Rewrite the generated S50 account list as normal multiline Kotlin. The original dense
# one-line expression used the reserved word `protected` and became parser-ambiguous after
# token substitution. Keep the same UI/permissions but make the syntax deterministic.
account_start = s.find("    private fun accountManager(){")
account_end = s.find("    private fun accountEditDialog(", account_start)
if account_start < 0 or account_end < 0:
    raise SystemExit("S50B account manager anchors missing")
account = r'''    private fun accountManager(){
        screenState="ACCOUNT_MANAGER"
        val root=baseRoot("QUẢN LÝ TÀI KHOẢN")
        val body=body()
        val selected=linkedSetOf<String>()
        val checks=mutableListOf<CheckBox>()
        body.addView(primary("TẠO TÀI KHOẢN",green){accountCreateDialog()},matchWrap())
        if(isSuper()){
            body.addView(gap(7))
            val bulk=row(bg)
            bulk.addView(smallButton("CHỌN TẤT CẢ",navy).apply{
                setOnClickListener{checks.forEach{if(it.isEnabled)it.isChecked=true}}
            },LinearLayout.LayoutParams(0,dp(42),1f).apply{marginEnd=dp(3)})
            bulk.addView(smallButton("XÓA ĐÃ CHỌN",red).apply{
                setOnClickListener{deleteAccountsBulk(selected.toList())}
            },LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(3)})
            body.addView(bulk,matchWrap())
        }
        body.addView(gap(10))
        val box=column(bg)
        body.addView(box,matchWrap())
        api.call("account_list"){r->runOnUiThread{
            box.removeAllViews()
            if(handleAuth(r))return@runOnUiThread
            if(!r.ok){box.addView(info(r.error?:"Không tải được tài khoản"));return@runOnUiThread}
            val a=r.json?.optJSONArray("items")?:JSONArray()
            for(i in 0 until a.length()){
                val x=a.optJSONObject(i)?:continue
                val id=x.optString("login_id")
                val isProtectedAccount=id==login||x.optString("role")=="SUPERADMIN"
                val card=column(surface).apply{
                    setPadding(dp(12),dp(10),dp(12),dp(10))
                    background=outlineBg(surface,12)
                    val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL}
                    if(isSuper()){
                        val c=CheckBox(this@OperationsActivity).apply{
                            isEnabled=!isProtectedAccount
                            isChecked=id in selected
                            setOnCheckedChangeListener{_,on->if(on)selected.add(id)else selected.remove(id)}
                        }
                        checks.add(c)
                        top.addView(c,size(dp(42),dp(42)))
                    }
                    top.addView(column(surface).apply{
                        addView(txt("$id • ${x.optString("display_name")}",13f,navy,true))
                        addView(txt("${roleText(x.optString("role"))} • ${if(x.optString("status")=="ACTIVE")"Đang hoạt động" else "Đã vô hiệu hóa"} • ${x.optString("email")}",9.8f,muted,false))
                    },LinearLayout.LayoutParams(0,-2,1f))
                    addView(top,matchWrap())
                    if(id!=login){
                        addView(gap(6))
                        val actions=row(surface)
                        if(isSuper()){
                            actions.addView(smallButton("SỬA",teal).apply{setOnClickListener{accountEditDialog(x)}},LinearLayout.LayoutParams(0,dp(38),1f).apply{marginEnd=dp(3)})
                        }
                        val newStatus=if(x.optString("status")=="ACTIVE")"DISABLED" else "ACTIVE"
                        actions.addView(smallButton(if(newStatus=="DISABLED")"VÔ HIỆU" else "KÍCH HOẠT",if(newStatus=="DISABLED")orange else green).apply{
                            setOnClickListener{api.call("account_status",JSONObject().put("login_id",id).put("status",newStatus)){rr->runOnUiThread{if(!rr.ok)showError(rr.error?:"Không cập nhật được")else accountManager()}}}
                        },LinearLayout.LayoutParams(0,dp(38),1f).apply{marginStart=dp(3);marginEnd=dp(3)})
                        if(isSuper()&&!isProtectedAccount){
                            actions.addView(smallButton("XÓA",red).apply{setOnClickListener{deleteAccountsBulk(listOf(id))}},LinearLayout.LayoutParams(0,dp(38),1f).apply{marginStart=dp(3)})
                        }
                        addView(actions,matchWrap())
                    }
                }
                box.addView(card,matchWrap())
                box.addView(gap(7))
            }
        }}
        attach(root,body)
    }

'''
s = s[:account_start] + account + s[account_end:]

# Durable marker in generated Kotlin for build diagnostics.
anchor = "    private fun pdaExchangeScreen(){"
if MARK not in s:
    if anchor not in s:
        raise SystemExit("S50B PDA function still missing")
    s = s.replace(anchor, "    // " + MARK + "\n" + anchor, 1)

if "private fun pdaExchangeScreen(){" not in s:
    raise SystemExit("S50B PDA exchange contract missing")
if "val isProtectedAccount=" not in s or "XÓA ĐÃ CHỌN" not in s:
    raise SystemExit("S50B account manager contract missing")

OPS.write_text(s, encoding="utf-8")
print("Applied S50B Beta44 compile hotfix: preserved PDA exchange and normalized account manager Kotlin")
