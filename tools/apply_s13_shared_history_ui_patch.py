#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ops_path = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
api_path = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt"
text = ops_path.read_text(encoding="utf-8")


def once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"S13 UI anchor {label!r}: expected 1, got {count}")
    text = text.replace(old, new, 1)


def block(start_marker: str, end_marker: str, replacement: str, label: str) -> None:
    global text
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"S13 UI block start {label!r} not found")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"S13 UI block end {label!r} not found")
    text = text[:start] + replacement + text[end:]


# Scanner/MNV field: restore a genuinely large field (~2x compact height), full wrapping and QR cue.
block(
    '    private fun scanField(',
    '    private fun mnvInput(',
    r'''    private fun scanField(h:String,numeric:Boolean)=input(h,false).apply{
        setSingleLine(false)
        maxLines=3
        setHorizontallyScrolling(false)
        gravity=Gravity.CENTER_VERTICAL
        minHeight=dp(128)
        textSize=13.2f
        setPadding(dp(14),dp(14),dp(14),dp(14))
        setCompoundDrawablesWithIntrinsicBounds(R.drawable.ic_pp_scan,0,0,0)
        compoundDrawableTintList=ColorStateList.valueOf(teal)
        compoundDrawablePadding=dp(10)
        if(numeric){
            inputType=InputType.TYPE_CLASS_NUMBER
            keyListener=DigitsKeyListener.getInstance("0123456789")
            imeOptions=EditorInfo.IME_ACTION_DONE
        }else{
            inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            imeOptions=EditorInfo.IME_ACTION_SEARCH
        }
    }
''',
    'large wrapped scanner',
)
once(
    '        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(76),1f))\n',
    '        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(128),1f))\n',
    'staff scanner explicit height',
)

# Refresh shared history automatically when another admin changes operational data.
once(
    '                    "REPORT" -> reportScreen()\n',
    '                    "REPORT" -> reportScreen()\n                    "HISTORY" -> historyScreen()\n',
    'history foreground refresh',
)

# Shared server history: one MNV card outside, detailed session timeline on tap.
block(
    '    private fun historyScreen(){',
    '    private fun syncScreen(){',
    r'''    private fun historyScreen(){
        module="HISTORY"
        screenState="HISTORY"
        val root=baseRoot("LỊCH SỬ CHUNG")
        val body=body()
        val summaryBox=column(bg)
        val state=info("Đang tải lịch sử chung từ hệ thống...")
        val box=column(bg)
        body.addView(summaryBox,matchWrap())
        body.addView(state,matchWrap())
        body.addView(gap(6))
        body.addView(box,matchWrap())
        api.call("history_shared"){r->runOnUiThread{
            if(handleAuth(r))return@runOnUiThread
            summaryBox.removeAllViews();box.removeAllViews()
            if(!r.ok){state.text=r.error?:"Không tải được lịch sử chung";return@runOnUiThread}
            val j=r.json?:JSONObject()
            val items=j.optJSONArray("items")?:JSONArray()
            state.text="Hôm nay • ${j.optString("business_date")} • dùng chung giữa các tài khoản"
            val metrics=row(bg)
            metrics.addView(metric("Nhân sự",j.optInt("total").toString(),navy),LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(2)})
            metrics.addView(metric("Đang ca",j.optInt("active_count").toString(),green),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(1);marginEnd=dp(1)})
            metrics.addView(metric("Đã ra",j.optInt("ended_count").toString(),teal),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2)})
            summaryBox.addView(metrics,matchWrap());summaryBox.addView(gap(6))
            if(items.length()==0){box.addView(info("Chưa có lịch sử nghiệp vụ trong ngày."));return@runOnUiThread}
            for(i in 0 until items.length()){
                val x=items.optJSONObject(i)?:continue
                val mnv=x.optString("mnv"),fullName=x.optString("full_name")
                val ended=x.optString("state")=="ENDED"
                val lastTime=x.optString("last_time").substringAfter(" ",x.optString("last_time"))
                val actor=x.optString("last_actor").ifBlank{"—"}
                val card=column(surface).apply{
                    setPadding(dp(11),dp(9),dp(11),dp(9));background=outlineBg(surface,11)
                    addView(txt("$mnv • ${fullName.ifBlank{"Chưa có tên"}}",12.3f,ink,true).apply{maxLines=2})
                    addView(gap(2))
                    addView(txt("${x.optString("shift").ifBlank{"—"}} • ${if(ended)"Đã ra ca" else "Đang trong ca"} • ${x.optInt("event_count")} thao tác",9.4f,if(ended)muted else green,false).apply{maxLines=2})
                    addView(txt("Mới nhất: $lastTime • ${x.optString("last_label").ifBlank{"—"}} • $actor",9.1f,muted,false).apply{maxLines=2})
                    setOnClickListener{historyTimelineScreen(mnv,fullName)}
                }
                box.addView(card,matchWrap());box.addView(gap(5))
            }
        }}
        attach(root,body)
    }

    private fun historyTimelineScreen(mnv:String,nameHint:String){
        module="HISTORY"
        screenState="HISTORY_DETAIL"
        val root=baseRoot("CHI TIẾT LỊCH SỬ")
        val body=body()
        body.addView(listCard("$mnv • ${nameHint.ifBlank{"Nhân sự"}}","Dòng thời gian nghiệp vụ của phiên hôm nay"),matchWrap())
        body.addView(gap(6))
        val box=column(bg);body.addView(box,matchWrap());box.addView(info("Đang tải dòng thời gian..."))
        api.call("history_shared",JSONObject().put("mnv",mnv)){r->runOnUiThread{
            if(handleAuth(r))return@runOnUiThread
            box.removeAllViews()
            if(!r.ok){box.addView(info(r.error?:"Không tải được chi tiết lịch sử"));return@runOnUiThread}
            val timeline=r.json?.optJSONArray("timeline")?:JSONArray()
            if(timeline.length()==0){box.addView(info("Chưa có thao tác cho MNV này."));return@runOnUiThread}
            for(i in 0 until timeline.length()){
                val e=timeline.optJSONObject(i)?:continue
                val last=i==timeline.length()-1
                val lineRow=row(bg).apply{gravity=Gravity.TOP}
                val rail=column(bg).apply{
                    gravity=Gravity.CENTER_HORIZONTAL
                    addView(txt("●",13f,if(e.optString("event_type")=="EXIT")red else teal,true).apply{gravity=Gravity.CENTER},size(dp(24),dp(24)))
                    if(!last)addView(View(this@OperationsActivity).apply{setBackgroundColor(line)},LinearLayout.LayoutParams(dp(2),dp(48)))
                }
                lineRow.addView(rail,LinearLayout.LayoutParams(dp(30),-2))
                val whenText=e.optString("at").substringAfter(" ",e.optString("at"))
                val actor=e.optString("actor").ifBlank{"—"}
                val detail=e.optString("detail").ifBlank{"Không có thông tin bổ sung"}
                lineRow.addView(column(surface).apply{
                    setPadding(dp(10),dp(8),dp(10),dp(8));background=outlineBg(surface,10)
                    addView(txt(e.optString("label").ifBlank{e.optString("event_type")},11.4f,ink,true))
                    addView(txt("$whenText • xử lý bởi $actor",9.2f,muted,false).apply{maxLines=2})
                    addView(gap(3))
                    addView(txt(detail,9.5f,ink,false).apply{maxLines=5})
                },LinearLayout.LayoutParams(0,-2,1f))
                box.addView(lineRow,matchWrap())
                if(!last)box.addView(gap(2))
            }
        }}
        attach(root,body)
    }

''',
    'shared MNV timeline history',
)

once(
    '            "ACCOUNT_MANAGER"->settingsScreen()\n',
    '            "ACCOUNT_MANAGER"->settingsScreen()\n            "HISTORY_DETAIL"->historyScreen()\n',
    'history detail back navigation',
)

ops_path.write_text(text, encoding="utf-8")

# Beta13 no longer records business/admin history in device-local SharedPreferences.
# Authoritative business history is appended server-side only after successful mutations.
api_text = api_path.read_text(encoding="utf-8")
old_ok = 'if(action in tracked) AppHistory.record(appContext,action,result.ok,result.error.orEmpty(),payload)'
old_fail = 'if(action in tracked) AppHistory.record(appContext,action,false,result.error.orEmpty(),payload)'
if api_text.count(old_ok) != 1 or api_text.count(old_fail) != 1:
    raise SystemExit("S13 BetaApiClient local-history anchors changed")
api_text = api_text.replace(old_ok, '// S13 shared history is server-authoritative; no local mutation history.', 1)
api_text = api_text.replace(old_fail, '// Failed requests do not create shared business history.', 1)
api_path.write_text(api_text, encoding="utf-8")

print("S13 shared history + large scanner UI patch applied")
