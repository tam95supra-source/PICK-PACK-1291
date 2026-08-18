#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
text = path.read_text(encoding="utf-8")


def once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"S14 anchor {label!r}: expected 1, got {count}")
    text = text.replace(old, new, 1)


def block(start_marker: str, end_marker: str, replacement: str, label: str) -> None:
    global text
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"S14 block start {label!r} not found")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"S14 block end {label!r} not found")
    text = text[:start] + replacement + text[end:]

# Foreground refresh keeps the device snapshots warm without blocking navigation.
once(
    '        if (api.token != null) foregroundSync.start()\n',
    '        if (api.token != null) { foregroundSync.start(); warmOperationalCaches(false) }\n',
    'warm cache on start',
)
once(
    '                if (!status.connected || !status.changed) return\n',
    '                if (!status.connected || !status.changed) return\n                warmOperationalCaches(true)\n',
    'warm cache on server revision',
)

# Scanner fields: numeric configuration first, wrapping last. This preserves numeric input while
# allowing contextual hints to occupy 2-3 lines. Staff search is intentionally shorter.
block(
    '    private fun scanField(',
    '    private fun bindScannerEnter(',
    r'''    private fun scanField(h:String,numeric:Boolean,heightDp:Int)=input(h,false).apply{
        if(numeric){
            inputType=InputType.TYPE_CLASS_NUMBER
            keyListener=DigitsKeyListener.getInstance("0123456789")
            imeOptions=EditorInfo.IME_ACTION_DONE
        }else{
            inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            imeOptions=EditorInfo.IME_ACTION_SEARCH
        }
        setSingleLine(false)
        minLines=2
        maxLines=3
        setHorizontallyScrolling(false)
        gravity=Gravity.CENTER_VERTICAL
        minHeight=dp(heightDp)
        textSize=13.0f
        setPadding(dp(12),dp(10),dp(12),dp(10))
        setCompoundDrawablesWithIntrinsicBounds(R.drawable.ic_pp_scan,0,0,0)
        compoundDrawableTintList=ColorStateList.valueOf(teal)
        compoundDrawablePadding=dp(9)
    }
    private fun mnvInput(h:String)=scanField(h,true,104)
    private fun scanSearchInput(h:String)=scanField(h,false,92)
''',
    'scanner helpers',
)
once(
    '        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(128),1f))\n',
    '        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(92),1f))\n',
    'staff search height',
)

# Report: render device snapshot immediately, then revalidate and replace it in-place.
block(
    '    private fun reportScreen(){',
    '    private fun reportTable(',
    r'''    private fun warmOperationalCaches(force:Boolean){
        val maxAge=if(force)0L else 60_000L
        if(force || OperationalViewCache.ageMs(this,"report_daily")>maxAge){
            cacheApi.call("report_daily"){r->if(r.ok&&r.json!=null)OperationalViewCache.save(applicationContext,"report_daily",r.json)}
        }
        if(force || OperationalViewCache.ageMs(this,"history_shared")>maxAge){
            cacheApi.call("history_shared"){r->if(r.ok&&r.json!=null)OperationalViewCache.save(applicationContext,"history_shared",r.json)}
        }
    }

    private fun reportScreen(){
        screenState="REPORT"
        val root=baseRoot("BÁO CÁO")
        val body=column(bg).apply{setPadding(dp(3),dp(4),dp(3),dp(32))}
        val period=spinner(arrayOf("Ca 1 + Ca HC","Ca 2","Cả ngày")).apply{minimumHeight=dp(42)}
        body.addView(period,matchWrap());body.addView(gap(3))
        val state=txt("",8.9f,muted,false).apply{setPadding(dp(2),dp(1),dp(2),dp(3))}
        val box=column(bg)
        body.addView(state,matchWrap());body.addView(box,matchWrap())
        var reportJson:JSONObject?=null
        fun render(){
            val rootJson=reportJson?:return
            box.removeAllViews()
            val key=when(period.selectedItemPosition){0->"ca1_hc";1->"ca2";else->"all"}
            val p=rootJson.optJSONObject("reports")?.optJSONObject(key)?:JSONObject()
            box.addView(reportTable("",p.optJSONObject("manpower"),"Vị trí","position",true),matchWrap())
            box.addView(gap(5));box.addView(reportTable("Thâm niên Picker",p.optJSONObject("picker_tenure"),"Thâm niên","label",false),matchWrap())
            box.addView(gap(5));box.addView(reportTable("Thâm niên Packer",p.optJSONObject("packer_tenure"),"Thâm niên","label",false),matchWrap())
            val support=p.optJSONObject("support")
            if((support?.optInt("total")?:0)>0){
                box.addView(gap(5));box.addView(reportTable("Hỗ trợ bộ phận khác",support,"Hỗ trợ","label",false),matchWrap())
                val remaining=p.optJSONObject("remaining")?:JSONObject();val rp=remaining.optJSONObject("picker")?:JSONObject();val rk=remaining.optJSONObject("packer")?:JSONObject()
                box.addView(gap(5));box.addView(column(ThemeManager.soft(this)).apply{
                    setPadding(dp(8),dp(6),dp(8),dp(6));background=outlineBg(ThemeManager.soft(this@OperationsActivity),8)
                    addView(txt("Sau khấu trừ hỗ trợ",9.6f,navy,true))
                    addView(txt("Picker: ${rp.optInt("total")}  •  Cũ ${rp.optInt("old")}  •  Mới ${rp.optInt("new")}",9.4f,ink,false))
                    addView(txt("Packer: ${rk.optInt("total")}  •  Cũ ${rk.optInt("old")}  •  Mới ${rk.optInt("new")}",9.4f,ink,false))
                },matchWrap())
            }
        }
        period.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{
            override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){render()}
            override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit
        }
        val cached=OperationalViewCache.load(this,"report_daily")
        if(cached!=null){reportJson=cached;state.text="Dữ liệu lưu trên máy • đang làm mới...";render()}
        else {state.text="Đang tải báo cáo lần đầu...";box.addView(txt("Đang tải báo cáo...",10f,muted,false))}
        api.call("report_daily"){r->runOnUiThread{
            if(handleAuth(r))return@runOnUiThread
            if(!r.ok){state.text=if(reportJson!=null)"Đang dùng dữ liệu lưu trên máy • chưa làm mới được" else (r.error?:"Không tải được báo cáo");return@runOnUiThread}
            reportJson=r.json?:JSONObject();OperationalViewCache.save(this@OperationsActivity,"report_daily",reportJson!!)
            state.text="Đã đồng bộ dữ liệu mới";render()
        }}
        attach(root,body)
    }

''',
    'report stale while revalidate',
)

# Shared history: cached summary and cached per-MNV timeline render first; server always revalidates.
block(
    '    private fun historyScreen(){',
    '    private fun syncScreen(){',
    r'''    private fun historyScreen(){
        module="HISTORY";screenState="HISTORY"
        val root=baseRoot("LỊCH SỬ CHUNG");val body=body();val summaryBox=column(bg)
        val state=txt("",8.9f,muted,false).apply{setPadding(dp(2),dp(1),dp(2),dp(3))};val box=column(bg)
        body.addView(summaryBox,matchWrap());body.addView(state,matchWrap());body.addView(box,matchWrap())
        fun renderHistory(j:JSONObject){
            summaryBox.removeAllViews();box.removeAllViews();val items=j.optJSONArray("items")?:JSONArray()
            val metrics=row(bg)
            metrics.addView(metric("Nhân sự",j.optInt("total").toString(),navy),LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(2)})
            metrics.addView(metric("Đang ca",j.optInt("active_count").toString(),green),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(1);marginEnd=dp(1)})
            metrics.addView(metric("Đã ra",j.optInt("ended_count").toString(),teal),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2)})
            summaryBox.addView(metrics,matchWrap());summaryBox.addView(gap(5))
            if(items.length()==0){box.addView(info("Chưa có lịch sử nghiệp vụ trong ngày."));return}
            for(i in 0 until items.length()){
                val x=items.optJSONObject(i)?:continue;val mnv=x.optString("mnv");val fullName=x.optString("full_name")
                val ended=x.optString("state")=="ENDED";val lastTime=x.optString("last_time").substringAfter(" ",x.optString("last_time"));val actor=x.optString("last_actor").ifBlank{"—"}
                val card=column(surface).apply{
                    setPadding(dp(10),dp(7),dp(10),dp(7));background=outlineBg(surface,10)
                    addView(txt("$mnv • ${fullName.ifBlank{"Chưa có tên"}}",11.7f,ink,true).apply{maxLines=2})
                    addView(txt("${x.optString("shift").ifBlank{"—"}} • ${if(ended)"Đã ra ca" else "Đang trong ca"} • ${x.optInt("event_count")} thao tác",9.1f,if(ended)muted else green,false).apply{maxLines=2})
                    addView(txt("$lastTime • ${x.optString("last_label").ifBlank{"—"}} • $actor",8.9f,muted,false).apply{maxLines=2})
                    setOnClickListener{historyTimelineScreen(mnv,fullName)}
                }
                box.addView(card,matchWrap());box.addView(gap(4))
            }
        }
        val cached=OperationalViewCache.load(this,"history_shared")
        if(cached!=null){state.text="Dữ liệu lưu trên máy • đang làm mới...";renderHistory(cached)}
        else {state.text="Đang tải lịch sử chung lần đầu...";box.addView(info("Đang tải lịch sử chung từ hệ thống..."))}
        api.call("history_shared"){r->runOnUiThread{
            if(handleAuth(r))return@runOnUiThread
            if(!r.ok){state.text=if(cached!=null)"Đang dùng dữ liệu lưu trên máy • chưa làm mới được" else (r.error?:"Không tải được lịch sử chung");return@runOnUiThread}
            val j=r.json?:JSONObject();OperationalViewCache.save(this@OperationsActivity,"history_shared",j);state.text="Đã đồng bộ dữ liệu mới";renderHistory(j)
        }}
        attach(root,body)
    }

    private fun historyTimelineScreen(mnv:String,nameHint:String){
        module="HISTORY";screenState="HISTORY_DETAIL"
        val root=baseRoot("CHI TIẾT LỊCH SỬ");val body=body()
        body.addView(listCard("$mnv • ${nameHint.ifBlank{"Nhân sự"}}","Dòng thời gian nghiệp vụ của phiên hôm nay"),matchWrap());body.addView(gap(5))
        val state=txt("",8.9f,muted,false);body.addView(state,matchWrap());val box=column(bg);body.addView(box,matchWrap())
        fun renderTimeline(j:JSONObject){
            box.removeAllViews();val timeline=j.optJSONArray("timeline")?:JSONArray()
            if(timeline.length()==0){box.addView(info("Chưa có thao tác cho MNV này."));return}
            for(i in 0 until timeline.length()){
                val e=timeline.optJSONObject(i)?:continue;val last=i==timeline.length()-1;val lineRow=row(bg).apply{gravity=Gravity.TOP}
                val rail=column(bg).apply{gravity=Gravity.CENTER_HORIZONTAL;addView(txt("●",13f,if(e.optString("event_type")=="EXIT")red else teal,true).apply{gravity=Gravity.CENTER},size(dp(24),dp(24)));if(!last)addView(View(this@OperationsActivity).apply{setBackgroundColor(line)},LinearLayout.LayoutParams(dp(2),dp(46)))}
                lineRow.addView(rail,LinearLayout.LayoutParams(dp(30),-2));val whenText=e.optString("at").substringAfter(" ",e.optString("at"));val actor=e.optString("actor").ifBlank{"—"};val detail=e.optString("detail").ifBlank{"Không có thông tin bổ sung"}
                lineRow.addView(column(surface).apply{setPadding(dp(9),dp(7),dp(9),dp(7));background=outlineBg(surface,9);addView(txt(e.optString("label").ifBlank{e.optString("event_type")},11.1f,ink,true));addView(txt("$whenText • xử lý bởi $actor",9f,muted,false).apply{maxLines=2});addView(gap(2));addView(txt(detail,9.3f,ink,false).apply{maxLines=5})},LinearLayout.LayoutParams(0,-2,1f))
                box.addView(lineRow,matchWrap());if(!last)box.addView(gap(2))
            }
        }
        val cacheKey=OperationalViewCache.detailKey(mnv);val cached=OperationalViewCache.load(this,cacheKey)
        if(cached!=null){state.text="Dữ liệu lưu trên máy • đang làm mới...";renderTimeline(cached)}else{state.text="Đang tải dòng thời gian...";box.addView(info("Đang tải dòng thời gian..."))}
        api.call("history_shared",JSONObject().put("mnv",mnv)){r->runOnUiThread{
            if(handleAuth(r))return@runOnUiThread
            if(!r.ok){state.text=if(cached!=null)"Đang dùng dữ liệu lưu trên máy • chưa làm mới được" else (r.error?:"Không tải được chi tiết lịch sử");return@runOnUiThread}
            val j=r.json?:JSONObject();OperationalViewCache.save(this@OperationsActivity,cacheKey,j);state.text="Đã đồng bộ dữ liệu mới";renderTimeline(j)
        }}
        attach(root,body)
    }

''',
    'history stale while revalidate',
)

path.write_text(text, encoding="utf-8")
print("S14 device cache + scanner sizing patch applied")
