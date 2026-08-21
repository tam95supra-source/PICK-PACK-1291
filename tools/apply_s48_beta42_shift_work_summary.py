#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S48_BETA42_SHIFT_WORK_SUMMARY'

def replace_private_fun(src:str, signature:str, replacement:str)->str:
    start=src.find('    private fun '+signature)
    if start<0: raise SystemExit('S48 function anchor missing: '+signature)
    end=src.find('\n    private fun ',start+20)
    if end<0: raise SystemExit('S48 next function anchor missing: '+signature)
    return src[:start]+replacement.rstrip()+'\n'+src[end:]

s=OPS.read_text(encoding='utf-8')
if MARK in s:
    print('S48 already applied')
    raise SystemExit(0)

anchor='    private fun renderActive(body: LinearLayout, ctx: JSONObject) {'
if anchor not in s: raise SystemExit('S48 active anchor missing')
helpers=r'''    // S48_BETA42_SHIFT_WORK_SUMMARY: local-first shift timeline + explicit PDA identity.
    private fun sessionWorkDetail(payload:JSONObject):String{
        val parts=mutableListOf<String>()
        val work=payload.optString("work_choice").trim().uppercase()
        when(work){
            "PICK"->{parts.add("PICK");payload.optString("pda_serial").trim().takeIf{it.isNotBlank()}?.let{parts.add("Seri PDA $it")};payload.optString("user_pick").trim().takeIf{it.isNotBlank()}?.let{parts.add("User Pick $it")}}
            "PACK"->{parts.add("PACK");payload.optString("pack_table").trim().takeIf{it.isNotBlank()}?.let{parts.add("Bàn $it")};payload.optString("user_pack").trim().takeIf{it.isNotBlank()}?.let{parts.add("User Pack $it")}}
            "KHÔNG","KHONG"->parts.add("Không gán Pick/Pack")
        }
        payload.optString("labor_type").trim().takeIf{it.isNotBlank()}?.let{parts.add("Công nhật: $it")}
        payload.optString("time_marker").trim().takeIf{it.isNotBlank()}?.let{parts.add("Mốc $it")}
        return parts.joinToString(" • ")
    }

    private fun sessionTimelineItems(mnv:String):MutableList<JSONObject>{
        val merged=LinkedHashMap<String,JSONObject>()
        val date=operationalStore.businessDate()
        val allowed=setOf("ATTENDANCE_ENTER","ENTER","RESOURCE_CHANGE","RESOURCE","LABOR_START","LABOR_FINISH","ATTENDANCE_EXIT","EXIT")
        val day=operationalStore.loadDay(date)
        val events=day?.optJSONArray("events")?:JSONArray()
        for(i in 0 until events.length()){
            val e=events.optJSONObject(i)?:continue
            if(e.optString("mnv").trim()!=mnv)continue
            val type=e.optString("event_type").uppercase();if(type !in allowed)continue
            val copy=JSONObject(e.toString()).put("timeline_source","CANONICAL")
            val id=copy.optString("event_id").ifBlank{"canonical:$date:$i:${copy.optString("at_iso").ifBlank{copy.optString("at")}}"}
            merged[id]=copy
        }
        for(local in operationalStore.localHistoryAll()){
            val id=local.optString("event_id").trim();if(id.isBlank())continue
            val body=local.optJSONObject("body")?:JSONObject();val payload=body.optJSONObject("payload")?:body
            if(payload.optString("mnv").trim()!=mnv)continue
            val action=body.optString("action").trim();val type=when(action){"enter"->"ATTENDANCE_ENTER";"resource_change"->"RESOURCE_CHANGE";"labor_start"->"LABOR_START";"labor_finish"->"LABOR_FINISH";"exit"->"ATTENDANCE_EXIT";else->""};if(type.isBlank())continue
            val existing=merged[id]
            if(existing!=null){existing.put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at",0L));continue}
            val label=when(type){"ATTENDANCE_ENTER"->"Vào ca";"RESOURCE_CHANGE"->"Cập nhật công việc";"LABOR_START"->"Bắt đầu công nhật";"LABOR_FINISH"->"Hoàn thành công nhật";"ATTENDANCE_EXIT"->"Ra ca";else->action}
            merged[id]=JSONObject().put("event_id",id).put("event_type",type).put("label",label).put("mnv",mnv).put("actor","Thiết bị này").put("detail",sessionWorkDetail(payload)).put("timeline_source","LOCAL_PDA").put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at",0L))
        }
        val out=merged.values.toMutableList()
        fun atMillis(e:JSONObject):Long{val q=e.optLong("local_queued_at",0L);if(q>0L)return q;return runCatching{Instant.parse(e.optString("at_iso").ifBlank{e.optString("at")}).toEpochMilli()}.getOrDefault(0L)}
        out.sortBy{atMillis(it)}
        return out
    }

    private fun sessionEventTitle(typeRaw:String,label:String):String=when(typeRaw.uppercase()){
        "ATTENDANCE_ENTER","ENTER"->"VÀO CA"
        "RESOURCE_CHANGE","RESOURCE"->"CẬP NHẬT CÔNG VIỆC"
        "LABOR_START"->"BẮT ĐẦU CÔNG NHẬT"
        "LABOR_FINISH"->"HOÀN THÀNH CÔNG NHẬT"
        "ATTENDANCE_EXIT","EXIT"->"RA CA"
        else->label.ifBlank{"THAO TÁC"}.uppercase()
    }

    private fun sessionEventTime(e:JSONObject):String{
        val local=e.optLong("local_queued_at",0L)
        if(local>0L)return Instant.ofEpochMilli(local).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).format(DateTimeFormatter.ofPattern("HH:mm:ss"))
        return formatIso(e.optString("at_iso").ifBlank{e.optString("at")})
    }

    private fun addPdaIdentity(body:LinearLayout,ses:JSONObject){
        fun clean(v:String)=v.trim().takeUnless{it.equals("null",true)||it=="—"}?:""
        val serial=clean(ses.optString("pda_serial"));val pdaStatus=clean(ses.optString("pda_enter_status"))
        body.addView(section("PDA TRONG PHIÊN"))
        if(serial.isBlank()){body.addView(info("Phiên vào ca này không sử dụng PDA."));return}
        val card=column(surface).apply{
            setPadding(dp(14),dp(12),dp(14),dp(12));background=outlineBg(surface,16);elevation=dp(2).toFloat()
            addView(txt("SERI PDA",9.5f,muted,true));addView(txt(serial,15f,navy,true));addView(gap(8));addView(txt("TÌNH TRẠNG LÚC NHẬN",9.5f,muted,true));addView(txt(pdaStatus.ifBlank{"Chưa có dữ liệu tình trạng"},12f,if(pdaStatus.isBlank())orange else teal,true))
        }
        body.addView(card,matchWrap())
    }

    private fun addSessionTimeline(body:LinearLayout,mnv:String){
        body.addView(section("DIỄN BIẾN CÔNG VIỆC TRONG CA"))
        body.addView(info("Mỗi lần đổi vị trí / Pick / Pack được giữ thành một mốc riêng. Mốc mới không ghi đè lịch sử cũ."));body.addView(gap(7))
        val items=sessionTimelineItems(mnv)
        if(items.isEmpty()){body.addView(info("Chưa có mốc công việc trong bộ nhớ PDA. Hệ thống sẽ bổ sung khi snapshot đồng bộ về."));return}
        for(e in items){
            val title=sessionEventTitle(e.optString("event_type"),e.optString("label"));val detail=e.optString("detail").trim();val actor=e.optString("actor").ifBlank{"Hệ thống"};val localStatus=e.optString("local_status")
            val card=column(surface).apply{
                setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(surface,14)
                val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL;addView(txt(title,10.7f,navy,true),LinearLayout.LayoutParams(0,-2,1f));addView(txt(sessionEventTime(e),9.4f,muted,true))};addView(top,matchWrap())
                if(detail.isNotBlank()){addView(gap(4));addView(txt(detail,10f,ink,false))}
                addView(gap(4));val statusText=when(localStatus){"LOCAL_PENDING","PENDING","OFFLINE_PROVISIONAL"->" • Chờ đồng bộ";"RETRY"->" • Chờ gửi lại";"REVIEW_REQUIRED","CONFLICT"->" • Cần kiểm tra";"REJECTED"->" • Bị từ chối";else->""};addView(txt("Người thực hiện: $actor$statusText",9.2f,muted,false))
            }
            body.addView(card,matchWrap());body.addView(gap(6))
        }
    }

'''
s=s.replace(anchor,helpers+anchor,1)

active=r'''    private fun renderActive(body: LinearLayout, ctx: JSONObject) {
        val ses=ctx.optJSONObject("session")?:JSONObject();val mnv=ses.optString("mnv")
        fun clean(v:String)=v.trim().takeUnless{it.equals("null",true)||it=="—"}?:""
        val pda=clean(ses.optString("pda_serial"));val initialStatus=clean(ses.optString("pda_enter_status"));val resourceNote=ses.optString("resource_note")
        val enteredWithPda=pda.isNotBlank()&&initialStatus.isNotBlank()
        body.addView(status("ĐANG TRONG PHIÊN",green,Color.rgb(235,248,239)));body.addView(gap(8))
        body.addView(section("THỜI GIAN & CÔNG VIỆC HIỆN TẠI"));body.addView(details(listOf(
            "Ca" to ses.optString("shift"),"Vào lúc" to formatIso(ses.optString("enter_at")),"Ra lúc" to "Chưa ra ca",
            "Vị trí hiện tại" to workText(ses.optString("work_choice")),"User Pick hiện tại" to dash(ses.optString("user_pick")),"Bàn Pack hiện tại" to dash(ses.optString("pack_table")),"User Pack hiện tại" to dash(ses.optString("user_pack")),"Ghi chú tài nguyên" to dash(resourceNote)
        )));body.addView(gap(9));addPdaIdentity(body,ses);body.addView(gap(9));addSessionTimeline(body,mnv);body.addView(gap(10))
        body.addView(primary("THÊM / SỬA CÔNG VIỆC TRONG CA",orange){initialMnv=mnv;resourceHome()},matchWrap());body.addView(gap(5));body.addView(txt("Lưu thay đổi sẽ tạo một mốc công việc mới và cập nhật trạng thái hiện tại; các mốc trước vẫn được giữ để đối chiếu.",9.6f,muted,false));body.addView(gap(10))
        val exit=primary("RA CA",red){}
        fun callExit(statusNow:String){
            val actionGeneration=employeeLookupGeneration
            exit.isEnabled=false;exit.text="ĐANG RA CA..."
            val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv)
            if(statusNow.isNotBlank())payload.put("pda_exit_status",statusNow)
            api.call("exit",payload){r->runOnUiThread{exit.isEnabled=true;exit.text="RA CA";if(!r.ok)showError(r.error?:"RA CA thất bại")else{TopNotice.show(this,"Đã ghi nhận ra ca.",TopNotice.Kind.SUCCESS);scheduleAttendanceAutoReset(mnv,actionGeneration)}}}
        }
        exit.setOnClickListener{
            if(!enteredWithPda){AlertDialog.Builder(this).setTitle("Xác nhận RA CA").setMessage("Phiên vào ca này không có PDA cần đối chiếu tình trạng. Xác nhận kết thúc phiên hôm nay?").setNegativeButton("Hủy",null).setPositiveButton("RA CA"){_,_->callExit("")}.show();return@setOnClickListener}
            val statuses=mutableListOf<String>();val arr=ctx.optJSONObject("options")?.optJSONArray("pda_statuses")?:MasterDataCache.resourceOptions(this).optJSONArray("pda_statuses")?:JSONArray();for(i in 0 until arr.length()){val v=clean(arr.optString(i));if(v.isNotBlank()&&!statuses.contains(v))statuses.add(v)};if(!statuses.contains(initialStatus))statuses.add(0,initialStatus)
            val sp=spinner(statuses.toTypedArray());val wrap=column(surface).apply{setPadding(dp(16),dp(6),dp(16),dp(4));addView(txt("Seri PDA: $pda",12f,navy,true));addView(gap(5));addView(txt("Tình trạng lúc nhận: $initialStatus",10.5f,muted,true));addView(gap(9));addView(labelled("Tình trạng PDA hiện tại",sp))}
            AlertDialog.Builder(this).setTitle("Xác nhận PDA khi RA CA").setView(wrap).setNegativeButton("Hủy",null).setPositiveButton("KIỂM TRA & RA CA"){_,_->val now=sp.selectedItem?.toString().orEmpty();if(now!=initialStatus)showError("PDA_STATUS_MISMATCH_NOTIFY_SPECIALIST")else callExit(now)}.show()
        }
        body.addView(exit,matchWrap())
    }'''
s=replace_private_fun(s,'renderActive(body: LinearLayout, ctx: JSONObject) {',active)

ended=r'''    private fun renderEnded(body: LinearLayout, ctx: JSONObject) {
        val ses=ctx.optJSONObject("session")?:JSONObject();val mnv=ses.optString("mnv")
        body.addView(status("ĐÃ RA CA",teal,Color.rgb(232,248,245)));body.addView(gap(8));body.addView(section("PHIÊN HÔM NAY"));body.addView(details(listOf(
            "Ca" to ses.optString("shift"),"Vào lúc" to formatIso(ses.optString("enter_at")),"Ra lúc" to formatIso(ses.optString("exit_at")),"Công việc cuối" to workText(ses.optString("work_choice")),"User Pick cuối" to dash(ses.optString("user_pick")),"Bàn Pack cuối" to dash(ses.optString("pack_table")),"User Pack cuối" to dash(ses.optString("user_pack"))
        )));body.addView(gap(9));addPdaIdentity(body,ses);body.addView(gap(9));addSessionTimeline(body,mnv)
    }'''
s=replace_private_fun(s,'renderEnded(body: LinearLayout, ctx: JSONObject) {',ended)

P=OPS
P.write_text(s,encoding='utf-8')
o=P.read_text(encoding='utf-8')
checks=[
    (MARK in o,'marker'),
    ('DIỄN BIẾN CÔNG VIỆC TRONG CA' in o,'shift timeline section'),
    ('THÊM / SỬA CÔNG VIỆC TRONG CA' in o,'edit/add work action'),
    ('SERI PDA' in o and 'TÌNH TRẠNG LÚC NHẬN' in o,'explicit PDA identity'),
    ('localHistoryAll()' in o and 'loadDay(date)' in o,'canonical + local history merge'),
    ('Mỗi lần đổi vị trí / Pick / Pack' in o,'audit-preserving explanation'),
    ('enteredWithPda=pda.isNotBlank()&&initialStatus.isNotBlank()' in o,'PDA exit criterion preserved'),
]
for ok,label in checks:
    if not ok: raise SystemExit('S48 contract missing: '+label)
print('Applied S48: clear PDA identity + multi-work shift timeline + scan edit/add action')
