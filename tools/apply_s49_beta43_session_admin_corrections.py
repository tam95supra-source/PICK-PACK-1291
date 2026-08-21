#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
API=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt'
MARK='S49_BETA43_SESSION_ADMIN_CORRECTIONS'

def replace_private_fun(src:str, signature:str, replacement:str)->str:
    start=src.find('    private fun '+signature)
    if start<0: raise SystemExit('S49 function anchor missing: '+signature)
    end=src.find('\n    private fun ',start+20)
    if end<0: raise SystemExit('S49 next function anchor missing: '+signature)
    return src[:start]+replacement.rstrip()+'\n'+src[end:]

s=OPS.read_text(encoding='utf-8')
if MARK in s:
    print('S49 already applied')
    raise SystemExit(0)

# Employee context must include active labor so the exit screen can explain/block pending labor before calling Service.
old='.put("include_options",true).put("include_labor",false)'
if old not in s: raise SystemExit('S49 employee context labor anchor missing')
s=s.replace(old,'.put("include_options",true).put("include_labor",true)',1)

# Replace S48 timeline parser with one that understands raw Service events, corrections and delete-exit audit events.
timeline=r'''    private fun sessionTimelineItems(mnv:String):MutableList<JSONObject>{
        val merged=LinkedHashMap<String,JSONObject>();val date=operationalStore.businessDate()
        val allowed=setOf("ATTENDANCE_ENTER","ENTER","RESOURCE_CHANGE","RESOURCE","LABOR_START","LABOR_FINISH","ATTENDANCE_EXIT","EXIT","ATTENDANCE_TIME_CORRECTED","ATTENDANCE_EXIT_DELETED")
        fun payload(e:JSONObject):JSONObject{val raw=e.optString("payload_json");if(raw.isNotBlank())return runCatching{JSONObject(raw)}.getOrDefault(JSONObject());return e.optJSONObject("payload")?:JSONObject()}
        fun detail(type:String,e:JSONObject,p:JSONObject):String{
            if(type=="ATTENDANCE_TIME_CORRECTED"){val field=if(p.optString("field")=="enter_at")"Giờ vào" else "Giờ ra";return "$field: ${formatIso(p.optString("before_value"))} → ${formatIso(p.optString("after_value"))} • Lý do: ${p.optString("reason").ifBlank{"—"}}"}
            if(type=="ATTENDANCE_EXIT_DELETED")return "Xóa mốc ra ca ${formatIso(p.optString("before_exit_at"))} • Lý do: ${p.optString("reason").ifBlank{"—"}}"
            if(type=="RESOURCE_CHANGE"){val after=p.optJSONObject("after");if(after!=null)return sessionWorkDetail(after)}
            return e.optString("detail").ifBlank{sessionWorkDetail(p)}
        }
        val day=operationalStore.loadDay(date);val events=day?.optJSONArray("events")?:JSONArray()
        for(i in 0 until events.length()){
            val e=events.optJSONObject(i)?:continue;val p=payload(e);val who=e.optString("mnv").ifBlank{p.optString("mnv")}.trim();if(who!=mnv)continue
            val type=e.optString("event_type").uppercase();if(type !in allowed)continue
            val copy=JSONObject(e.toString()).put("timeline_source","CANONICAL").put("mnv",mnv).put("detail",detail(type,e,p)).put("actor",e.optString("actor").ifBlank{e.optString("actor_id")})
            if(copy.optString("at_iso").isBlank())copy.put("at_iso",e.optString("committed_at").ifBlank{e.optString("occurred_at")})
            val id=copy.optString("event_id").ifBlank{"canonical:$date:$i:${copy.optString("at_iso")}"};merged[id]=copy
        }
        for(local in operationalStore.localHistoryAll()){
            val id=local.optString("event_id").trim();if(id.isBlank())continue;val body=local.optJSONObject("body")?:JSONObject();val p=body.optJSONObject("payload")?:body;if(p.optString("mnv").trim()!=mnv)continue
            val action=body.optString("action").trim();val type=when(action){"enter"->"ATTENDANCE_ENTER";"resource_change"->"RESOURCE_CHANGE";"labor_start"->"LABOR_START";"labor_finish"->"LABOR_FINISH";"exit"->"ATTENDANCE_EXIT";else->""};if(type.isBlank())continue
            val existing=merged[id];if(existing!=null){existing.put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at",0L));continue}
            val label=when(type){"ATTENDANCE_ENTER"->"Vào ca";"RESOURCE_CHANGE"->"Cập nhật công việc";"LABOR_START"->"Bắt đầu công nhật";"LABOR_FINISH"->"Hoàn thành công nhật";"ATTENDANCE_EXIT"->"Ra ca";else->action}
            merged[id]=JSONObject().put("event_id",id).put("event_type",type).put("label",label).put("mnv",mnv).put("actor","Thiết bị này").put("detail",sessionWorkDetail(p)).put("timeline_source","LOCAL_PDA").put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at",0L))
        }
        val out=merged.values.toMutableList();fun atMillis(e:JSONObject):Long{val q=e.optLong("local_queued_at",0L);if(q>0L)return q;return runCatching{Instant.parse(e.optString("at_iso").ifBlank{e.optString("at")}).toEpochMilli()}.getOrDefault(0L)};out.sortBy{atMillis(it)};return out
    }'''
s=replace_private_fun(s,'sessionTimelineItems(mnv:String):MutableList<JSONObject>{',timeline)

title=r'''    private fun sessionEventTitle(typeRaw:String,label:String):String=when(typeRaw.uppercase()){
        "ATTENDANCE_ENTER","ENTER"->"VÀO CA";"RESOURCE_CHANGE","RESOURCE"->"CẬP NHẬT CÔNG VIỆC";"LABOR_START"->"BẮT ĐẦU CÔNG NHẬT";"LABOR_FINISH"->"HOÀN THÀNH CÔNG NHẬT";"ATTENDANCE_EXIT","EXIT"->"RA CA";"ATTENDANCE_TIME_CORRECTED"->"SỬA THỜI GIAN VÀO / RA";"ATTENDANCE_EXIT_DELETED"->"XÓA GHI NHẬN RA CA";else->label.ifBlank{"THAO TÁC"}.uppercase()
    }'''
s=replace_private_fun(s,'sessionEventTitle(typeRaw:String,label:String):String=',title)

pda=r'''    private fun addPdaIdentity(body:LinearLayout,ses:JSONObject){
        fun clean(v:String)=v.trim().takeUnless{it.equals("null",true)||it=="—"}?:"";val serial=clean(ses.optString("pda_serial"));val pdaStatus=clean(ses.optString("pda_enter_status"));body.addView(section("PDA ĐANG GIỮ TRONG PHIÊN"))
        if(serial.isBlank()){body.addView(info("Hiện tại phiên không giữ PDA; khi ra ca sẽ không yêu cầu đối chiếu tình trạng PDA."));return}
        body.addView(column(surface).apply{setPadding(dp(14),dp(12),dp(14),dp(12));background=outlineBg(surface,16);elevation=dp(2).toFloat();addView(txt("SERI PDA",9.5f,muted,true));addView(txt(serial,15f,navy,true));addView(gap(8));addView(txt("TÌNH TRẠNG KHI NHẬN PDA HIỆN TẠI",9.5f,muted,true));addView(txt(pdaStatus.ifBlank{"Chưa có dữ liệu tình trạng"},12f,if(pdaStatus.isBlank())orange else teal,true))},matchWrap())
    }'''
s=replace_private_fun(s,'addPdaIdentity(body:LinearLayout,ses:JSONObject){',pda)

# Insert new session editor/admin helpers before renderActive.
anchor='    private fun renderActive(body: LinearLayout, ctx: JSONObject) {'
if anchor not in s: raise SystemExit('S49 active helper insertion anchor missing')
helpers=r'''    // S49_BETA43_SESSION_ADMIN_CORRECTIONS
    private fun pickSummary(s:JSONObject):String{val x=mutableListOf<String>();s.optString("pda_serial").trim().takeIf{it.isNotBlank()}?.let{x.add("PDA $it")};s.optString("user_pick").trim().takeIf{it.isNotBlank()}?.let{x.add("User $it")};return if(x.isEmpty())"Không" else x.joinToString(" • ")}
    private fun packSummary(s:JSONObject):String{val x=mutableListOf<String>();s.optString("pack_table").trim().takeIf{it.isNotBlank()}?.let{x.add("Bàn $it")};s.optString("user_pack").trim().takeIf{it.isNotBlank()}?.let{x.add("User $it")};return if(x.isEmpty())"Không" else x.joinToString(" • ")}
    private fun returnedSessionContext(ctx:JSONObject,r:BetaApiClient.Result):JSONObject?{val ss=r.json?.optJSONObject("session")?:return null;return JSONObject(ctx.toString()).put("session",ss).put("state",ss.optString("state"))}

    private fun sessionWorkEditor(ctx:JSONObject){
        val ses=ctx.optJSONObject("session")?:return;val mnv=ses.optString("mnv");if(ses.optString("state")!="ACTIVE"){showError("Phiên đã ra ca. ADMIN/SUPERADMIN hãy hủy ghi nhận ra ca trước khi sửa công việc.");return}
        val options=PdaLocalProjection.resourceOptions(this,mnv);val pdas=options.optJSONArray("pdas")?:JSONArray();val picks=options.optJSONArray("user_picks")?:JSONArray();val pickReissue=options.optJSONArray("user_picks_reissue")?:JSONArray();val packs=options.optJSONArray("pack_tables")?:JSONArray();val packReissue=options.optJSONArray("pack_tables_reissue")?:JSONArray()
        val dialogBody=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))};dialogBody.addView(info("PICK và PACK là hai phần độc lập. Có thể giữ đồng thời cả hai; lưu mới chỉ cập nhật trạng thái hiện tại, lịch sử các lần trước vẫn giữ nguyên."));dialogBody.addView(gap(8))
        val pickOn=CheckBox(this).apply{text="Có công việc PICK";isChecked=ses.optString("pda_serial").isNotBlank()||ses.optString("user_pick").isNotBlank()||ses.optString("work_choice")=="PICK";setTextColor(ink)}
        val packOn=CheckBox(this).apply{text="Có công việc PACK";isChecked=ses.optString("pack_table").isNotBlank()||ses.optString("user_pack").isNotBlank()||ses.optString("work_choice")=="PACK";setTextColor(ink)}
        dialogBody.addView(pickOn,matchWrap());dialogBody.addView(packOn,matchWrap());dialogBody.addView(gap(7));val host=column(surface);dialogBody.addView(host,matchWrap())
        var pdaField:AutoCompleteTextView?=null;var selectedPda:JSONObject?=null;var pickSpinner:Spinner?=null;var pickValues=mutableListOf<String>();var packSpinner:Spinner?=null;var packRows=mutableListOf<JSONObject>()
        fun rebuild(){
            host.removeAllViews();pdaField=null;selectedPda=null;pickSpinner=null;pickValues.clear();packSpinner=null;packRows.clear()
            if(pickOn.isChecked){host.addView(section("PICK"));val pdaInfo=txt("Không giữ PDA.",10f,muted,false);pdaField=pdaInput(pdas,ses.optString("pda_serial")){p->selectedPda=p;pdaInfo.text=if(p==null)"Không giữ PDA." else "Seri PDA: ${p.optString("serial")}\nTình trạng khi nhận: ${p.optString("status").ifBlank{"—"}}"};host.addView(labelled("PDA (có thể đổi / trả)",pdaField!!));host.addView(gap(4));host.addView(pdaInfo,matchWrap());host.addView(gap(5));host.addView(smallButton("TRẢ PDA",orange).apply{setOnClickListener{selectedPda=null;pdaField?.setText("",false);pdaInfo.text="Đã chọn trả PDA khi lưu."}},matchWrap());host.addView(gap(7));val labels=mutableListOf("Không dùng User Pick");pickValues.add("");fun addPick(v:String,label:String=v){if(v.isBlank()||pickValues.contains(v))return;pickValues.add(v);labels.add(label)};for(i in 0 until picks.length())addPick(picks.optString(i));for(i in 0 until pickReissue.length()){val o=pickReissue.optJSONObject(i)?:continue;addPick(o.optString("id"),"⚠ ${o.optString("id")} • ĐÃ DÙNG TRƯỚC ĐÓ")};addPick(ses.optString("user_pick"));pickSpinner=spinner(labels.toTypedArray());val cur=pickValues.indexOf(ses.optString("user_pick"));if(cur>=0)pickSpinner!!.setSelection(cur);host.addView(labelled("User Pick",pickSpinner!!));host.addView(gap(9))}
            if(packOn.isChecked){host.addView(section("PACK"));fun addPack(a:JSONArray){for(i in 0 until a.length()){val o=a.optJSONObject(i)?:continue;if(o.optString("shift")!=ses.optString("shift"))continue;val t=o.optString("table"),u=o.optString("user_pack");if(t.isBlank()||u.isBlank()||packRows.any{it.optString("table")==t&&it.optString("user_pack")==u})continue;packRows.add(JSONObject(o.toString()))}};addPack(packs);addPack(packReissue);if(ses.optString("pack_table").isNotBlank()&&ses.optString("user_pack").isNotBlank()&&!packRows.any{it.optString("table")==ses.optString("pack_table")&&it.optString("user_pack")==ses.optString("user_pack")})packRows.add(JSONObject().put("table",ses.optString("pack_table")).put("user_pack",ses.optString("user_pack")).put("shift",ses.optString("shift")));val labels=if(packRows.isEmpty())arrayOf("Không có cặp Bàn Pack / User Pack khả dụng") else packRows.map{"${it.optString("table")} • ${it.optString("user_pack")}"}.toTypedArray();packSpinner=spinner(labels);val cur=packRows.indexOfFirst{it.optString("table")==ses.optString("pack_table")&&it.optString("user_pack")==ses.optString("user_pack")};if(cur>=0)packSpinner!!.setSelection(cur);host.addView(labelled("Bàn Pack + User Pack",packSpinner!!));host.addView(gap(7))}
            if(!pickOn.isChecked&&!packOn.isChecked)host.addView(info("Không gán công việc PICK/PACK. Lưu để trả toàn bộ tài nguyên đang giữ."))
        }
        pickOn.setOnCheckedChangeListener{_,_->rebuild()};packOn.setOnCheckedChangeListener{_,_->rebuild()};rebuild()
        AlertDialog.Builder(this).setTitle("Thêm / sửa công việc trong ca").setView(ScrollView(this).apply{addView(dialogBody)}).setNegativeButton("Hủy",null).setPositiveButton("LƯU"){_,_->
            val p=JSONObject().put("session_id",ses.optString("session_id")).put("idempotency_key",UUID.randomUUID().toString())
            val pick=if(pickOn.isChecked)pickValues.getOrNull(pickSpinner?.selectedItemPosition?:0).orEmpty() else "";val pda=if(pickOn.isChecked)selectedPda?.optString("serial").orEmpty() else "";p.put("pda_serial",pda).put("user_pick",pick)
            if(packOn.isChecked){val row=packRows.getOrNull(packSpinner?.selectedItemPosition?:-1);if(row==null){showError("Chọn Bàn Pack + User Pack hợp lệ.");return@setPositiveButton};p.put("pack_table",row.optString("table")).put("user_pack",row.optString("user_pack"))}else p.put("pack_table","").put("user_pack","")
            val current=ses.optString("work_choice");val primary=when{pickOn.isChecked&&packOn.isChecked&&current in setOf("PICK","PACK")->current;pickOn.isChecked->"PICK";packOn.isChecked->"PACK";else->"KHONG"};p.put("work_choice",primary).put("resource_note",when{pickOn.isChecked&&packOn.isChecked->"PICK + PACK";pickOn.isChecked->"PICK";packOn.isChecked->"PACK";else->"Đã trả tài nguyên"})
            api.call("session_work_update",p){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không cập nhật được công việc");return@runOnUiThread};TopNotice.show(this,"Đã cập nhật công việc trong ca.",TopNotice.Kind.SUCCESS);foregroundSync.requestSync();val next=returnedSessionContext(ctx,r);if(next!=null)renderEmployee(next,PdaLocalProjection.resourceOptions(this,mnv))else loadEmployee(mnv)}}
        }.show()
    }

    private fun editableTime(iso:String):String=runCatching{Instant.parse(iso).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss"))}.getOrDefault(iso)
    private fun parseEditableTime(v:String):String?=runCatching{java.time.LocalDateTime.parse(v.trim(),DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss")).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).toInstant().toString()}.getOrNull()
    private fun editAttendanceTime(ctx:JSONObject,field:String){
        if(!isAdmin())return;val ses=ctx.optJSONObject("session")?:return;val old=ses.optString(field);if(old.isBlank()){showError("Chưa có mốc thời gian để sửa.");return};val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))};val time=input("dd/MM/yyyy HH:mm:ss",false).apply{setText(editableTime(old))};val reason=input("Lý do điều chỉnh",false).apply{setText("Điều chỉnh theo xác nhận thực tế")};box.addView(info("Giờ ghi nhận ban đầu vẫn được giữ trong lịch sử audit. Sheet RA/VÀO chỉ hiển thị giờ sửa sau cùng."));box.addView(gap(7));box.addView(labelled(if(field=="enter_at")"Giờ vào ca mới" else "Giờ ra ca mới",time));box.addView(gap(7));box.addView(labelled("Lý do",reason));AlertDialog.Builder(this).setTitle(if(field=="enter_at")"Sửa giờ vào ca" else "Sửa giờ ra ca").setView(box).setNegativeButton("Hủy",null).setPositiveButton("LƯU"){_,_->val parsed=parseEditableTime(time.text.toString());if(parsed==null){showError("Thời gian phải đúng định dạng dd/MM/yyyy HH:mm:ss.");return@setPositiveButton};if(reason.text.toString().trim().length<3){showError("Nhập lý do điều chỉnh.");return@setPositiveButton};api.call("attendance_time_correct",JSONObject().put("session_id",ses.optString("session_id")).put("field",field).put("corrected_at",parsed).put("reason",reason.text.toString().trim()).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không sửa được thời gian");return@runOnUiThread};TopNotice.show(this,"Đã sửa thời gian và lưu audit.",TopNotice.Kind.SUCCESS);foregroundSync.requestSync();val next=returnedSessionContext(ctx,r);if(next!=null)renderEmployee(next,PdaLocalProjection.resourceOptions(this,ses.optString("mnv")))else loadEmployee(ses.optString("mnv"))}}}.show()
    }

    private fun deleteExitRecord(ctx:JSONObject){
        if(!isAdmin())return;val ses=ctx.optJSONObject("session")?:return;val mnv=ses.optString("mnv");val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))};val reason=input("Lý do xóa ghi nhận ra ca",false).apply{setText("Bắn nhầm ra ca")};box.addView(info("Mốc EXIT sẽ bị xóa hẳn khỏi sheet RA/VÀO và phiên được mở lại. Sự kiện xóa vẫn tồn tại trong Lịch sử và Diễn biến trong ca."));box.addView(gap(7));box.addView(reason,matchWrap());AlertDialog.Builder(this).setTitle("Hủy ghi nhận RA CA?").setView(box).setNegativeButton("Không",null).setPositiveButton("XÓA RA CA"){_,_->if(reason.text.toString().trim().length<3){showError("Nhập lý do xóa.");return@setPositiveButton};api.call("attendance_exit_delete",JSONObject().put("session_id",ses.optString("session_id")).put("reason",reason.text.toString().trim()).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không xóa được mốc ra ca");return@runOnUiThread};val conflicts=r.json?.optJSONArray("resource_reacquire_conflicts")?:JSONArray();TopNotice.show(this,if(conflicts.length()>0)"Đã mở lại phiên; một số tài nguyên đã được người khác nhận nên không tự cấp lại." else "Đã xóa mốc ra ca và mở lại phiên.",if(conflicts.length()>0)TopNotice.Kind.WARNING else TopNotice.Kind.SUCCESS);foregroundSync.requestSync();loadEmployee(mnv)}}}.show()
    }

'''
s=s.replace(anchor,helpers+anchor,1)

active=r'''    private fun renderActive(body: LinearLayout, ctx: JSONObject) {
        val ses=ctx.optJSONObject("session")?:JSONObject();val mnv=ses.optString("mnv");fun clean(v:String)=v.trim().takeUnless{it.equals("null",true)||it=="—"}?:"";val pda=clean(ses.optString("pda_serial"));val expectedStatus=clean(ses.optString("pda_enter_status"));val activeLabor=ctx.optJSONObject("active_labor")
        body.addView(status("ĐANG TRONG PHIÊN",green,Color.rgb(235,248,239)));body.addView(gap(8));body.addView(section("THỜI GIAN & CÔNG VIỆC HIỆN TẠI"));body.addView(details(listOf("Ca" to ses.optString("shift"),"Vào lúc" to formatIso(ses.optString("enter_at")),"Ra lúc" to "Chưa ra ca","Công việc PICK" to pickSummary(ses),"Công việc PACK" to packSummary(ses),"Ghi chú" to dash(ses.optString("resource_note")))));body.addView(gap(9));addPdaIdentity(body,ses);body.addView(gap(8))
        if(activeLabor!=null){body.addView(status("CÒN CÔNG NHẬT ĐANG LÀM",orange,Color.rgb(255,247,230)));body.addView(gap(4));body.addView(info("${activeLabor.optString("labor_type")} • bắt đầu ${formatIso(activeLabor.optString("start_at"))}. Phải hoàn thành công nhật trước khi ra ca."));body.addView(gap(8))}
        addSessionTimeline(body,mnv);body.addView(gap(9));body.addView(primary("THÊM / SỬA CÔNG VIỆC TRONG CA",orange){sessionWorkEditor(ctx)},matchWrap());body.addView(gap(6));if(isAdmin()){body.addView(smallButton("SỬA GIỜ VÀO CA",navy).apply{setOnClickListener{editAttendanceTime(ctx,"enter_at")}},matchWrap());body.addView(gap(8))}
        val exit=primary("RA CA",red){}
        fun doExit(statusNow:String){exit.isEnabled=false;exit.text="ĐANG RA CA...";api.call("session_exit_guarded",JSONObject().put("session_id",ses.optString("session_id")).put("pda_exit_status",statusNow).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{exit.isEnabled=true;exit.text="RA CA";if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"RA CA thất bại");return@runOnUiThread};TopNotice.show(this,"Đã ghi nhận ra ca.",TopNotice.Kind.SUCCESS);foregroundSync.requestSync();scheduleAttendanceAutoReset(mnv,employeeLookupGeneration)}}}
        exit.setOnClickListener{
            if(activeLabor!=null){showError("Còn công nhật đang làm. Hoàn thành công nhật trước khi ra ca.");return@setOnClickListener}
            if(pda.isBlank()){AlertDialog.Builder(this).setTitle("Xác nhận RA CA").setMessage("Không còn PDA/công nhật cần xử lý. Xác nhận kết thúc phiên?").setNegativeButton("Hủy",null).setPositiveButton("RA CA"){_,_->doExit("")}.show();return@setOnClickListener}
            val statuses=mutableListOf<String>();val arr=MasterDataCache.resourceOptions(this).optJSONArray("pda_statuses")?:JSONArray();for(i in 0 until arr.length()){val v=clean(arr.optString(i));if(v.isNotBlank()&&!statuses.contains(v))statuses.add(v)};if(expectedStatus.isNotBlank()&&!statuses.contains(expectedStatus))statuses.add(0,expectedStatus);if(statuses.isEmpty()){showError("Không có danh mục tình trạng PDA để đối chiếu.");return@setOnClickListener};val sp=spinner(statuses.toTypedArray());val wrap=column(surface).apply{setPadding(dp(16),dp(6),dp(16),dp(4));addView(txt("Seri PDA: $pda",12f,navy,true));addView(gap(5));addView(txt("Tình trạng khi nhận: ${expectedStatus.ifBlank{"Chưa có"}}",10.5f,muted,true));addView(gap(9));addView(labelled("Tình trạng PDA hiện tại",sp))};AlertDialog.Builder(this).setTitle("Đối chiếu PDA trước khi RA CA").setView(wrap).setNegativeButton("Hủy",null).setPositiveButton("KIỂM TRA & RA CA"){_,_->doExit(sp.selectedItem?.toString().orEmpty())}.show()
        };body.addView(exit,matchWrap())
    }'''
s=replace_private_fun(s,'renderActive(body: LinearLayout, ctx: JSONObject) {',active)

ended=r'''    private fun renderEnded(body: LinearLayout, ctx: JSONObject) {
        val ses=ctx.optJSONObject("session")?:JSONObject();val mnv=ses.optString("mnv");body.addView(status("ĐÃ RA CA",teal,Color.rgb(232,248,245)));body.addView(gap(8));body.addView(section("PHIÊN HÔM NAY"));body.addView(details(listOf("Ca" to ses.optString("shift"),"Vào lúc" to formatIso(ses.optString("enter_at")),"Ra lúc" to formatIso(ses.optString("exit_at")),"Công việc PICK cuối" to pickSummary(ses),"Công việc PACK cuối" to packSummary(ses))));body.addView(gap(9));addPdaIdentity(body,ses);body.addView(gap(9));addSessionTimeline(body,mnv)
        if(isAdmin()){body.addView(gap(8));body.addView(section("ADMIN / SUPERADMIN"));body.addView(info("Phiên đã kết thúc chỉ ADMIN/SUPERADMIN được sửa dữ liệu. Mọi sửa/xóa đều có audit; xóa RA CA sẽ mở lại phiên để sửa công việc nếu cần."));body.addView(gap(7));body.addView(smallButton("SỬA GIỜ VÀO CA",navy).apply{setOnClickListener{editAttendanceTime(ctx,"enter_at")}},matchWrap());body.addView(gap(6));body.addView(smallButton("SỬA GIỜ RA CA",orange).apply{setOnClickListener{editAttendanceTime(ctx,"exit_at")}},matchWrap());body.addView(gap(6));body.addView(primary("XÓA GHI NHẬN RA CA",red){deleteExitRecord(ctx)},matchWrap())}
    }'''
s=replace_private_fun(s,'renderEnded(body: LinearLayout, ctx: JSONObject) {',ended)

OPS.write_text(s,encoding='utf-8')

# Extend the direct Service helper installed by S33. Resource GET is now wired, and session correction endpoints are explicit.
a=API.read_text(encoding='utf-8')
old='''val path=if(action=="history_correction")"/v1/corrections" else "/v1/admin/resources";val method=if(action=="resource_master_list")"GET" else "POST";val body=JSONObject(payload.toString())'''
new='''val path=when(action){"history_correction"->"/v1/corrections";"session_work_update"->"/v1/session/work";"session_exit_guarded"->"/v1/session/exit";"attendance_time_correct"->"/v1/session/time-correction";"attendance_exit_delete"->"/v1/session/delete-exit";else->"/v1/admin/resources"};val method=if(action=="resource_master_list")"GET" else "POST";val body=JSONObject(payload.toString())'''
if old not in a: raise SystemExit('S49 serviceOwnerCall path anchor missing')
a=a.replace(old,new,1)
oldset='setOf("resource_master_list","resource_master_upsert","resource_master_delete","history_correction")'
newset='setOf("resource_master_list","resource_master_upsert","resource_master_delete","history_correction","session_work_update","session_exit_guarded","attendance_time_correct","attendance_exit_delete")'
if oldset not in a: raise SystemExit('S49 direct action set anchor missing')
a=a.replace(oldset,newset,1)
# Nested Service errors use {error:{code,...}}. Surface the actual code to UI instead of a JSON object string.
oldres='''Result(ok,http,j,if(ok)null else j.optString("error","HTTP_$http"))'''
newres='''Result(ok,http,j,if(ok)null else (j.optJSONObject("error")?.optString("code")?.takeIf{it.isNotBlank()}?:j.optString("error","HTTP_$http")))'''
if oldres not in a: raise SystemExit('S49 nested error anchor missing')
a=a.replace(oldres,newres,1)
a=a.replace('"resource_master_upsert","resource_master_delete","history_correction","diagnostic_log"','"resource_master_upsert","resource_master_delete","history_correction","session_work_update","session_exit_guarded","attendance_time_correct","attendance_exit_delete","diagnostic_log"')
API.write_text(a,encoding='utf-8')

final=OPS.read_text(encoding='utf-8');api=API.read_text(encoding='utf-8')
checks=[
    (MARK in final,'marker'),('sessionWorkEditor(ctx)' in final,'inline session editor'),('Có công việc PICK' in final and 'Có công việc PACK' in final,'independent pick pack'),
    ('TRẢ PDA' in final,'PDA return'),('attendance_time_correct' in final,'time correction UI'),('attendance_exit_delete' in final,'delete exit UI'),
    ('Còn công nhật đang làm' in final,'labor exit guard'),('session_exit_guarded' in final,'guarded exit'),('ATTENDANCE_TIME_CORRECTED' in final and 'ATTENDANCE_EXIT_DELETED' in final,'timeline corrections'),
    ('/v1/session/work' in api and '/v1/session/delete-exit' in api,'service direct routes'),('optJSONObject("error")' in api,'nested error handling')]
for ok,label in checks:
    if not ok: raise SystemExit('S49 contract missing: '+label)
print('Applied S49: independent Pick+Pack editor, PDA/labor exit guards, attendance time audit corrections, admin delete-exit, resource endpoint wiring')
