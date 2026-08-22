#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
API=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt'
MARK='S52_BETA46_SUPERADMIN_HISTORY_DELETE'

s=OPS.read_text(encoding='utf-8')
if MARK in s:
    print('S52 Beta46 already applied');raise SystemExit(0)

hs=s.find('    private fun historyScreen(){')
he=s.find('\n    private fun historyTimelineScreen(',hs)
if hs<0 or he<0: raise SystemExit('S52 final History block anchors missing')
h=s[hs:he]

old='''        val root=baseRoot("LỊCH SỬ");val body=body();var selectedDate=operationalStore.latestBusinessDate().ifBlank{operationalStore.businessDate()};var filter="ALL";val pageSize=100;var pageStart=0;var query=""'''
new='''        // S52_BETA46_SUPERADMIN_HISTORY_DELETE: SUPERADMIN bulk logical delete with immutable tombstone audit.\n        val root=baseRoot("LỊCH SỬ");val body=body();var selectedDate=operationalStore.latestBusinessDate().ifBlank{operationalStore.businessDate()};var filter="ALL";val pageSize=100;var pageStart=0;var query=""\n        val hiddenHistoryIds=(getSharedPreferences("pp_history_delete_ui",MODE_PRIVATE).getStringSet("hidden_ids",emptySet())?:emptySet()).toMutableSet()\n        val selectedHistoryIds=linkedSetOf<String>();val currentPageDeleteIds=linkedSetOf<String>();val pageChecks=mutableListOf<CheckBox>()'''
if old not in h: raise SystemExit('S52 History header/paging anchor missing')
h=h.replace(old,new,1)

old='''        val box=column(bg);body.addView(box,matchWrap())'''
new='''        val selectionBox=column(bg)\n        val selectionCount=txt("Đã chọn 0 lịch sử",10f,muted,true)\n        fun updateSelectedCount(){selectionCount.text="Đã chọn ${selectedHistoryIds.size} lịch sử"}\n        if(isSuper()){\n            selectionBox.addView(info("Quản trị cao nhất có thể chọn một hoặc nhiều mục đã đồng bộ để xóa. Trước khi xóa phải xác thực lại mật khẩu; dấu vết kiểm toán của thao tác xóa vẫn được giữ."))\n            selectionBox.addView(gap(6));selectionBox.addView(selectionCount)\n            val choose=row(bg);val selectPage=smallButton("CHỌN TRANG",navy);val clear=smallButton("BỎ CHỌN",muted)\n            choose.addView(selectPage,LinearLayout.LayoutParams(0,dp(42),1f).apply{marginEnd=dp(3)});choose.addView(clear,LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(3)});selectionBox.addView(gap(5));selectionBox.addView(choose,matchWrap())\n            val deleteSelected=smallButton("XÓA ĐÃ CHỌN",red);selectionBox.addView(gap(5));selectionBox.addView(deleteSelected,matchWrap());selectionBox.addView(gap(8))\n            selectPage.setOnClickListener{selectedHistoryIds.addAll(currentPageDeleteIds);pageChecks.forEach{it.isChecked=true};updateSelectedCount()}\n            clear.setOnClickListener{selectedHistoryIds.clear();pageChecks.forEach{it.isChecked=false};updateSelectedCount()}\n            deleteSelected.setOnClickListener{deleteHistoryBulk(selectedHistoryIds.toList())}\n            body.addView(selectionBox,matchWrap())\n        }\n        val box=column(bg);body.addView(box,matchWrap())'''
if old not in h: raise SystemExit('S52 History result box anchor missing')
h=h.replace(old,new,1)

scan_start=h.find('        fun scanDate(date:String,needle:String,remaining:Int,out:MutableList<JSONObject>){')
scan_end=h.find('        fun loadRows():MutableList<JSONObject>{',scan_start)
if scan_start<0 or scan_end<0: raise SystemExit('S52 scanDate anchors missing')
scan=r'''        fun scanDate(date:String,needle:String,remaining:Int,out:MutableList<JSONObject>){
            if(remaining<=0)return;val day=operationalStore.loadDay(date)?:return;val events=day.optJSONArray("events")?:JSONArray();val n=needle.uppercase()
            // First pass: collect tombstones before considering older target events in the same day snapshot.
            for(i in 0 until events.length()){
                val e=events.optJSONObject(i)?:continue;if(e.optString("event_type").uppercase()!="HISTORY_DELETE")continue
                val p=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrDefault(JSONObject());val ids=p.optJSONArray("target_event_ids")?:JSONArray();for(j in 0 until ids.length()){val id=ids.optString(j);if(id.isNotBlank())hiddenHistoryIds.add(id)}
            }
            for(i in 0 until events.length()){
                if(out.size>=remaining)return;val e=events.optJSONObject(i)?:continue;val type=e.optString("event_type");val realId=e.optString("event_id");if(type.uppercase()=="HISTORY_DELETE"||realId in hiddenHistoryIds)continue
                var mnv=e.optString("mnv");var full=e.optString("full_name");var actor=e.optString("actor").ifBlank{e.optString("actor_id")};var detail=e.optString("detail");var shift=e.optString("shift")
                var p:JSONObject?=null;if(mnv.isBlank()||full.isBlank()||actor.isBlank()||detail.isBlank()||n.isNotBlank()){p=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrNull();mnv=mnv.ifBlank{p?.optString("mnv").orEmpty()};full=full.ifBlank{p?.optString("full_name").orEmpty()};actor=actor.ifBlank{p?.optString("actor").orEmpty()};detail=detail.ifBlank{p?.optString("detail").orEmpty().ifBlank{p?.optString("labor_type").orEmpty()}};shift=shift.ifBlank{p?.optString("shift").orEmpty()}}
                if(full.isBlank()&&mnv.isNotBlank())full=MasterDataCache.employee(this,mnv)?.optString("full_name").orEmpty();val label=friendly(type,e.optString("label"));if(n.isNotBlank()&&!listOf(mnv,full,label,actor,detail,shift).any{it.uppercase().contains(n)})continue
                out.add(JSONObject().put("event_id",realId.ifBlank{"$date:$i"}).put("event_type",type).put("entity_type",e.optString("entity_type")).put("entity_id",e.optString("entity_id")).put("payload_json",e.optString("payload_json","{}")).put("label",label).put("mnv",mnv).put("full_name",full).put("actor",actor).put("detail",detail).put("shift",shift).put("at_iso",e.optString("at_iso").ifBlank{e.optString("committed_at")}.ifBlank{e.optString("at")}).put("authority_seq",e.optLong("authority_seq",0L)).put("business_date",date).put("history_source","SERVICE_CANONICAL").put("local_status","CONFIRMED"))
            }
        }
'''
h=h[:scan_start]+scan+h[scan_end:]

old='''                val id=local.optString("event_id");val idx=out.indexOfFirst{it.optString("event_id")==id};if(idx>=0){out[idx].put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at"));continue}'''
new='''                val id=local.optString("event_id");if(id in hiddenHistoryIds)continue;val idx=out.indexOfFirst{it.optString("event_id")==id};if(idx>=0){out[idx].put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at"));continue}'''
if old not in h: raise SystemExit('S52 local History merge anchor missing')
h=h.replace(old,new,1)

old='''            box.removeAllViews();val rows=loadRows();'''
new='''            box.removeAllViews();currentPageDeleteIds.clear();pageChecks.clear();val rows=loadRows();'''
if old not in h: raise SystemExit('S52 render reset anchor missing')
h=h.replace(old,new,1)

loop_start=h.find('            for(g in visible){')
loop_end=h.find('            if(visible.isEmpty())',loop_start)
if loop_start<0 or loop_end<0: raise SystemExit('S52 History visible loop anchors missing')
loop=r'''            for(g in visible){
                val items=g.value;val first=items.first();val state=if(items.any{statusOf(it)=="FAILED"})"FAILED" else if(items.any{statusOf(it)=="PENDING"})"PENDING" else "SYNCED";val label=when(state){"FAILED"->"Lỗi đồng bộ";"PENDING"->"Chưa đồng bộ";else->"Đã đồng bộ"};val tint=when(state){"FAILED"->Color.rgb(254,242,242);"PENDING"->Color.rgb(255,251,235);else->Color.rgb(240,253,250)};val mnv=first.optString("mnv");val full=first.optString("full_name");val last=items.first()
                val deletable=items.filter{it.optString("history_source")=="SERVICE_CANONICAL"&&it.optLong("authority_seq",0L)>0L}.map{it.optString("event_id")}.filter{it.isNotBlank()}.distinct();currentPageDeleteIds.addAll(deletable)
                val card=column(tint).apply{
                    setPadding(dp(13),dp(11),dp(13),dp(11));background=outlineBg(tint,17)
                    val top=row(tint).apply{gravity=Gravity.CENTER_VERTICAL
                        if(isSuper()&&deletable.isNotEmpty()){val c=CheckBox(this@OperationsActivity).apply{isChecked=deletable.all{it in selectedHistoryIds};setOnCheckedChangeListener{_,on->if(on)selectedHistoryIds.addAll(deletable)else selectedHistoryIds.removeAll(deletable.toSet());updateSelectedCount()}};pageChecks.add(c);addView(c,size(dp(42),dp(42)))}
                        addView(txt(listOf(mnv,full).filter{it.isNotBlank()}.joinToString(" – ").ifBlank{"Thao tác hệ thống"},12.5f,ink,true),LinearLayout.LayoutParams(0,-2,1f));addView(badge(label,when(state){"FAILED"->red;"PENDING"->Color.rgb(217,119,6);else->teal}))
                    };addView(top,matchWrap());addView(txt("${last.optString("label")} • ${formatIso(last.optString("at_iso"))} • ${last.optString("actor").ifBlank{"Hệ thống"}}",10f,muted,false));if(last.optString("detail").isNotBlank())addView(txt(last.optString("detail"),9.5f,muted,false).apply{maxLines=2});if(isSuper()&&deletable.isEmpty())addView(txt("Mục chưa đồng bộ nên chưa thể xóa.",9.1f,orange,false));setOnClickListener{historyTimelineScreen(mnv,items.toMutableList())}
                };box.addView(card,matchWrap());box.addView(gap(6))
            }
            updateSelectedCount()
'''
h=h[:loop_start]+loop+h[loop_end:]

s=s[:hs]+h+s[he:]

anchor='    private fun historyTimelineScreen('
idx=s.find(anchor)
if idx<0: raise SystemExit('S52 timeline helper insertion anchor missing')
helper=r'''    private fun deleteHistoryBulk(ids:List<String>){
        if(!isSuper()){showError("Chỉ Quản trị cao nhất được xóa lịch sử.");return}
        val clean=ids.filter{it.isNotBlank()}.distinct();if(clean.isEmpty()){showError("Chọn ít nhất một lịch sử đã đồng bộ cần xóa.");return}
        AlertDialog.Builder(this).setTitle("Xóa ${clean.size} lịch sử?").setMessage("Các mục đã chọn sẽ bị ẩn khỏi lịch sử trên các PDA sau khi đồng bộ. Dữ liệu gốc không bị sửa vật lý và dấu vết kiểm toán của thao tác xóa vẫn được giữ.").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->
            verifyDeletePassword("xóa ${clean.size} lịch sử"){
                api.call("history_delete",JSONObject().put("event_ids",JSONArray(clean)).put("idempotency_key",UUID.randomUUID().toString()).put("reason","SUPERADMIN xóa lịch sử từ PDA")){r->runOnUiThread{
                    if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không xóa được lịch sử");return@runOnUiThread}
                    val prefs=getSharedPreferences("pp_history_delete_ui",MODE_PRIVATE);val hidden=(prefs.getStringSet("hidden_ids",emptySet())?:emptySet()).toMutableSet();hidden.addAll(clean);prefs.edit().putStringSet("hidden_ids",hidden).apply()
                    TopNotice.show(this,"Đã xóa ${clean.size} lịch sử.",TopNotice.Kind.SUCCESS);foregroundSync.requestSync();historyScreen()
                }}
            }
        }.show()
    }

'''
s=s[:idx]+helper+s[idx:]
OPS.write_text(s,encoding='utf-8')

# Route the destructive command directly to Service. Password itself is never placed in this request.
a=API.read_text(encoding='utf-8')
route='''"account_delete"->"/v1/admin/accounts/delete";else->"/v1/admin/resources"'''
if route not in a: raise SystemExit('S52 BetaApiClient route anchor missing')
a=a.replace(route,'''"account_delete"->"/v1/admin/accounts/delete";"history_delete"->"/v1/history/delete";else->"/v1/admin/resources"''',1)
action='''"service_connections","account_delete")'''
if action not in a: raise SystemExit('S52 BetaApiClient action-set anchor missing')
a=a.replace(action,'''"service_connections","account_delete","history_delete")''',1)
API.write_text(a,encoding='utf-8')

out=OPS.read_text(encoding='utf-8');api=API.read_text(encoding='utf-8')
checks=[(MARK in out,'marker'),('deleteHistoryBulk' in out,'delete helper'),('CHỌN TRANG' in out,'page multi-select'),('XÓA ĐÃ CHỌN' in out,'bulk delete button'),('verifyDeletePassword("xóa ${clean.size} lịch sử")' in out,'password gate'),('HISTORY_DELETE' in out and 'target_event_ids' in out,'tombstone filter'),('/v1/history/delete' in api,'service route'),('"history_delete"' in api,'direct action')]
for ok,label in checks:
    if not ok: raise SystemExit('S52 contract missing: '+label)
print('Applied S52 Beta46: SUPERADMIN password-gated single/page bulk logical History delete + tombstone filtering')
