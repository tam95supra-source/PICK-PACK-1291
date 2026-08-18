#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
text = path.read_text(encoding="utf-8")


def once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"S15 anchor {label!r}: expected 1, got {count}")
    text = text.replace(old, new, 1)


def block(start_marker: str, end_marker: str, replacement: str, label: str) -> None:
    global text
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"S15 block start {label!r} not found")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"S15 block end {label!r} not found")
    text = text[:start] + replacement + text[end:]

# Local-first operational store + revision reconciler.
once(
    '    private val cacheApi by lazy { BetaApiClient(applicationContext) }\n',
    '''    private val cacheApi by lazy { BetaApiClient(applicationContext) }
    private val operationalStore by lazy { OperationalDataStore(applicationContext) }
    private val operationalSync by lazy {
        OperationalSyncEngine(this, cacheApi, operationalStore) { changedDates ->
            runOnUiThread {
                if(changedDates.isEmpty()) return@runOnUiThread
                when(screenState){
                    "REPORT" -> reportScreen()
                    "HISTORY" -> historyScreen()
                }
            }
        }
    }
''',
    'operational store fields',
)
once(
    '                refreshHeaderConnection()\n',
    '''                refreshHeaderConnection()
                if(status.connected && status.businessDate.isNotBlank() && status.retentionFloor.isNotBlank()) {
                    operationalSync.reconcile(status.businessDate,status.retentionFloor,status.retentionEpoch,status.dayRevisions)
                }
''',
    'sync manifest hook',
)
once(
    '                warmOperationalCaches(true)\n',
    '',
    'remove revision screen warming',
)
once(
    '        if (api.token != null) { foregroundSync.start(); warmOperationalCaches(false) }\n',
    '        if (api.token != null) foregroundSync.start()\n',
    'remove screen cache warming',
)

# Compact scan controls: ~2/3 of Beta14 height, stronger visual affordance and wrapped hint.
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
        maxLines=2
        setHorizontallyScrolling(false)
        gravity=Gravity.CENTER_VERTICAL
        minHeight=dp(heightDp)
        maxHeight=dp(heightDp)
        textSize=12.4f
        setHintTextColor(Color.rgb(100,116,139))
        setPadding(dp(12),dp(7),dp(12),dp(7))
        setCompoundDrawablesWithIntrinsicBounds(R.drawable.ic_pp_scan,0,0,0)
        compoundDrawableTintList=ColorStateList.valueOf(teal)
        compoundDrawablePadding=dp(9)
        background=GradientDrawable().apply{
            setColor(ThemeManager.soft(this@OperationsActivity))
            setStroke(dp(1),teal)
            cornerRadius=dp(14).toFloat()
        }
        elevation=0f
    }
    private fun mnvInput(h:String)=scanField(h,true,72)
    private fun scanSearchInput(h:String)=scanField(h,false,72)
''',
    'compact scanner helpers',
)
once(
    '        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(92),1f))\n',
    '        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(72),1f))\n',
    'compact staff search height',
)

# Report is now 100% local. Date choices are exactly the dates present in the 45-day SQLite cache.
block(
    '    private fun warmOperationalCaches(',
    '    private fun reportTable(',
    r'''    private fun reportDateLabel(iso:String):String=runCatching{
        java.time.LocalDate.parse(iso).format(java.time.format.DateTimeFormatter.ofPattern("dd/MM/yyyy"))
    }.getOrDefault(iso)

    private fun reportScreen(){
        screenState="REPORT"
        val root=baseRoot("BÁO CÁO")
        val body=column(bg).apply{setPadding(dp(3),dp(4),dp(3),dp(32))}
        val dates=operationalStore.availableDates()
        if(dates.isEmpty()){
            body.addView(info("Đang đồng bộ dữ liệu lần đầu. Báo cáo sẽ hiện ngay khi dữ liệu ngày gần nhất được lưu trên máy."),matchWrap())
            attach(root,body);return
        }
        val today=operationalStore.businessDate()
        val dateSpinner=spinner(dates.map{reportDateLabel(it)}.toTypedArray()).apply{minimumHeight=dp(42)}
        val todayIndex=dates.indexOf(today);dateSpinner.setSelection(if(todayIndex>=0)todayIndex else 0)
        val period=spinner(arrayOf("Ca 1 + Ca HC","Ca 2","Cả ngày")).apply{minimumHeight=dp(42)}
        val selectors=row(bg).apply{gravity=Gravity.CENTER_VERTICAL}
        selectors.addView(dateSpinner,LinearLayout.LayoutParams(0,dp(42),0.43f).apply{marginEnd=dp(2)})
        selectors.addView(period,LinearLayout.LayoutParams(0,dp(42),0.57f).apply{marginStart=dp(2)})
        body.addView(selectors,matchWrap());body.addView(gap(4))
        val box=column(bg);body.addView(box,matchWrap())
        fun render(){
            box.removeAllViews()
            val date=dates.getOrNull(dateSpinner.selectedItemPosition)?:return
            val snapshot=operationalStore.loadDay(date)
            val rootJson=snapshot?.optJSONObject("report")
            if(rootJson==null){box.addView(info("Chưa có dữ liệu báo cáo cho ngày ${reportDateLabel(date)}."));return}
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
        val listener=object:android.widget.AdapterView.OnItemSelectedListener{
            override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){render()}
            override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit
        }
        dateSpinner.onItemSelectedListener=listener;period.onItemSelectedListener=listener
        render();attach(root,body)
    }

''',
    'local report with cached date selector',
)

# Shared history and timeline read the current-day SQLite snapshot only; no screen-triggered API call.
block(
    '    private fun historyScreen(){',
    '    private fun syncScreen(){',
    r'''    private fun historyScreen(){
        module="HISTORY";screenState="HISTORY"
        val root=baseRoot("LỊCH SỬ CHUNG");val body=body();val summaryBox=column(bg);val box=column(bg)
        body.addView(summaryBox,matchWrap());body.addView(box,matchWrap())
        val dates=operationalStore.availableDates();val today=operationalStore.businessDate();val date=if(dates.contains(today))today else dates.firstOrNull()
        val snapshot=date?.let{operationalStore.loadDay(it)};val j=snapshot?.optJSONObject("history")
        if(j==null){box.addView(info("Đang đồng bộ lịch sử nghiệp vụ gần nhất về máy."));attach(root,body);return}
        val items=j.optJSONArray("items")?:JSONArray()
        val metrics=row(bg)
        metrics.addView(metric("Nhân sự",j.optInt("total").toString(),navy),LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(2)})
        metrics.addView(metric("Đang ca",j.optInt("active_count").toString(),green),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(1);marginEnd=dp(1)})
        metrics.addView(metric("Đã ra",j.optInt("ended_count").toString(),teal),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2)})
        summaryBox.addView(metrics,matchWrap());summaryBox.addView(gap(5))
        if(items.length()==0){box.addView(info("Chưa có lịch sử nghiệp vụ trong ngày."));attach(root,body);return}
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
        attach(root,body)
    }

    private fun historyTimelineScreen(mnv:String,nameHint:String){
        module="HISTORY";screenState="HISTORY_DETAIL"
        val root=baseRoot("CHI TIẾT LỊCH SỬ");val body=body()
        body.addView(listCard("$mnv • ${nameHint.ifBlank{"Nhân sự"}}","Dòng thời gian nghiệp vụ của phiên hôm nay"),matchWrap());body.addView(gap(5))
        val box=column(bg);body.addView(box,matchWrap())
        val dates=operationalStore.availableDates();val today=operationalStore.businessDate();val date=if(dates.contains(today))today else dates.firstOrNull()
        val timeline=JSONArray();val events=date?.let{operationalStore.loadDay(it)}?.optJSONArray("events")?:JSONArray()
        for(i in 0 until events.length()){val e=events.optJSONObject(i)?:continue;if(e.optString("mnv")==mnv)timeline.put(e)}
        if(timeline.length()==0){box.addView(info("Chưa có thao tác cho MNV này."));attach(root,body);return}
        for(i in 0 until timeline.length()){
            val e=timeline.optJSONObject(i)?:continue;val last=i==timeline.length()-1;val lineRow=row(bg).apply{gravity=Gravity.TOP}
            val rail=column(bg).apply{gravity=Gravity.CENTER_HORIZONTAL;addView(txt("●",13f,if(e.optString("event_type")=="EXIT")red else teal,true).apply{gravity=Gravity.CENTER},size(dp(24),dp(24)));if(!last)addView(View(this@OperationsActivity).apply{setBackgroundColor(line)},LinearLayout.LayoutParams(dp(2),dp(46)))}
            lineRow.addView(rail,LinearLayout.LayoutParams(dp(30),-2));val whenText=e.optString("at").substringAfter(" ",e.optString("at"));val actor=e.optString("actor").ifBlank{"—"};val detail=e.optString("detail").ifBlank{"Không có thông tin bổ sung"}
            lineRow.addView(column(surface).apply{setPadding(dp(9),dp(7),dp(9),dp(7));background=outlineBg(surface,9);addView(txt(e.optString("label").ifBlank{e.optString("event_type")},11.1f,ink,true));addView(txt("$whenText • xử lý bởi $actor",9f,muted,false).apply{maxLines=2});addView(gap(2));addView(txt(detail,9.3f,ink,false).apply{maxLines=5})},LinearLayout.LayoutParams(0,-2,1f))
            box.addView(lineRow,matchWrap());if(!last)box.addView(gap(2))
        }
        attach(root,body)
    }

''',
    'local shared history',
)

path.write_text(text, encoding="utf-8")
print("S15 local-first UI + report date selector + compact scanner patch applied")
