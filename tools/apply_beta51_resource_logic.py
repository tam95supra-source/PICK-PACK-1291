#!/usr/bin/env python3
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
GRADLE=ROOT/'app/build.gradle.kts'
text=OPS.read_text(encoding='utf-8')

helper='''    private fun naturalUserCompare(aRaw:String,bRaw:String):Int{
        val a=aRaw.trim();val b=bRaw.trim();val rx=Regex("^(.*?)(\\\\d+)$")
        val am=rx.matchEntire(a);val bm=rx.matchEntire(b)
        if(am!=null&&bm!=null){
            val ap=am.groupValues[1].lowercase();val bp=bm.groupValues[1].lowercase();val prefix=ap.compareTo(bp)
            if(prefix!=0)return prefix
            val an=am.groupValues[2].toLongOrNull();val bn=bm.groupValues[2].toLongOrNull()
            if(an!=null&&bn!=null&&an!=bn)return an.compareTo(bn)
        }
        return a.compareTo(b,ignoreCase=true)
    }
    private fun <T> sortedByNaturalUser(items:List<T>,value:(T)->String):List<T> = items.sortedWith(Comparator{a,b->naturalUserCompare(value(a),value(b))})
    private fun compactReissueButton(label:String,enabled:Boolean,onClick:()->Unit)=smallButton(label,orange).apply{
        isAllCaps=false;textSize=8.6f;setSingleLine(true);setPadding(dp(3),0,dp(3),0);isEnabled=enabled;alpha=if(enabled)1f else .45f;setOnClickListener{if(isEnabled)onClick()}
    }

'''
anchor='    private fun pdaInput(pdas:JSONArray,currentSerial:String="",onSelected:(JSONObject?)->Unit={}):AutoCompleteTextView{'
if 'private fun naturalUserCompare(' not in text:
    if text.count(anchor)!=1: raise SystemExit(f'PDA_INPUT_ANCHOR_COUNT={text.count(anchor)}')
    text=text.replace(anchor,helper+anchor)

editor='''    private fun sessionWorkEditor(ctx:JSONObject){
        val ses=ctx.optJSONObject("session")?:return;val mnv=ses.optString("mnv")
        if(ses.optString("state")!="ACTIVE"){showError("Phiên đã ra ca. ADMIN/SUPERADMIN hãy hủy ghi nhận ra ca trước khi sửa công việc.");return}
        val options=PdaLocalProjection.resourceOptions(this,mnv)
        val pdas=options.optJSONArray("pdas")?:JSONArray();val picks=options.optJSONArray("user_picks")?:JSONArray();val pickReissue=options.optJSONArray("user_picks_reissue")?:JSONArray()
        val packs=options.optJSONArray("pack_tables")?:JSONArray();val packReissue=options.optJSONArray("pack_tables_reissue")?:JSONArray()
        val dialogBody=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))}
        dialogBody.addView(info("PICK và PACK là hai phần độc lập. Có thể giữ đồng thời cả hai; lưu mới chỉ cập nhật trạng thái hiện tại, lịch sử các lần trước vẫn giữ nguyên."));dialogBody.addView(gap(8))
        val pickOn=CheckBox(this).apply{text="Có công việc PICK";isChecked=ses.optString("pda_serial").isNotBlank()||ses.optString("user_pick").isNotBlank()||ses.optString("work_choice")=="PICK";setTextColor(ink)}
        val packOn=CheckBox(this).apply{text="Có công việc PACK";isChecked=ses.optString("pack_table").isNotBlank()||ses.optString("user_pack").isNotBlank()||ses.optString("work_choice")=="PACK";setTextColor(ink)}
        dialogBody.addView(pickOn,matchWrap());dialogBody.addView(packOn,matchWrap());dialogBody.addView(gap(7));val host=column(surface);dialogBody.addView(host,matchWrap())
        var pdaField:AutoCompleteTextView?=null;var selectedPda:JSONObject?=null
        var pickSpinner:Spinner?=null;var pickChoices=mutableListOf<Pair<String,Boolean>>()
        var selectedPack:JSONObject?=null;var allowPickReissue=false;var allowPackReissue=false
        fun rebuild(){
            host.removeAllViews();pdaField=null;selectedPda=null;pickSpinner=null;pickChoices.clear();selectedPack=null
            if(pickOn.isChecked){
                host.addView(section("PICK"))
                pdaField=pdaInput(pdas,ses.optString("pda_serial")){selectedPda=it}
                host.addView(labelled("PDA (có thể đổi / trả)",pdaField!!));host.addView(gap(4));host.addView(pdaSelectedPanel(pdas,pdaField!!),matchWrap());host.addView(gap(5))
                host.addView(smallButton("TRẢ PDA",orange).apply{setOnClickListener{selectedPda=null;pdaField?.setText("",false)}},matchWrap());host.addView(gap(7))
                val base=mutableListOf<String>();for(i in 0 until picks.length()){val id=picks.optString(i).trim();if(id.isNotBlank()&&!base.contains(id))base.add(id)}
                val currentPick=ses.optString("user_pick").trim();if(currentPick.isNotBlank()&&!base.contains(currentPick))base.add(currentPick)
                pickChoices=mutableListOf("" to false);val labels=mutableListOf("Không dùng")
                sortedByNaturalUser(base){it}.forEach{pickChoices.add(it to false);labels.add(it)}
                if(allowPickReissue){
                    val used=mutableListOf<String>();for(i in 0 until pickReissue.length()){val id=pickReissue.optJSONObject(i)?.optString("id").orEmpty().trim();if(id.isNotBlank()&&!base.contains(id)&&!used.contains(id))used.add(id)}
                    sortedByNaturalUser(used){it}.forEach{pickChoices.add(it to true);labels.add("⚠ $it • ĐÃ DÙNG HÔM NAY")}
                }
                pickSpinner=spinner(labels.toTypedArray());val cur=pickChoices.indexOfFirst{it.first==currentPick};if(cur>=0)pickSpinner!!.setSelection(cur)
                val userRow=row(surface).apply{gravity=Gravity.CENTER_VERTICAL}
                userRow.addView(pickSpinner!!,LinearLayout.LayoutParams(0,dp(50),1.35f).apply{marginEnd=dp(5)})
                userRow.addView(compactReissueButton("Phát lại user pick",pickReissue.length()>0&&!allowPickReissue){allowPickReissue=true;rebuild()},LinearLayout.LayoutParams(0,dp(46),.85f))
                host.addView(labelled("User Pick hy1.outbound",userRow));host.addView(gap(9))
            }
            if(packOn.isChecked){
                host.addView(section("PACK"))
                val rows=mutableListOf<JSONObject>()
                fun addPack(a:JSONArray,duplicate:Boolean){for(i in 0 until a.length()){val o=a.optJSONObject(i)?:continue;val t=o.optString("table").trim();val u=o.optString("user_pack").trim();if(t.isBlank()||u.isBlank())continue;val existing=rows.indexOfFirst{it.optString("table")==t&&it.optString("user_pack")==u};if(existing>=0){if(!duplicate)rows[existing].put("duplicate_user",false);continue};rows.add(JSONObject(o.toString()).put("duplicate_user",duplicate))}}
                addPack(packs,false);if(allowPackReissue)addPack(packReissue,true)
                val currentTable=ses.optString("pack_table").trim();val currentUser=ses.optString("user_pack").trim()
                if(currentTable.isNotBlank()&&currentUser.isNotBlank()&&!rows.any{it.optString("table")==currentTable&&it.optString("user_pack")==currentUser})rows.add(JSONObject().put("table",currentTable).put("user_pack",currentUser).put("duplicate_user",false))
                val tables=rows.map{it.optString("table")}.filter{it.isNotBlank()}.distinct().sortedWith(Comparator{a,b->naturalUserCompare(a,b)})
                val tableSp=spinner((if(tables.isEmpty())listOf("Không có bàn Pack khả dụng")else tables).toTypedArray());val tableCur=tables.indexOf(currentTable);if(tableCur>=0)tableSp.setSelection(tableCur)
                host.addView(labelled("Bàn Pack",tableSp));host.addView(gap(7));val userHost=column(surface);host.addView(userHost,matchWrap())
                fun renderPackUsers(){
                    userHost.removeAllViews();selectedPack=null
                    if(tables.isEmpty()){userHost.addView(info("Không có User Pack khả dụng."));return}
                    val table=tables.getOrNull(tableSp.selectedItemPosition).orEmpty();val mapped=sortedByNaturalUser(rows.filter{it.optString("table")==table}){it.optString("user_pack")}
                    val labels=mapped.map{if(it.optBoolean("duplicate_user"))"⚠ ${it.optString("user_pack")} • ĐÃ DÙNG HÔM NAY" else it.optString("user_pack")}
                    val userSp=spinner((if(labels.isEmpty())listOf("Không có User Pack")else labels).toTypedArray());val userCur=mapped.indexOfFirst{it.optString("table")==currentTable&&it.optString("user_pack")==currentUser};if(userCur>=0)userSp.setSelection(userCur)
                    selectedPack=mapped.getOrNull(userSp.selectedItemPosition)
                    userSp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){selectedPack=mapped.getOrNull(pos)};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit}
                    val userRow=row(surface).apply{gravity=Gravity.CENTER_VERTICAL};userRow.addView(userSp,LinearLayout.LayoutParams(0,dp(50),1.35f).apply{marginEnd=dp(5)})
                    userRow.addView(compactReissueButton("Phát lại user pack",packReissue.length()>0&&!allowPackReissue){allowPackReissue=true;rebuild()},LinearLayout.LayoutParams(0,dp(46),.85f));userHost.addView(labelled("User Pack",userRow))
                }
                tableSp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){renderPackUsers()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};renderPackUsers();host.addView(gap(7))
            }
            if(!pickOn.isChecked&&!packOn.isChecked)host.addView(info("Không gán công việc PICK/PACK. Lưu để trả toàn bộ tài nguyên đang giữ."))
        }
        pickOn.setOnCheckedChangeListener{_,_->rebuild()};packOn.setOnCheckedChangeListener{_,_->rebuild()};rebuild()
        AlertDialog.Builder(this).setTitle("Thêm / sửa công việc trong ca").setView(ScrollView(this).apply{addView(dialogBody)}).setNegativeButton("Hủy",null).setPositiveButton("LƯU"){_,_->
            val p=JSONObject().put("session_id",ses.optString("session_id")).put("idempotency_key",UUID.randomUUID().toString())
            val pickChoice=if(pickOn.isChecked)pickChoices.getOrNull(pickSpinner?.selectedItemPosition?:0) else null;val pick=pickChoice?.first.orEmpty();val pda=if(pickOn.isChecked)selectedPda?.optString("serial").orEmpty() else ""
            p.put("pda_serial",pda).put("user_pick",pick)
            var reissue=pickChoice?.second==true
            if(packOn.isChecked){val row=selectedPack;if(row==null){showError("Chọn Bàn Pack + User Pack hợp lệ.");return@setPositiveButton};p.put("pack_table",row.optString("table")).put("user_pack",row.optString("user_pack"));reissue=reissue||row.optBoolean("duplicate_user")}else p.put("pack_table","").put("user_pack","")
            if(reissue)p.put("duplicate_user",true)
            val current=ses.optString("work_choice");val primary=when{pickOn.isChecked&&packOn.isChecked&&current in setOf("PICK","PACK")->current;pickOn.isChecked->"PICK";packOn.isChecked->"PACK";else->"KHONG"}
            val baseNote=when{pickOn.isChecked&&packOn.isChecked->"PICK + PACK";pickOn.isChecked->"PICK";packOn.isChecked->"PACK";else->"Đã trả tài nguyên"};p.put("work_choice",primary).put("resource_note",if(reissue)"$baseNote • PHÁT LẠI USER" else baseNote)
            api.call("session_work_update",p){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không cập nhật được công việc");return@runOnUiThread};TopNotice.show(this,"Đã cập nhật công việc trong ca.",TopNotice.Kind.SUCCESS);foregroundSync.requestSync();val next=returnedSessionContext(ctx,r);if(next!=null)renderEmployee(next,PdaLocalProjection.resourceOptions(this,mnv))else loadEmployee(mnv)}}
        }.show()
    }

'''
pat=r'    private fun sessionWorkEditor\(ctx:JSONObject\)\{.*?\n    private fun editableTime'
text,n=re.subn(pat,editor+'    private fun editableTime',text,count=1,flags=re.S)
if n!=1: raise SystemExit(f'EDITOR_REPLACE_COUNT={n}')

enter='''    private fun renderEnter(body: LinearLayout, ctx: JSONObject, masters: JSONObject) {
        val e=ctx.optJSONObject("employee")?:JSONObject();val mnv=e.optString("mnv")
        body.addView(section("PHÂN CÔNG TRONG CA"))
        val now=java.time.LocalTime.now(ZoneId.of("Asia/Ho_Chi_Minh"));var shiftValue=when{now.isBefore(java.time.LocalTime.of(8,0))->"Ca 1";now.isBefore(java.time.LocalTime.of(10,0))->"Ca HC";else->"Ca 2"}
        var workValue=when{e.optString("main_position").trim().equals("Pick",true)->"PICK";e.optString("main_position").trim().equals("Pack",true)->"PACK";else->"KHONG"}
        val resourceBox=column(bg);val shiftBox=column(bg);val workBox=column(bg);var rebuildResources:(()->Unit)?=null
        shiftBox.addView(segmentedChoice(listOf("Ca 1" to "Ca 1","Ca HC" to "Ca HC","Ca 2" to "Ca 2"),shiftValue){shiftValue=it;rebuildResources?.invoke()},matchWrap())
        workBox.addView(segmentedChoice(listOf("Không" to "KHONG","Pick" to "PICK","Pack" to "PACK"),workValue){workValue=it;rebuildResources?.invoke()},matchWrap())
        body.addView(labelled("Ca",shiftBox));body.addView(gap(9));body.addView(labelled("Vị trí trong ca",workBox));body.addView(gap(8));body.addView(resourceBox,matchWrap())
        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val pickReissue=masters.optJSONArray("user_picks_reissue")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray();val packReissue=masters.optJSONArray("pack_tables_reissue")?:JSONArray()
        var pdaField:AutoCompleteTextView?=null;var selectedPda:JSONObject?=null;var pickSpinner:Spinner?=null;var pickChoices=mutableListOf<Pair<String,Boolean>>();var packSelection:JSONObject?=null
        var allowPickReissue=false;var allowPackReissue=false
        fun renderPick(){
            pdaField=pdaInput(pdas,onSelected={selectedPda=it});resourceBox.addView(labelled("Seri PDA — gõ 5 số cuối",pdaField!!));resourceBox.addView(gap(5));resourceBox.addView(pdaSelectedPanel(pdas,pdaField!!),matchWrap());resourceBox.addView(gap(8))
            val base=mutableListOf<String>();for(i in 0 until picks.length()){val id=picks.optString(i).trim();if(id.isNotBlank()&&!base.contains(id))base.add(id)}
            pickChoices=mutableListOf("" to false);val labels=mutableListOf("Không dùng");sortedByNaturalUser(base){it}.forEach{pickChoices.add(it to false);labels.add(it)}
            if(allowPickReissue){val used=mutableListOf<String>();for(i in 0 until pickReissue.length()){val id=pickReissue.optJSONObject(i)?.optString("id").orEmpty().trim();if(id.isNotBlank()&&!base.contains(id)&&!used.contains(id))used.add(id)};sortedByNaturalUser(used){it}.forEach{pickChoices.add(it to true);labels.add("⚠ $it • ĐÃ DÙNG HÔM NAY")}}
            pickSpinner=spinner(labels.toTypedArray());val userRow=row(bg).apply{gravity=Gravity.CENTER_VERTICAL};userRow.addView(pickSpinner!!,LinearLayout.LayoutParams(0,dp(50),1.35f).apply{marginEnd=dp(5)});userRow.addView(compactReissueButton("Phát lại user pick",pickReissue.length()>0&&!allowPickReissue){allowPickReissue=true;rebuildResources?.invoke()},LinearLayout.LayoutParams(0,dp(46),.85f));resourceBox.addView(labelled("User Pick hy1.outbound",userRow))
        }
        fun renderPack(){
            val rows=mutableListOf<JSONObject>();fun addRows(a:JSONArray,duplicate:Boolean){for(i in 0 until a.length()){val o=a.optJSONObject(i)?:continue;val t=o.optString("table").trim();val u=o.optString("user_pack").trim();if(t.isBlank()||u.isBlank())continue;val existing=rows.indexOfFirst{it.optString("table")==t&&it.optString("user_pack")==u};if(existing>=0){if(!duplicate)rows[existing].put("duplicate_user",false);continue};rows.add(JSONObject(o.toString()).put("duplicate_user",duplicate))}};addRows(packs,false);if(allowPackReissue)addRows(packReissue,true)
            val tables=rows.map{it.optString("table")}.filter{it.isNotBlank()}.distinct().sortedWith(Comparator{a,b->naturalUserCompare(a,b)});val tableSp=spinner((if(tables.isEmpty())listOf("Không có bàn Pack khả dụng")else tables).toTypedArray());resourceBox.addView(labelled("Bàn Pack",tableSp));resourceBox.addView(gap(8));val userHost=column(bg);resourceBox.addView(userHost,matchWrap())
            fun renderUsers(){userHost.removeAllViews();packSelection=null;if(tables.isEmpty()){userHost.addView(info("Không có User Pack khả dụng."));return};val table=tables.getOrNull(tableSp.selectedItemPosition).orEmpty();val mapped=sortedByNaturalUser(rows.filter{it.optString("table")==table}){it.optString("user_pack")};val labels=mapped.map{if(it.optBoolean("duplicate_user"))"⚠ ${it.optString("user_pack")} • ĐÃ DÙNG HÔM NAY" else it.optString("user_pack")};val userSp=spinner((if(labels.isEmpty())listOf("Không có User Pack")else labels).toTypedArray());packSelection=mapped.getOrNull(0);userSp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){packSelection=mapped.getOrNull(pos)};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};val userRow=row(bg).apply{gravity=Gravity.CENTER_VERTICAL};userRow.addView(userSp,LinearLayout.LayoutParams(0,dp(50),1.35f).apply{marginEnd=dp(5)});userRow.addView(compactReissueButton("Phát lại user pack",packReissue.length()>0&&!allowPackReissue){allowPackReissue=true;rebuildResources?.invoke()},LinearLayout.LayoutParams(0,dp(46),.85f));userHost.addView(labelled("User Pack",userRow))}
            tableSp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){renderUsers()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};renderUsers()
        }
        rebuildResources={resourceBox.removeAllViews();pdaField=null;selectedPda=null;pickSpinner=null;pickChoices.clear();packSelection=null;when(workValue){"PICK"->renderPick();"PACK"->renderPack();else->Unit}}
        rebuildResources?.invoke();body.addView(gap(12));val enterBtn=primary("VÀO CA",teal){}
        enterBtn.setOnClickListener{
            val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv).put("shift",shiftValue).put("work_choice",workValue)
            if(workValue=="PICK"){
                val p=selectedPda;val expected=if(p==null)"" else p.optString("last5").trim().ifBlank{p.optString("serial").takeLast(5)};if(p==null||pdaField?.text?.toString()?.trim()!=expected){showError("Hãy gõ 5 số cuối và chọn PDA trong danh sách gợi ý.");return@setOnClickListener};payload.put("pda_serial",p.optString("serial")).put("pda_status_at_enter",p.optString("status"));val picked=pickChoices.getOrNull(pickSpinner?.selectedItemPosition?:0)?:("" to false);if(picked.first.isNotBlank())payload.put("user_pick",picked.first);if(picked.second)payload.put("duplicate_user",true).put("resource_note","PHÁT LẠI USER")
            }
            if(workValue=="PACK"){
                val row=packSelection;if(row==null){showError("Chọn Bàn Pack và User Pack hợp lệ.");return@setOnClickListener};payload.put("pack_table",row.optString("table")).put("user_pack",row.optString("user_pack"));if(row.optBoolean("duplicate_user"))payload.put("duplicate_user",true).put("resource_note","PHÁT LẠI USER")
            }
            val actionGeneration=employeeLookupGeneration;enterBtn.isEnabled=false;enterBtn.text="ĐANG VÀO CA...";api.call("enter",payload){r->runOnUiThread{enterBtn.isEnabled=true;enterBtn.text="VÀO CA";if(!r.ok)showError(r.error?:"VÀO CA thất bại")else{TopNotice.show(this,"Đã ghi nhận vào ca.",TopNotice.Kind.SUCCESS);scheduleAttendanceAutoReset(mnv,actionGeneration)}}}
        }
        body.addView(enterBtn,matchWrap())
    }

'''
pat=r'    private fun renderEnter\(body: LinearLayout, ctx: JSONObject, masters: JSONObject\) \{.*?\n    private fun laborHome'
text,n=re.subn(pat,enter+'    private fun laborHome',text,count=1,flags=re.S)
if n!=1: raise SystemExit(f'RENDER_ENTER_REPLACE_COUNT={n}')

for forbidden in ['Chọn gợi ý để hiện đầy đủ Seri PDA','Không dùng User hy1.outbound','PHÁT LẠI USER ĐÃ DÙNG','ẨN USER TRÙNG']:
    if forbidden in text: raise SystemExit('FORBIDDEN_REMAINS:'+forbidden)
for required in ['Phát lại user pick','Phát lại user pack','User Pick hy1.outbound','ĐÃ DÙNG HÔM NAY','private fun naturalUserCompare']:
    if required not in text: raise SystemExit('REQUIRED_MISSING:'+required)
OPS.write_text(text,encoding='utf-8')

g=GRADLE.read_text(encoding='utf-8')
if 'versionCode = 56' not in g or 'versionName = "0.4.2-beta.50"' not in g: raise SystemExit('BETA50_VERSION_ANCHOR_MISSING')
g=g.replace('versionCode = 56','versionCode = 57',1).replace('versionName = "0.4.2-beta.50"','versionName = "0.4.2-beta.51"',1)
GRADLE.write_text(g,encoding='utf-8')
print('BETA51_ANDROID_RESOURCE_PATCH=PASS')
