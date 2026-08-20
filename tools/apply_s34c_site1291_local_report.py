#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s=OPS.read_text(encoding='utf-8')
MARK='S34C_SITE1291_LOCAL_REPORT'
if MARK in s:
    print('S34C already applied')
    raise SystemExit(0)

start=s.find('    private fun reportScreen(){')
if start<0: raise SystemExit('S34C reportScreen anchor missing')
end=s.find('\n    private fun ',start+24)
if end<0: raise SystemExit('S34C next private function anchor missing')

replacement=r'''    // S34C_SITE1291_LOCAL_REPORT: manpower is derived from the canonical day event snapshot.
    // A person counts on the entry business date as soon as ATTENDANCE_ENTER exists; ATTENDANCE_EXIT is not required.
    private fun reportScreen(){
        screenState="REPORT"
        val root=baseRoot("BÁO CÁO NHÂN SỰ");val body=column(bg).apply{setPadding(dp(3),dp(6),dp(3),dp(42))}
        val period=spinner(arrayOf("Ca 1 + Ca HC","Ca 2","Cả ngày"));body.addView(labelled("Phạm vi báo cáo",period));body.addView(gap(5))
        val box=column(bg);body.addView(box,matchWrap())
        fun fold(v:String)=java.text.Normalizer.normalize(v,java.text.Normalizer.Form.NFD).replace(Regex("\\p{Mn}+"),"").uppercase().trim()
        fun site1291(v:String):Boolean{val x=fold(v);return x=="1291"||x=="SITE 1291"||Regex("(^|[^0-9])1291([^0-9]|$)").containsMatchIn(x)}
        fun shiftBucket(v:String):String{val x=fold(v).replace(Regex("\\s+")," ");return when{x=="CA 1"||x=="CA1"||x=="1"->"CA1";x=="CA HC"||x=="CAHC"||x=="HC"||x.contains("HANH CHINH")->"HC";x=="CA 2"||x=="CA2"||x=="2"->"CA2";else->x}}
        fun supplierCode(raw:String):String{val x=fold(raw);return listOf("IH","NLV","VW","MP","MGL","HGP","HAD").firstOrNull{x==it||x.startsWith("$it ")||x.contains(" $it ")||x.endsWith(" $it")}?:raw.trim().takeIf{it.isNotBlank()}?:"Khác"}
        fun reportPosition(emp:JSONObject,work:String):String{val p=fold(emp.optString("main_position"));val d=fold(emp.optString("department"));return when{p=="TRUONG NHOM"->"Trưởng nhóm";p=="CHUYEN VIEN"->"Chuyên viên";p=="TO TRUONG"->"Tổ trưởng";p.contains("DIEU PHOI")&&d.contains("PACK")->"Điều phối khu pack";p.contains("DIEU PHOI")&&d.contains("CHO XUAT")->"Điều phối khu chờ xuất";p.contains("KEO HANG")->"Kéo hàng";p=="5S"||p.contains(" 5S")->"5S";p.contains("PHUC LONG")->"Phúc Long";fold(work)=="PICK"||p.contains("PICK")->"Picker";fold(work)=="PACK"||p.contains("PACK")->"Packer";else->emp.optString("main_position").ifBlank{"Khác"}}}
        fun tenureLabel(emp:JSONObject):String{val raw=emp.optString("start_date").trim();if(raw.isBlank())return "Nhân sự cũ";val started=runCatching{if(raw.matches(Regex("\\d{2}/\\d{2}/\\d{4}")))java.time.LocalDate.parse(raw,DateTimeFormatter.ofPattern("dd/MM/yyyy"))else java.time.LocalDate.parse(raw.take(10))}.getOrNull()?:return "Nhân sự cũ";return if(java.time.temporal.ChronoUnit.DAYS.between(started,java.time.LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh")))<=30)"Nhân sự mới" else "Nhân sự cũ"}
        data class Entry(val mnv:String,val shift:String,val work:String,val emp:JSONObject)
        fun entriesForToday():List<Entry>{
            val date=operationalStore.businessDate();val day=operationalStore.loadDay(date)?:return emptyList();val events=day.optJSONArray("events")?:JSONArray();val out=LinkedHashMap<String,Entry>()
            for(i in 0 until events.length()){
                val e=events.optJSONObject(i)?:continue;if(e.optString("event_type").uppercase()!="ATTENDANCE_ENTER")continue
                val p=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrDefault(JSONObject());val after=p.optJSONObject("after");val snap=p.optJSONObject("employee_snapshot")?:after?.optJSONObject("employee_snapshot")
                val mnv=e.optString("mnv").ifBlank{p.optString("mnv")}.ifBlank{after?.optString("mnv").orEmpty()}.ifBlank{snap?.optString("mnv").orEmpty()};if(mnv.isBlank())continue
                val emp=MasterDataCache.employee(this,mnv)?:snap?:JSONObject();if(!site1291(emp.optString("site")))continue
                val shift=e.optString("shift").ifBlank{p.optString("shift")}.ifBlank{after?.optString("shift").orEmpty()};val work=e.optString("work_choice").ifBlank{p.optString("work_choice")}.ifBlank{after?.optString("work_choice").orEmpty()}
                val key=e.optString("entity_id").ifBlank{e.optString("session_id")}.ifBlank{e.optString("event_id")}.ifBlank{"$mnv|$shift|$i"};out[key]=Entry(mnv,shift,work,emp)
            }
            return out.values.toList()
        }
        fun makeGrid(rows:List<Entry>,kind:String):JSONObject{
            val columns=rows.map{supplierCode(it.emp.optString("supplier"))}.distinct().sorted();val rowOrder=if(kind=="position")listOf("Trưởng nhóm","Chuyên viên","Tổ trưởng","Điều phối khu pack","Điều phối khu chờ xuất","Kéo hàng","5S","Picker","Packer","Phúc Long","Khác") else listOf("Nhân sự mới","Nhân sự cũ")
            val values=LinkedHashMap<String,MutableMap<String,Int>>();rowOrder.forEach{values[it]=LinkedHashMap()};rows.forEach{r->val label=if(kind=="position")reportPosition(r.emp,r.work) else tenureLabel(r.emp);val key=if(values.containsKey(label))label else if(kind=="position")"Khác" else label;val sup=supplierCode(r.emp.optString("supplier"));values.getOrPut(key){LinkedHashMap()}[sup]=(values[key]?.get(sup)?:0)+1}
            val outRows=JSONArray();rowOrder.forEach{label->val counts=JSONObject();var total=0;columns.forEach{c->val n=values[label]?.get(c)?:0;counts.put(c,n);total+=n};if(total>0||kind!="position")outRows.put(JSONObject().put(if(kind=="position")"position" else "label",label).put("counts",counts).put("total",total))};val totals=JSONObject();var grand=0;columns.forEach{c->val n=rowOrder.sumOf{values[it]?.get(c)?:0};totals.put(c,n);grand+=n};return JSONObject().put("columns",JSONArray(columns)).put("rows",outRows).put("totals",totals).put("total",grand)
        }
        fun render(){
            box.removeAllViews();val all=entriesForToday();val selected=all.filter{when(period.selectedItemPosition){0->shiftBucket(it.shift) in setOf("CA1","HC");1->shiftBucket(it.shift)=="CA2";else->true}}
            box.addView(info("Site 1291 • Tính theo ngày vào ca ${java.time.LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh")).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))} • Vào ca hoặc vào–ra đều được tính."));box.addView(gap(5));box.addView(reportGrid("",makeGrid(selected,"position"),"Vị trí","position"));box.addView(gap(4));box.addView(reportGrid("",makeGrid(selected,"tenure"),"Thâm niên","label"));if(all.isEmpty())box.addView(info("Chưa có snapshot ngày hôm nay trên PDA. Hệ thống đang yêu cầu đồng bộ lại; dữ liệu không được tự suy diễn thành 0."))
        }
        period.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){render()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};foregroundSync.requestSync();render();attach(root,body)
    }
'''
s=s[:start]+replacement.rstrip()+s[end:]
OPS.write_text(s,encoding='utf-8')
ops=OPS.read_text(encoding='utf-8')
for x in [MARK,'ATTENDANCE_ENTER','site1291','Tính theo ngày vào ca','Vào ca hoặc vào–ra đều được tính']:
    if x not in ops: raise SystemExit('S34C contract missing '+x)
print('Applied S34C: Site 1291 manpower/tenure report from canonical entry-day snapshot')
