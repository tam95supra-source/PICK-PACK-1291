#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S36_PERF_HISTORY_REPORT_SERVICE'

def replace_private_fun(src:str, signature:str, replacement:str)->str:
    start=src.find('    private fun '+signature)
    if start<0: raise SystemExit('S36 function anchor missing: '+signature)
    end=src.find('\n    private fun ',start+16)
    if end<0: raise SystemExit('S36 next function anchor missing after: '+signature)
    return src[:start]+replacement.rstrip()+'\n'+src[end:]

s=OPS.read_text(encoding='utf-8')
if MARK in s:
    print('S36 Android already applied');raise SystemExit(0)

# Canonical refresh remains background-only and is strongly cooled down. Do not rerender
# History unless the retained revision map changed; this prevents a second expensive screen build.
refresh=r'''    // S36_PERF_HISTORY_REPORT_SERVICE: bounded background canonical refresh.
    private fun refreshHistoryCanonical(){
        if(historySyncInFlight)return
        val now=System.currentTimeMillis();if(now-historyLastCanonicalRefreshAt<60_000L)return
        val before=operationalStore.revisions().toString()
        historySyncInFlight=true
        Thread{
            val ok=runCatching{M2BackgroundSync.catchUp(applicationContext)}.getOrDefault(false)
            val changed=ok&&before!=operationalStore.revisions().toString()
            runOnUiThread{
                historySyncInFlight=false;historyLastCanonicalRefreshAt=System.currentTimeMillis()
                if(changed&&screenState=="HISTORY")historyScreen()
            }
        }.start()
    }'''
s=replace_private_fun(s,'refreshHistoryCanonical(){',refresh)

report=r'''    // S36_PERF_HISTORY_REPORT_SERVICE: selected-date cached aggregation; no full-day parse on UI thread.
    private fun reportScreen(){
        module="BUSINESS";screenState="REPORT"
        val root=baseRoot("BÁO CÁO NHÂN SỰ");val body=column(bg).apply{setPadding(dp(3),dp(6),dp(3),dp(42))}
        val period=spinner(arrayOf("Ca 1 + Ca HC","Ca 2","Cả ngày"))
        var selectedDate=operationalStore.latestBusinessDate().ifBlank{operationalStore.businessDate()}
        val dateButton=Button(this).apply{text=runCatching{java.time.LocalDate.parse(selectedDate).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}.getOrDefault(selectedDate);textSize=12f;isAllCaps=false;background=outlineBg(surface,14);setTextColor(ink)}
        val controls=row(bg).apply{gravity=Gravity.CENTER_VERTICAL;addView(period,LinearLayout.LayoutParams(0,dp(50),1f).apply{marginEnd=dp(5)});addView(dateButton,LinearLayout.LayoutParams(0,dp(50),1f).apply{marginStart=dp(5)})}
        body.addView(section("Phạm vi báo cáo"));body.addView(controls,matchWrap());body.addView(gap(7))
        val box=column(bg);body.addView(box,matchWrap())
        fun fold(v:String)=java.text.Normalizer.normalize(v,java.text.Normalizer.Form.NFD).replace(Regex("\\p{Mn}+"),"").uppercase().trim()
        fun site1291(v:String):Boolean{val x=fold(v);return x=="1291"||x=="SITE 1291"||Regex("(^|[^0-9])1291([^0-9]|$)").containsMatchIn(x)}
        fun shiftBucket(v:String):String{val x=fold(v).replace(Regex("\\s+")," ");return when{x=="CA 1"||x=="CA1"||x=="1"->"CA1";x=="CA HC"||x=="CAHC"||x=="HC"||x.contains("HANH CHINH")->"HC";x=="CA 2"||x=="CA2"||x=="2"->"CA2";else->x}}
        fun supplierCode(raw:String):String{val x=fold(raw);return when{x=="INHOUSE"||x=="IH"->"IH";x=="NGUON LUC VIET"||x=="NLV"->"NLV";x=="VIET WORK"||x=="VW"->"VW";x=="MAN POWER"||x=="MP"->"MP";x=="MEGA LINK"||x=="MGL"->"MGL";x=="HA GIA PHAT"||x=="HGP"->"HGP";x=="HOA ANH DAO"||x=="HAD"->"HAD";else->raw.trim().ifBlank{"Khác"}}}
        fun reportPosition(emp:JSONObject,work:String):String{val p=fold(emp.optString("main_position"));val d=fold(emp.optString("department"));return when{p=="TRUONG NHOM"->"Trưởng nhóm";p=="CHUYEN VIEN"->"Chuyên viên";p=="TO TRUONG"->"Tổ trưởng";p.contains("DIEU PHOI")&&d.contains("PACK")->"Điều phối khu pack";p.contains("DIEU PHOI")&&(d.contains("CHO XUAT")||d.contains("GIAO VAN")||d.contains("OUTBOUND"))->"Điều phối khu chờ xuất";p.contains("KEO HANG")->"Kéo hàng";p=="5S"||p.contains(" 5S")->"5S";p.contains("PHUC LONG")->"Phúc Long";fold(work)=="PICK"||p.contains("PICK")->"Picker";fold(work)=="PACK"||p.contains("PACK")->"Packer";else->emp.optString("main_position").ifBlank{"Khác"}}}
        fun tenureLabel(emp:JSONObject,date:String):String{val raw=emp.optString("start_date").trim();if(raw.isBlank())return "Nhân sự cũ";val started=runCatching{if(raw.matches(Regex("\\d{2}/\\d{2}/\\d{4}")))java.time.LocalDate.parse(raw,DateTimeFormatter.ofPattern("dd/MM/yyyy"))else java.time.LocalDate.parse(raw.take(10))}.getOrNull()?:return "Nhân sự cũ";val target=runCatching{java.time.LocalDate.parse(date)}.getOrNull()?:return "Nhân sự cũ";return if(java.time.temporal.ChronoUnit.DAYS.between(started,target)<=30)"Nhân sự mới" else "Nhân sự cũ"}
        data class Entry(val mnv:String,val shift:String,val work:String,val emp:JSONObject)
        var cachedDate="";var cachedEntries:List<Entry> = emptyList();var loadSerial=0
        fun makeGrid(rows:List<Entry>,kind:String,date:String):JSONObject{
            val columns=listOf("IH","NLV","VW","MP","MGL","HGP","HAD").filter{c->rows.any{supplierCode(it.emp.optString("supplier"))==c}}
            val rowOrder=if(kind=="position")listOf("Trưởng nhóm","Chuyên viên","Tổ trưởng","Điều phối khu pack","Điều phối khu chờ xuất","Kéo hàng","5S","Picker","Packer","Phúc Long","Khác") else listOf("Nhân sự mới","Nhân sự cũ")
            val values=LinkedHashMap<String,MutableMap<String,Int>>();rowOrder.forEach{values[it]=LinkedHashMap()}
            rows.forEach{r->val label=if(kind=="position")reportPosition(r.emp,r.work) else tenureLabel(r.emp,date);val key=if(values.containsKey(label))label else if(kind=="position")"Khác" else label;val sup=supplierCode(r.emp.optString("supplier"));values.getOrPut(key){LinkedHashMap()}[sup]=(values[key]?.get(sup)?:0)+1}
            val outRows=JSONArray();rowOrder.forEach{label->val counts=JSONObject();var total=0;columns.forEach{c->val n=values[label]?.get(c)?:0;counts.put(c,n);total+=n};if(total>0||kind!="position")outRows.put(JSONObject().put(if(kind=="position")"position" else "label",label).put("counts",counts).put("total",total))};val totals=JSONObject();var grand=0;columns.forEach{c->val n=rowOrder.sumOf{values[it]?.get(c)?:0};totals.put(c,n);grand+=n};return JSONObject().put("columns",JSONArray(columns)).put("rows",outRows).put("totals",totals).put("total",grand)
        }
        fun renderCached(){
            box.removeAllViews();if(cachedDate!=selectedDate){box.addView(info("Đang đọc snapshot $selectedDate từ bộ nhớ PDA…"));return}
            val selected=cachedEntries.filter{when(period.selectedItemPosition){0->shiftBucket(it.shift) in setOf("CA1","HC");1->shiftBucket(it.shift)=="CA2";else->true}}
            val shown=runCatching{java.time.LocalDate.parse(selectedDate).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}.getOrDefault(selectedDate)
            box.addView(info("Site 1291 • Ngày báo cáo $shown • ${selected.size} nhân sự vào ca • Nhà thầu: IH / NLV / VW / MP / MGL / HGP / HAD"));box.addView(gap(5))
            box.addView(reportGrid("",makeGrid(selected,"position",selectedDate),"Vị trí","position"));box.addView(gap(4));box.addView(reportGrid("",makeGrid(selected,"tenure",selectedDate),"Thâm niên","label"))
            if(cachedEntries.isEmpty())box.addView(info("Chưa có snapshot ngày đã chọn trên PDA. Chọn ngày khác hoặc đồng bộ để tải dữ liệu canonical."))
        }
        fun loadDate(){
            val serial=++loadSerial;cachedDate="";box.removeAllViews();box.addView(info("Đang đọc báo cáo $selectedDate…"))
            Thread{
                val out=LinkedHashMap<String,Entry>();val day=operationalStore.loadDay(selectedDate);val events=day?.optJSONArray("events")?:JSONArray()
                for(i in 0 until events.length()){
                    val e=events.optJSONObject(i)?:continue;if(e.optString("event_type").uppercase()!="ATTENDANCE_ENTER")continue
                    val p=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrDefault(JSONObject());val after=p.optJSONObject("after");val snap=p.optJSONObject("employee_snapshot")?:after?.optJSONObject("employee_snapshot")
                    val mnv=e.optString("mnv").ifBlank{p.optString("mnv")}.ifBlank{after?.optString("mnv").orEmpty()}.ifBlank{snap?.optString("mnv").orEmpty()};if(mnv.isBlank())continue
                    val emp=MasterDataCache.employee(this,mnv)?:snap?:JSONObject();if(!site1291(emp.optString("site")))continue
                    val shift=e.optString("shift").ifBlank{p.optString("shift")}.ifBlank{after?.optString("shift").orEmpty()};val work=e.optString("work_choice").ifBlank{p.optString("work_choice")}.ifBlank{after?.optString("work_choice").orEmpty()}
                    val key=e.optString("entity_id").ifBlank{e.optString("session_id")}.ifBlank{e.optString("event_id")}.ifBlank{"$mnv|$shift|$i"};out[key]=Entry(mnv,shift,work,emp)
                }
                runOnUiThread{if(serial==loadSerial&&screenState=="REPORT"){cachedDate=selectedDate;cachedEntries=out.values.toList();renderCached()}}
            }.start()
        }
        dateButton.setOnClickListener{
            val d=runCatching{java.time.LocalDate.parse(selectedDate)}.getOrDefault(java.time.LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh")))
            android.app.DatePickerDialog(this,{_,y,m,day->selectedDate=java.time.LocalDate.of(y,m+1,day).toString();dateButton.text=java.time.LocalDate.parse(selectedDate).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"));loadDate()},d.year,d.monthValue-1,d.dayOfMonth).show()
        }
        period.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){if(cachedDate==selectedDate)renderCached()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit}
        attach(root,body);loadDate()
    }'''
s=replace_private_fun(s,'reportScreen(){',report)

history=r'''    // S36_PERF_HISTORY_REPORT_SERVICE: selected-date history, bounded global search, pagination and Service telemetry.
    private fun historyScreen(){
        module="HISTORY";screenState="HISTORY";historyDetailMnv="";historyDetailName=""
        val root=baseRoot("LỊCH SỬ");val body=body();var selectedDate=operationalStore.latestBusinessDate().ifBlank{operationalStore.businessDate()};var filter="ALL";var pageSize=60;var query=""
        val serviceBox=column(surface).apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(surface,16)};serviceBox.addView(txt("SERVICE • đang đọc trạng thái…",11f,navy,true));body.addView(serviceBox,matchWrap());body.addView(gap(7))
        val q=input("Tìm MNV, họ tên, nghiệp vụ, người xử lý",false).apply{setSingleLine(true)};val dateButton=Button(this).apply{text=runCatching{java.time.LocalDate.parse(selectedDate).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}.getOrDefault(selectedDate);textSize=11f;isAllCaps=false;background=outlineBg(surface,14);setTextColor(ink)}
        val searchRow=row(bg).apply{addView(q,LinearLayout.LayoutParams(0,dp(50),1f).apply{marginEnd=dp(5)});addView(dateButton,size(dp(112),dp(50)))};body.addView(searchRow,matchWrap());body.addView(gap(7))
        val metrics=row(bg);val allBtn=metric("Tổng","0",navy);val pendingBtn=metric("Chờ","0",Color.rgb(217,119,6));val failBtn=metric("Cần xử lí","0",red);metrics.addView(allBtn,LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(2)});metrics.addView(pendingBtn,LinearLayout.LayoutParams(0,-2,1f).apply{setMargins(dp(2),0,dp(2),0)});metrics.addView(failBtn,LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2)});body.addView(metrics,matchWrap());body.addView(gap(7))
        val box=column(bg);body.addView(box,matchWrap())
        fun friendly(type:String,label:String):String=when(type.uppercase()){ "ATTENDANCE_ENTER","ENTER"->"Vào ca";"ATTENDANCE_EXIT","EXIT"->"Ra ca";"RESOURCE_CHANGE"->"Đổi tài nguyên";"LABOR_START"->"Bắt đầu công nhật";"LABOR_FINISH"->"Hoàn thành công nhật";"ADMIN_AUDIT"->"Thao tác quản trị";"MASTER_STAFF_UPSERT"->"Cập nhật nhân sự";"MASTER_STAFF_DELETE"->"Xóa nhân sự";"ACCOUNT_UPSERT"->"Tạo / sửa tài khoản";"ACCOUNT_STATUS"->"Đổi trạng thái tài khoản";"ACCOUNT_EMAIL"->"Đổi email tài khoản";"ACCOUNT_PASSWORD"->"Đổi mật khẩu";else->label.ifBlank{type.ifBlank{"Thao tác"}} }
        fun statusOf(e:JSONObject):String{val s=e.optString("local_status").uppercase();return when{s in setOf("REJECTED","REVIEW_REQUIRED","CONFLICT","FAILED","ERROR")->"FAILED";s in setOf("LOCAL_PENDING","PENDING","RETRY","OFFLINE_PROVISIONAL")->"PENDING";else->"SYNCED"}}
        fun eventDate(e:JSONObject,fallback:String):String=e.optString("business_date").ifBlank{e.optString("cache_business_date")}.ifBlank{runCatching{java.time.Instant.parse(e.optString("at_iso").ifBlank{e.optString("at")}).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).toLocalDate().toString()}.getOrDefault(fallback)}
        fun scanDate(date:String,needle:String,remaining:Int,out:MutableList<JSONObject>){
            if(remaining<=0)return;val day=operationalStore.loadDay(date)?:return;val events=day.optJSONArray("events")?:JSONArray();val n=needle.uppercase()
            for(i in 0 until events.length()){
                if(out.size>=remaining)return;val e=events.optJSONObject(i)?:continue;val type=e.optString("event_type");var mnv=e.optString("mnv");var full=e.optString("full_name");var actor=e.optString("actor").ifBlank{e.optString("actor_id")};var detail=e.optString("detail");var shift=e.optString("shift")
                var p:JSONObject?=null;if(mnv.isBlank()||full.isBlank()||actor.isBlank()||detail.isBlank()||n.isNotBlank()){p=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrNull();mnv=mnv.ifBlank{p?.optString("mnv").orEmpty()};full=full.ifBlank{p?.optString("full_name").orEmpty()};actor=actor.ifBlank{p?.optString("actor").orEmpty()};detail=detail.ifBlank{p?.optString("detail").orEmpty().ifBlank{p?.optString("labor_type").orEmpty()}};shift=shift.ifBlank{p?.optString("shift").orEmpty()}}
                if(full.isBlank()&&mnv.isNotBlank())full=MasterDataCache.employee(this,mnv)?.optString("full_name").orEmpty();val label=friendly(type,e.optString("label"));if(n.isNotBlank()&&!listOf(mnv,full,label,actor,detail,shift).any{it.uppercase().contains(n)})continue
                out.add(JSONObject().put("event_id",e.optString("event_id").ifBlank{"$date:$i"}).put("event_type",type).put("label",label).put("mnv",mnv).put("full_name",full).put("actor",actor).put("detail",detail).put("shift",shift).put("at_iso",e.optString("at_iso").ifBlank{e.optString("committed_at")}.ifBlank{e.optString("at")}).put("authority_seq",e.optLong("authority_seq",0L)).put("business_date",date).put("history_source","SERVICE_CANONICAL").put("local_status","CONFIRMED"))
            }
        }
        fun loadRows():MutableList<JSONObject>{
            val out=mutableListOf<JSONObject>();val needle=query.trim();if(needle.isBlank())scanDate(selectedDate,"",1800,out) else for(d in operationalStore.availableDates()){if(out.size>=300)break;scanDate(d,needle,300,out)}
            for(local in operationalStore.localHistory(600)){
                val bodyJ=local.optJSONObject("body")?:continue;val payload=bodyJ.optJSONObject("payload")?:bodyJ;val d=payload.optString("business_date").ifBlank{bodyJ.optString("business_date")}.ifBlank{runCatching{java.time.Instant.ofEpochMilli(local.optLong("queued_at")).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).toLocalDate().toString()}.getOrDefault(selectedDate)};if(needle.isBlank()&&d!=selectedDate)continue
                val id=local.optString("event_id");val idx=out.indexOfFirst{it.optString("event_id")==id};if(idx>=0){out[idx].put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at"));continue}
                val action=bodyJ.optString("action");val mnv=payload.optString("mnv").ifBlank{bodyJ.optString("target_id")};val full=payload.optString("full_name").ifBlank{bodyJ.optString("target_label")}.ifBlank{MasterDataCache.employee(this,mnv)?.optString("full_name").orEmpty()};val actor=payload.optString("actor").ifBlank{payload.optString("login_id")}.ifBlank{"Thiết bị này"};val detail=bodyJ.optString("detail").ifBlank{payload.optString("labor_type")};val label=friendly(action.uppercase(),action)
                if(needle.isNotBlank()&&!listOf(mnv,full,label,actor,detail).any{it.uppercase().contains(needle.uppercase())})continue
                out.add(JSONObject().put("event_id",id).put("event_type",action.uppercase()).put("label",label).put("mnv",mnv).put("full_name",full).put("actor",actor).put("detail",detail).put("business_date",d).put("history_source","LOCAL_PDA").put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at")))
            }
            out.sortByDescending{e->val qAt=e.optLong("local_queued_at",0L);if(qAt>0)qAt else runCatching{java.time.Instant.parse(e.optString("at_iso")).toEpochMilli()}.getOrDefault(0L)};return out
        }
        fun render(){
            box.removeAllViews();val rows=loadRows();val groups=rows.groupBy{e->e.optString("mnv").ifBlank{e.optString("event_id")}}.entries.sortedByDescending{entry->entry.value.maxOfOrNull{e->e.optLong("local_queued_at",0L).takeIf{it>0}?:runCatching{java.time.Instant.parse(e.optString("at_iso")).toEpochMilli()}.getOrDefault(0L)}?:0L};val states=groups.map{g->if(g.value.any{statusOf(it)=="FAILED"})"FAILED" else if(g.value.any{statusOf(it)=="PENDING"})"PENDING" else "SYNCED"};val pending=states.count{it=="PENDING"};val failed=states.count{it=="FAILED"}
            fun updateMetric(v:View,n:Int){if(v is LinearLayout&&v.childCount>1)(v.getChildAt(1) as? TextView)?.text=n.toString()};updateMetric(allBtn,groups.size);updateMetric(pendingBtn,pending);updateMetric(failBtn,failed)
            val filtered=groups.filterIndexed{idx,_->filter=="ALL"||states[idx]==filter};val visible=filtered.take(pageSize)
            if(query.isNotBlank())box.addView(info("Tìm trên toàn bộ lịch sử đang giữ trên PDA • tối đa 300 kết quả trước khi nhóm."))
            for(g in visible){val items=g.value;val first=items.first();val state=if(items.any{statusOf(it)=="FAILED"})"FAILED" else if(items.any{statusOf(it)=="PENDING"})"PENDING" else "SYNCED";val label=when(state){"FAILED"->"Lỗi đồng bộ";"PENDING"->"Chưa đồng bộ";else->"Đã đồng bộ"};val tint=when(state){"FAILED"->Color.rgb(254,242,242);"PENDING"->Color.rgb(255,251,235);else->Color.rgb(240,253,250)};val mnv=first.optString("mnv");val full=first.optString("full_name");val last=items.first();val card=column(tint).apply{setPadding(dp(13),dp(11),dp(13),dp(11));background=outlineBg(tint,17);val top=row(tint).apply{gravity=Gravity.CENTER_VERTICAL;addView(txt(listOf(mnv,full).filter{it.isNotBlank()}.joinToString(" – ").ifBlank{"Thao tác hệ thống"},12.5f,ink,true),LinearLayout.LayoutParams(0,-2,1f));addView(badge(label,when(state){"FAILED"->red;"PENDING"->Color.rgb(217,119,6);else->teal}))};addView(top,matchWrap());addView(txt("${last.optString("label")} • ${formatIso(last.optString("at_iso"))} • ${last.optString("actor").ifBlank{"Hệ thống"}}",10f,muted,false));if(last.optString("detail").isNotBlank())addView(txt(last.optString("detail"),9.5f,muted,false).apply{maxLines=2});setOnClickListener{historyTimelineScreen(mnv,items.toMutableList())}};box.addView(card,matchWrap());box.addView(gap(6))}
            if(visible.isEmpty())box.addView(info("Không có lịch sử phù hợp."));if(filtered.size>visible.size)box.addView(primary("XEM THÊM ${filtered.size-visible.size}",teal){pageSize+=60;render()},matchWrap())
        }
        allBtn.setOnClickListener{filter="ALL";pageSize=60;render()};pendingBtn.setOnClickListener{filter="PENDING";pageSize=60;render()};failBtn.setOnClickListener{filter="FAILED";pageSize=60;render()}
        q.addTextChangedListener(object:TextWatcher{override fun beforeTextChanged(v:CharSequence?,st:Int,c:Int,a:Int)=Unit;override fun onTextChanged(v:CharSequence?,st:Int,b:Int,c:Int){query=v?.toString().orEmpty();pageSize=60;render()};override fun afterTextChanged(v:Editable?)=Unit})
        dateButton.setOnClickListener{val d=runCatching{java.time.LocalDate.parse(selectedDate)}.getOrDefault(java.time.LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh")));android.app.DatePickerDialog(this,{_,y,m,day->selectedDate=java.time.LocalDate.of(y,m+1,day).toString();dateButton.text=java.time.LocalDate.parse(selectedDate).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"));pageSize=60;if(query.isBlank())render()},d.year,d.monthValue-1,d.dayOfMonth).show()}
        attach(root,body);render();refreshHistoryCanonical()
        val started=android.os.SystemClock.elapsedRealtime();api.call("sync_status",JSONObject()){r->runOnUiThread{if(screenState!="HISTORY")return@runOnUiThread;serviceBox.removeAllViews();val j=r.json;val rt=android.os.SystemClock.elapsedRealtime()-started;if(!r.ok||j==null){serviceBox.addView(txt("SERVICE • không đọc được telemetry (${r.error?:r.code})",10.5f,red,true));return@runOnUiThread};val a=j.optJSONObject("authority")?:JSONObject();val rep=j.optJSONObject("replication")?:JSONObject();val exact=j.optInt("realtime_connections",-1);val recent=j.optInt("online_recent_devices",-1);serviceBox.addView(txt("SERVICE • Hoạt động • RTT ${rt} ms",11f,teal,true));serviceBox.addView(txt("Authority ${a.optString("mode")} • epoch ${a.optLong("authority_epoch")} • seq ${a.optLong("authority_seq")} • ${a.optString("scope")}",9.6f,ink,false));serviceBox.addView(txt("Replication ${rep.optString("state")} • pending ${rep.optInt("pending_count")} • ${rep.optString("last_error_class").ifBlank{"không lỗi"}}",9.6f,ink,false));serviceBox.addView(txt("Realtime đang nối: ${if(exact>=0)exact else "—"} • Online gần đây ≤${j.optInt("online_window_seconds",90)}s: ${if(recent>=0)recent else "—"}",9.6f,navy,true));serviceBox.addView(txt("Ngày realtime ${j.optString("realtime_business_date").ifBlank{"—"}} • generation ${j.optString("service_generation")}",9.2f,muted,false))}}
    }'''
s=replace_private_fun(s,'historyScreen(){',history)

OPS.write_text(s,encoding='utf-8')
o=OPS.read_text(encoding='utf-8')
for x in [MARK,'realtime_connections','online_recent_devices','DatePickerDialog','Nhà thầu: IH / NLV / VW / MP / MGL / HGP / HAD','localHistory(600)','pageSize=60','now-historyLastCanonicalRefreshAt<60_000L']:
    if x not in o: raise SystemExit('S36 Android contract missing: '+x)
print('Applied S36: low-allocation selected-date History/Report + Service online telemetry')
